#!/usr/bin/env bash
# ChatPop dev_seed bootstrap from local state.
#
# Takes your local Postgres database and backend/media/ contents and uses
# them as the canonical "dev_seed" starting point on AWS:
#
#   1. Drops and recreates the RDS database `dev_seed`.
#   2. pg_dumps your local chatpop DB and restores it into RDS.
#   3. Confirms pgvector is enabled.
#   4. Syncs backend/media/ to s3://<media-bucket>/dev_seed/.
#
# Idempotent: re-runnable any time. Safe to run while servers are stopped;
# DO NOT run while Daphne is talking to dev_seed (it will be dropped).

set -euo pipefail

# --- Config ----------------------------------------------------------------

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AWS_PROFILE_NAME="chatpop-dev"
TF_DIR="${PROJECT_ROOT}/infra/terraform"

LOCAL_PG_CONTAINER="chatpop_postgres"
LOCAL_PG_USER="chatpop_user"
LOCAL_PG_DB="chatpop"

LIBPQ_PATH="/opt/homebrew/opt/libpq/bin"

# --- Colors ----------------------------------------------------------------

RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[1;33m'
BLUE=$'\033[0;34m'
BOLD=$'\033[1m'
NC=$'\033[0m'

err()  { printf "${RED}error:${NC} %s\n" "$*" >&2; exit 1; }
ok()   { printf "${GREEN}✓${NC} %s\n" "$*"; }
info() { printf "${BLUE}→${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}!${NC} %s\n" "$*"; }

printf "${BOLD}ChatPop dev_seed bootstrap from local${NC}\n"
printf "=====================================\n\n"

# --- Preflight -------------------------------------------------------------

info "Preflight checks"

# libpq client tools
if [[ -d "$LIBPQ_PATH" ]]; then
  export PATH="$LIBPQ_PATH:$PATH"
fi
command -v psql >/dev/null 2>&1 || err "psql not found. Install with: brew install libpq"
ok "psql:        $(psql --version | awk '{print $3}')"

# Docker + local Postgres
docker ps --format '{{.Names}}' | grep -q "^${LOCAL_PG_CONTAINER}\$" \
  || err "Local Postgres container '${LOCAL_PG_CONTAINER}' not running. Start with: docker-compose up -d"
ok "local PG:    container '${LOCAL_PG_CONTAINER}' is running"

# AWS profile
aws --profile "$AWS_PROFILE_NAME" sts get-caller-identity >/dev/null 2>&1 \
  || err "AWS profile '${AWS_PROFILE_NAME}' not working. Re-run infra/bootstrap.sh."
ok "AWS:         profile '${AWS_PROFILE_NAME}' authenticated"

# Pull terraform outputs
cd "$TF_DIR"
RDS_HOST=$(terraform output -raw rds_address 2>/dev/null)        || err "Cannot read rds_address from terraform output. Run terraform apply first."
RDS_PORT=$(terraform output -raw rds_port 2>/dev/null)           || err "Cannot read rds_port."
RDS_DB=$(terraform output -raw rds_initial_database 2>/dev/null) || err "Cannot read rds_initial_database."
SECRET_NAME=$(terraform output -raw rds_master_secret_name 2>/dev/null) || err "Cannot read rds_master_secret_name."
MEDIA_BUCKET=$(terraform output -raw media_bucket_name 2>/dev/null) || err "Cannot read media_bucket_name."
cd - >/dev/null

ok "RDS:         ${RDS_HOST}:${RDS_PORT} db=${RDS_DB}"
ok "S3 bucket:   ${MEDIA_BUCKET}"

# Pull RDS master credentials
SECRET_JSON=$(aws --profile "$AWS_PROFILE_NAME" secretsmanager get-secret-value \
  --secret-id "$SECRET_NAME" --query 'SecretString' --output text) \
  || err "Failed to fetch RDS master credentials."

RDS_USER=$(echo "$SECRET_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['username'])")
RDS_PASS=$(echo "$SECRET_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['password'])")
unset SECRET_JSON
ok "credentials: fetched (user=${RDS_USER}, password length=${#RDS_PASS})"

# TCP probe
nc -zv -G 5 "$RDS_HOST" "$RDS_PORT" >/dev/null 2>&1 \
  || err "Cannot reach ${RDS_HOST}:${RDS_PORT}. Is Tailscale connected and the subnet route approved?"
ok "Tailscale:   RDS reachable on port ${RDS_PORT}"

# --- Confirmation ----------------------------------------------------------

cat <<EOF

${BOLD}This will:${NC}
  - DROP and recreate database '${RDS_DB}' on RDS (${RDS_HOST})
  - pg_dump your local '${LOCAL_PG_DB}' database (~14MB)
  - Restore the dump into '${RDS_DB}' on RDS
  - Verify pgvector is available
  - Sync backend/media/ to s3://${MEDIA_BUCKET}/dev_seed/

EOF

read -p "Continue? [y/N] " confirm
[[ "${confirm:-}" =~ ^[Yy]$ ]] || { info "Aborted."; exit 0; }

# --- Drop and recreate dev_seed -------------------------------------------

echo
info "Drop and recreate '${RDS_DB}' on RDS"

# Connect to the postgres maintenance DB to drop/create dev_seed.
# RDS hostname always has a 'postgres' DB available.
PGPASSWORD="$RDS_PASS" psql \
  "host=${RDS_HOST} port=${RDS_PORT} dbname=postgres user=${RDS_USER} sslmode=require" \
  -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS ${RDS_DB} WITH (FORCE);" \
  -c "CREATE DATABASE ${RDS_DB};" \
  >/dev/null

ok "Recreated '${RDS_DB}'."

# --- Enable pgvector before restore ---------------------------------------

info "Enable pgvector on '${RDS_DB}'"

PGPASSWORD="$RDS_PASS" psql \
  "host=${RDS_HOST} port=${RDS_PORT} dbname=${RDS_DB} user=${RDS_USER} sslmode=require" \
  -v ON_ERROR_STOP=1 \
  -c "CREATE EXTENSION IF NOT EXISTS vector;" \
  -c "SELECT extname, extversion FROM pg_extension WHERE extname='vector';"

ok "pgvector enabled."

# --- Dump local + pipe to RDS ---------------------------------------------

info "Dump local '${LOCAL_PG_DB}' and restore into '${RDS_DB}' on RDS"
echo "    (this can take 30-60 seconds for ~14MB)"

# pg_dump runs inside the container (matched 16.13 client/server).
# --no-owner / --no-acl: strip ownership and grants so everything ends up
#                        owned by chatpop_admin on RDS.
# --quote-all-identifiers: defensive against name collisions.
# We pipe stdout straight into psql to avoid writing the dump to disk.

start_time=$(date +%s)

if ! docker exec "$LOCAL_PG_CONTAINER" pg_dump \
       --username "$LOCAL_PG_USER" \
       --no-owner --no-acl \
       --quote-all-identifiers \
       "$LOCAL_PG_DB" 2>/dev/null \
   | PGPASSWORD="$RDS_PASS" psql \
       "host=${RDS_HOST} port=${RDS_PORT} dbname=${RDS_DB} user=${RDS_USER} sslmode=require" \
       -v ON_ERROR_STOP=1 \
       --quiet \
       >/dev/null; then
  err "Dump/restore failed. Check the connection and credentials."
fi

elapsed=$(( $(date +%s) - start_time ))
ok "Restored in ${elapsed}s."

# --- Verify ---------------------------------------------------------------

info "Verify schema in RDS"

VERIFY_SQL="
SELECT
  (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public') AS tables,
  (SELECT COUNT(*) FROM django_migrations) AS migrations,
  (SELECT COUNT(*) FROM chats_chattheme) AS themes,
  (SELECT COUNT(*) FROM chats_giftcatalogitem) AS gifts;
"

PGPASSWORD="$RDS_PASS" psql \
  "host=${RDS_HOST} port=${RDS_PORT} dbname=${RDS_DB} user=${RDS_USER} sslmode=require" \
  -v ON_ERROR_STOP=1 \
  -c "$VERIFY_SQL"

# --- Sync media to S3 -----------------------------------------------------

echo
info "Sync backend/media/ to s3://${MEDIA_BUCKET}/dev_seed/"

if [[ ! -d "${PROJECT_ROOT}/backend/media" ]]; then
  warn "backend/media/ does not exist; skipping media sync."
else
  start_time=$(date +%s)
  aws --profile "$AWS_PROFILE_NAME" s3 sync \
    "${PROJECT_ROOT}/backend/media/" "s3://${MEDIA_BUCKET}/dev_seed/" \
    --no-progress
  elapsed=$(( $(date +%s) - start_time ))

  OBJECT_COUNT=$(aws --profile "$AWS_PROFILE_NAME" s3 ls "s3://${MEDIA_BUCKET}/dev_seed/" --recursive | wc -l | tr -d ' ')
  ok "Synced ${OBJECT_COUNT} objects in ${elapsed}s."
fi

# --- Cleanup --------------------------------------------------------------

unset RDS_PASS PGPASSWORD

cat <<EOF

${GREEN}${BOLD}✓ dev_seed bootstrap complete.${NC}

  RDS database:   ${RDS_DB} on ${RDS_HOST}
  S3 prefix:      s3://${MEDIA_BUCKET}/dev_seed/

The dev_seed is now the team's canonical starting point. Future:
  - Per-developer DBs are cloned via 'CREATE DATABASE <dev>_main TEMPLATE ${RDS_DB};'
  - Per-developer media starts as 'aws s3 sync s3://${MEDIA_BUCKET}/dev_seed/ s3://${MEDIA_BUCKET}/<dev>/'

Re-run this script any time you want to refresh dev_seed from your local
state (e.g., after seeding new test data locally).

EOF
