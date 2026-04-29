#!/usr/bin/env bash
# ChatMie AWS bootstrap (path b: console-then-profile-config)
#
# Configures a local AWS CLI profile named "chatmie-dev-admin" using
# credentials you generate in the AWS Console for the IAM user
# "chatmie-dev-deploy" (AdministratorAccess).
#
# This is for the FIRST-TIME ADMIN setting up cloud infrastructure. Other
# developers (joiners) get scoped per-developer keys and use chatpop join.
#
# This script is one-shot. After it succeeds, it has no further role.
# All subsequent infra work uses Terraform under infra/terraform/.

set -euo pipefail

PROFILE="chatmie-dev-admin"
EXPECTED_ACCOUNT="090719695164"
EXPECTED_USER_NAME="chatmie-dev-deploy"
DEFAULT_REGION="us-east-1"

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

printf "${BOLD}ChatMie AWS bootstrap${NC}\n"
printf "=====================\n\n"

# --- Preflight -------------------------------------------------------------

command -v aws >/dev/null 2>&1 || err "aws CLI not installed (brew install awscli)"
ok "aws CLI: $(aws --version 2>&1 | awk '{print $1}')"

# --- Idempotency check -----------------------------------------------------

if aws configure list --profile "$PROFILE" >/dev/null 2>&1; then
  if CURRENT=$(aws --profile "$PROFILE" sts get-caller-identity --output json 2>/dev/null); then
    warn "Profile '$PROFILE' already exists and is functional:"
    echo "$CURRENT" | python3 -m json.tool | sed 's/^/    /'
    read -p "Reconfigure? [y/N] " confirm
    [[ "${confirm:-}" =~ ^[Yy]$ ]] || { ok "Keeping existing profile."; exit 0; }
  fi
fi

# --- Console instructions --------------------------------------------------

cat <<EOF

${BOLD}Step 1 — Create the IAM user in the AWS Console${NC}

Open https://console.aws.amazon.com/iam/home#/users in a browser, signed in
to account ${EXPECTED_ACCOUNT} (appsandbox).

  1. Click 'Create user'.
  2. User name: ${EXPECTED_USER_NAME}
  3. Skip 'Provide user access to the AWS Management Console' (we don't need it).
  4. Click Next.
  5. Permissions options: 'Attach policies directly'.
  6. Search for and check: AdministratorAccess
     (Temporary — we'll scope this down once we know what resources we need.)
  7. Click Next, then Create user.

${BOLD}Step 2 — Generate an access key for that user${NC}

  8.  Click on the user '${EXPECTED_USER_NAME}'.
  9.  Click the 'Security credentials' tab.
  10. Under 'Access keys', click 'Create access key'.
  11. Choose 'Command Line Interface (CLI)', acknowledge the recommendation, click Next.
  12. (Optional) Description tag: "chatmie-dev-admin local bootstrap"
  13. Click 'Create access key'.
  14. KEEP THIS PAGE OPEN. You'll need:
        - Access key ID
        - Secret access key
      The Secret is only shown once.

EOF

read -p "Have you completed steps 1–14 and have the keys ready? [y/N] " confirm
[[ "${confirm:-}" =~ ^[Yy]$ ]] || { info "Re-run when ready: ./infra/bootstrap.sh"; exit 0; }

# --- Configure the profile -------------------------------------------------
#
# We deliberately avoid `aws configure` (interactive) because pasting the
# secret into its prompt can echo to the terminal scrollback. Instead we
# read the secret with `read -s` (no echo) and write directly via
# `aws configure set`. The secret never appears in your terminal output.

echo
warn "DO NOT share or paste your terminal output anywhere after this point."
warn "Even if you trust the recipient, exposed keys must be rotated. No exceptions."
echo
info "Configuring profile '${PROFILE}'."
echo

read -r -p "AWS Access Key ID: " AWS_KEY
[[ -n "$AWS_KEY" ]] || err "Access key ID cannot be empty."

# -s = silent (no echo). The secret is never displayed.
read -r -s -p "AWS Secret Access Key (input hidden): " AWS_SECRET
echo
[[ -n "$AWS_SECRET" ]] || err "Secret access key cannot be empty."

aws configure set aws_access_key_id     "$AWS_KEY"        --profile "$PROFILE"
aws configure set aws_secret_access_key "$AWS_SECRET"     --profile "$PROFILE"
aws configure set region                "$DEFAULT_REGION" --profile "$PROFILE"
aws configure set output                json              --profile "$PROFILE"

# Scrub from this script's environment immediately
unset AWS_KEY AWS_SECRET

# --- Verify ----------------------------------------------------------------

echo
info "Verifying credentials..."

CALLER=$(aws --profile "$PROFILE" sts get-caller-identity --output json) \
  || err "sts get-caller-identity failed. Re-check the access key/secret you pasted."

ACCOUNT_ID=$(echo "$CALLER" | python3 -c "import sys,json; print(json.load(sys.stdin)['Account'])")
USER_ARN=$(echo "$CALLER"   | python3 -c "import sys,json; print(json.load(sys.stdin)['Arn'])")

ok "Authenticated as: $USER_ARN"
ok "Account ID:       $ACCOUNT_ID"
ok "Region:           $(aws configure get region --profile "$PROFILE")"

[[ "$ACCOUNT_ID" == "$EXPECTED_ACCOUNT" ]] \
  || warn "Account ID '$ACCOUNT_ID' does not match expected '$EXPECTED_ACCOUNT'. Verify you used the right keys."

[[ "$USER_ARN" == *"user/${EXPECTED_USER_NAME}"* ]] \
  || warn "ARN does not look like the ${EXPECTED_USER_NAME} user. Verify."

cat <<EOF

${GREEN}${BOLD}✓ Bootstrap complete.${NC}

Profile '${PROFILE}' is configured at ~/.aws/credentials and ~/.aws/config.
This is the ADMIN profile (chatpop-dev-deploy keys with AdministratorAccess).
Used by terraform and chatpop admin operations.

  Test:        aws --profile ${PROFILE} sts get-caller-identity
  Terraform:   uses var.aws_profile = "${PROFILE}" by default

After 'terraform apply', run 'chatpop admin add <your-name>' followed by
'chatpop admin install-dev-keys <your-name>' to set up your developer
profile (chatpop-dev) for daily work.

${YELLOW}${BOLD}IMPORTANT:${NC} Do not paste this terminal output anywhere — including
to AI assistants or chat tools. Even though the secret was hidden during
input, your access key ID is sensitive when paired with the secret. If this
output is exposed, rotate the key in the IAM console immediately.

Next: Terraform foundation (infra/terraform/).

EOF
