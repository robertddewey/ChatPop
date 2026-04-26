#!/usr/bin/env bash
# Configure backend/.env to talk to AWS (RDS + S3) instead of local Docker.
#
# Pulls:
#   - RDS endpoint and credentials (Secrets Manager)
#   - S3 bucket name (Terraform output)
# Updates only the keys it owns; everything else in .env is preserved.
#
# Re-runnable. Pass the dev name as the first argument (defaults to whatever
# is stored in .dev-identity, then falls back to "robert").

set -euo pipefail

DEV_NAME_DEFAULT="robert"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${PROJECT_ROOT}/infra/terraform"
ENV_FILE="${PROJECT_ROOT}/backend/.env"
IDENTITY_FILE="${PROJECT_ROOT}/.dev-identity"
AWS_PROFILE_NAME="chatpop-dev"
AWS_PROFILE_ADMIN_NAME="chatpop-dev-admin"

# Deterministic resource naming derived from terraform's
# `${var.project}-${var.environment}` (defaults: chatpop-dev). Used as fallback
# values when terraform state isn't on this machine (e.g., 2nd admin laptop).
NAME_PREFIX_DEFAULT="chatpop-dev"
RDS_INSTANCE_ID_DEFAULT="${NAME_PREFIX_DEFAULT}-postgres"
SECRET_NAME_DEFAULT="${NAME_PREFIX_DEFAULT}/rds/master"
REGION_DEFAULT="us-east-1"

RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'; BLUE=$'\033[0;34m'; BOLD=$'\033[1m'; NC=$'\033[0m'
err()  { printf "${RED}error:${NC} %s\n" "$*" >&2; exit 1; }
ok()   { printf "${GREEN}✓${NC} %s\n" "$*"; }
info() { printf "${BLUE}→${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}!${NC} %s\n" "$*"; }

# --- Arg parsing -----------------------------------------------------------

DEV_NAME="${1:-}"
if [[ -z "$DEV_NAME" ]]; then
  if [[ -f "$IDENTITY_FILE" ]]; then
    DEV_NAME=$(cat "$IDENTITY_FILE")
  else
    DEV_NAME="$DEV_NAME_DEFAULT"
  fi
fi

# Normalize: lowercase, [a-z0-9_] only, no leading/trailing underscores.
# Use python3 — bash's `tr` includes the trailing newline of `echo`, leaving
# spurious underscores. python3 is reliable across macOS/Linux.
normalize() {
  python3 -c '
import re, sys
s = sys.argv[1].lower()
s = re.sub(r"[^a-z0-9_]", "_", s)
s = re.sub(r"_+", "_", s)
print(s.strip("_"))
' "$1"
}

DEV_NAME=$(normalize "$DEV_NAME")
[[ -n "$DEV_NAME" ]] || err "Empty dev name after normalization"

echo "$DEV_NAME" > "$IDENTITY_FILE"

CURRENT_BRANCH=$(cd "$PROJECT_ROOT" && git symbolic-ref --short HEAD 2>/dev/null || echo "main")
BRANCH_SAFE=$(normalize "$CURRENT_BRANCH")

MAIN_DB="${DEV_NAME}_main"
DB_NAME="${DEV_NAME}_${BRANCH_SAFE}"
S3_PREFIX="${DEV_NAME}/${BRANCH_SAFE}"

printf "${BOLD}Configure backend/.env for AWS${NC}\n"
printf "==================================\n\n"
ok "Dev name:    ${DEV_NAME}"
ok "Branch:      ${CURRENT_BRANCH} → ${BRANCH_SAFE}"
ok "DB name:     ${DB_NAME}"
ok "S3 prefix:   ${S3_PREFIX}"
echo

# --- Preflight -------------------------------------------------------------

[[ -f "$ENV_FILE" ]] || err "${ENV_FILE} not found"

aws --profile "$AWS_PROFILE_NAME" sts get-caller-identity >/dev/null 2>&1 \
  || err "AWS profile '${AWS_PROFILE_NAME}' not working"
ok "AWS profile authenticated"

# --- Pull values from AWS / terraform --------------------------------------
#
# Try terraform first (fast path on the admin's primary machine). Fall back
# to AWS API queries when state isn't available locally — the case on a 2nd
# admin laptop or any developer machine that's never run terraform.

tf_get() {
  (cd "$TF_DIR" 2>/dev/null && terraform output -raw "$1" 2>/dev/null)
}

RDS_HOST=$(tf_get rds_address)              || RDS_HOST=""
RDS_PORT=$(tf_get rds_port)                 || RDS_PORT=""
SECRET_NAME=$(tf_get rds_master_secret_name) || SECRET_NAME=""
BUCKET=$(tf_get media_bucket_name)          || BUCKET=""
REGION=$(tf_get aws_region)                 || REGION=""

# RDS endpoint via AWS API (dev IAM has rds:DescribeDBInstances).
if [[ -z "$RDS_HOST" || -z "$RDS_PORT" ]]; then
  info "Reading RDS endpoint from AWS API (no terraform state on this machine)…"
  RDS_JSON=$(aws --profile "$AWS_PROFILE_NAME" rds describe-db-instances \
    --db-instance-identifier "$RDS_INSTANCE_ID_DEFAULT" \
    --query 'DBInstances[0].Endpoint' --output json 2>/dev/null) \
    || err "Cannot find RDS instance '${RDS_INSTANCE_ID_DEFAULT}'. Has terraform been applied?"
  RDS_HOST=$(echo "$RDS_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['Address'])")
  RDS_PORT=$(echo "$RDS_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['Port'])")
  unset RDS_JSON
fi

# Master DB password secret name (deterministic from naming convention).
if [[ -z "$SECRET_NAME" ]]; then
  SECRET_NAME="$SECRET_NAME_DEFAULT"
fi

# AWS region: prefer the dev profile's configured region, fall back to default.
if [[ -z "$REGION" ]]; then
  REGION=$(aws --profile "$AWS_PROFILE_NAME" configure get region 2>/dev/null || echo "")
  [[ -n "$REGION" ]] || REGION="$REGION_DEFAULT"
fi

# S3 bucket name (random hex suffix — not deterministic). Order of preference:
#   1. terraform output (handled above)
#   2. existing AWS_STORAGE_BUCKET_NAME in backend/.env (recovery on a machine
#      that previously ran configure-env.sh successfully)
#   3. ListAllMyBuckets via admin profile (only available during admin recovery)
if [[ -z "$BUCKET" ]]; then
  BUCKET=$(grep -E '^AWS_STORAGE_BUCKET_NAME=' "$ENV_FILE" | head -1 | cut -d= -f2- || true)
fi
if [[ -z "$BUCKET" ]]; then
  if aws --profile "$AWS_PROFILE_ADMIN_NAME" sts get-caller-identity >/dev/null 2>&1; then
    info "Locating S3 media bucket via admin profile…"
    BUCKET=$(aws --profile "$AWS_PROFILE_ADMIN_NAME" s3api list-buckets \
      --query "Buckets[?starts_with(Name, '${NAME_PREFIX_DEFAULT}-media-')].Name | [0]" \
      --output text 2>/dev/null || echo "")
    [[ "$BUCKET" == "None" ]] && BUCKET=""
  fi
fi
if [[ -z "$BUCKET" ]]; then
  err "Cannot locate the S3 media bucket. Without terraform state, you need either:
  • the admin profile (chatpop-dev-admin) configured locally, or
  • a previous AWS_STORAGE_BUCKET_NAME entry in backend/.env
Ask an admin for the exact bucket name (it's chatpop-dev-media-<hex>) and add it
to backend/.env, then rerun this script."
fi

ok "RDS:         ${RDS_HOST}:${RDS_PORT}"
ok "S3 bucket:   ${BUCKET}"
ok "Region:      ${REGION}"

SECRET_JSON=$(aws --profile "$AWS_PROFILE_NAME" secretsmanager get-secret-value \
  --secret-id "$SECRET_NAME" --query 'SecretString' --output text) \
  || err "Failed to fetch RDS master credentials"

DB_USER=$(echo "$SECRET_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['username'])")
DB_PASS=$(echo "$SECRET_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['password'])")
unset SECRET_JSON
ok "Credentials fetched (no values printed)"

# --- Confirm DB exists -----------------------------------------------------

export PATH="/opt/homebrew/opt/libpq/bin:$PATH"
if ! command -v psql >/dev/null 2>&1; then
  err "psql not found. Install with: brew install libpq"
fi

db_exists() {
  local name="$1"
  local result
  result=$(PGPASSWORD="$DB_PASS" psql \
    "host=${RDS_HOST} port=${RDS_PORT} dbname=postgres user=${DB_USER} sslmode=require" \
    -tAc "SELECT 1 FROM pg_database WHERE datname='${name}'" 2>/dev/null || echo "")
  [[ "$result" == "1" ]]
}

db_create_from() {
  local target="$1"
  local source="$2"
  PGPASSWORD="$DB_PASS" psql \
    "host=${RDS_HOST} port=${RDS_PORT} dbname=postgres user=${DB_USER} sslmode=require" \
    -v ON_ERROR_STOP=1 \
    -c "CREATE DATABASE ${target} TEMPLATE ${source};" >/dev/null
}

# Always ensure <dev>_main exists (cloned from dev_seed once, ever).
if ! db_exists "$MAIN_DB"; then
  info "Creating ${MAIN_DB} from dev_seed (first-time setup)"
  db_create_from "$MAIN_DB" "dev_seed"
  ok "Created '${MAIN_DB}'"
else
  ok "'${MAIN_DB}' exists"
fi

# Ensure the current-branch DB exists (cloned from <dev>_main).
if [[ "$DB_NAME" == "$MAIN_DB" ]]; then
  ok "On main branch — using ${MAIN_DB} directly"
elif ! db_exists "$DB_NAME"; then
  info "Creating ${DB_NAME} from ${MAIN_DB} (first time on this branch)"
  db_create_from "$DB_NAME" "$MAIN_DB"
  ok "Created '${DB_NAME}'"
else
  ok "'${DB_NAME}' exists"
fi

# --- S3 prefix sanity check ------------------------------------------------

# Determine which S3 prefix to seed from. For non-main branches, copy from
# this dev's main; for main itself, copy from dev_seed.
if [[ "$BRANCH_SAFE" == "main" ]]; then
  SOURCE_PREFIX="dev_seed"
else
  SOURCE_PREFIX="${DEV_NAME}/main"
fi

if aws --profile "$AWS_PROFILE_NAME" s3 ls "s3://${BUCKET}/${S3_PREFIX}/" 2>/dev/null | head -1 | grep -q .; then
  ok "S3 prefix s3://${BUCKET}/${S3_PREFIX}/ already populated"
else
  info "Syncing s3://${BUCKET}/${SOURCE_PREFIX}/ → s3://${BUCKET}/${S3_PREFIX}/"
  aws --profile "$AWS_PROFILE_NAME" s3 sync \
    "s3://${BUCKET}/${SOURCE_PREFIX}/" "s3://${BUCKET}/${S3_PREFIX}/" --no-progress >/dev/null
  ok "Synced media to s3://${BUCKET}/${S3_PREFIX}/"
fi

# --- Write .env ------------------------------------------------------------

info "Updating ${ENV_FILE}"

# Use Python for safe in-place updating (handles arbitrary password chars).
DB_PASS="$DB_PASS" \
DB_NAME="$DB_NAME" \
DB_USER="$DB_USER" \
RDS_HOST="$RDS_HOST" \
RDS_PORT="$RDS_PORT" \
BUCKET="$BUCKET" \
REGION="$REGION" \
S3_PREFIX="$S3_PREFIX" \
AWS_PROFILE_NAME="$AWS_PROFILE_NAME" \
ENV_FILE="$ENV_FILE" \
python3 - <<'PYEOF'
import os, re
from pathlib import Path

updates = {
    "POSTGRES_DB":            os.environ["DB_NAME"],
    "POSTGRES_USER":          os.environ["DB_USER"],
    "POSTGRES_PASSWORD":      os.environ["DB_PASS"],
    "POSTGRES_HOST":          os.environ["RDS_HOST"],
    "POSTGRES_PORT":          os.environ["RDS_PORT"],
    "POSTGRES_SSLMODE":       "require",
    "AWS_PROFILE":            os.environ["AWS_PROFILE_NAME"],
    "AWS_STORAGE_BUCKET_NAME": os.environ["BUCKET"],
    "AWS_S3_REGION_NAME":     os.environ["REGION"],
    "AWS_LOCATION":           os.environ["S3_PREFIX"],
}

# Legacy keys to strip outright. boto3 falls through to AWS_PROFILE when
# these env vars are absent, which is what we want — having them present
# (even empty) is just noise, and any real values in them would override
# the profile.
deletions = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]

env_path = Path(os.environ["ENV_FILE"])
content = env_path.read_text()

for key in deletions:
    # Match the line + trailing newline so the file doesn't grow blank lines.
    pattern = re.compile(rf"^{re.escape(key)}=.*\n?", re.MULTILINE)
    content = pattern.sub("", content)

for key, val in updates.items():
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    new_line = f"{key}={val}"
    if pattern.search(content):
        # Use a callable to avoid backref interpretation of '\' or '&' in val
        content = pattern.sub(lambda _m, _l=new_line: _l, content)
    else:
        if not content.endswith("\n"):
            content += "\n"
        content += new_line + "\n"

env_path.write_text(content)
PYEOF

unset DB_PASS PGPASSWORD

ok "Updated ${ENV_FILE} (other settings preserved)"

cat <<EOF

${GREEN}${BOLD}✓ Configured for AWS.${NC}

Backend now points at:
  Postgres:   ${RDS_HOST}:${RDS_PORT}/${DB_NAME}
  S3 bucket:  s3://${BUCKET}/${S3_PREFIX}/
  AWS profile: ${AWS_PROFILE_NAME}

Restart Daphne to pick up the new config:
  lsof -ti:9000 | xargs kill 2>/dev/null
  cd backend && ./venv/bin/daphne -e ssl:9000:privateKey=../certs/localhost+3-key.pem:certKey=../certs/localhost+3.pem -b 0.0.0.0 chatpop.asgi:application

EOF
