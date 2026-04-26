#!/usr/bin/env bash
# ChatPop Tailscale bootstrap
#
# Walks you through installing Tailscale, signing in, and capturing a
# reusable auth key for the EC2 subnet router that bridges your laptop
# into the AWS VPC.
#
# Outcome: infra/terraform/secrets.auto.tfvars contains your auth key.
# Terraform auto-loads *.auto.tfvars so subsequent plan/apply commands
# pick it up with no flags.
#
# This script is one-shot and idempotent. Re-running it asks before
# overwriting an existing key file.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="${SCRIPT_DIR}/terraform"
SECRETS_FILE="${TF_DIR}/secrets.auto.tfvars"
KEY_PREFIX="tskey-auth-"
KEYS_PAGE="https://login.tailscale.com/admin/settings/keys"

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

printf "${BOLD}ChatPop Tailscale bootstrap${NC}\n"
printf "===========================\n\n"

# --- Step 1: Install Tailscale ---------------------------------------------

info "Step 1 — Tailscale installation"

if [[ -d "/Applications/Tailscale.app" ]] || command -v tailscale >/dev/null 2>&1; then
  ok "Tailscale is already installed."
else
  warn "Tailscale not detected."
  if ! command -v brew >/dev/null 2>&1; then
    err "Homebrew not installed. Install Tailscale manually from https://tailscale.com/download/mac"
  fi
  read -p "Install Tailscale via Homebrew now? [y/N] " confirm
  if [[ "${confirm:-}" =~ ^[Yy]$ ]]; then
    brew install --cask tailscale || err "Tailscale install failed."
    ok "Tailscale installed."
  else
    err "Cannot proceed without Tailscale. Install from https://tailscale.com/download/mac"
  fi
fi

# --- Step 2: Sign in ------------------------------------------------------

echo
info "Step 2 — Sign in to Tailscale"

cat <<EOF

  1. Open the Tailscale menu-bar app (Spotlight 'Tailscale', or look for
     the icon in your menu bar — it appears after first launch).
  2. Click the icon, then 'Log in...'.
  3. Sign in with Google, GitHub, Microsoft, email, or any SSO option.
     This auto-creates your personal tailnet (free for up to 3 users).
  4. After login, you'll see this Mac listed as a 'Machine'.

EOF

read -p "Have you signed in to Tailscale on this Mac? [y/N] " confirm
[[ "${confirm:-}" =~ ^[Yy]$ ]] || { info "Re-run when signed in: ${BASH_SOURCE[0]}"; exit 0; }

# Locate the tailscale CLI (it lives inside the .app bundle on macOS).
TAILSCALE_BIN=""
if [[ -x "/Applications/Tailscale.app/Contents/MacOS/Tailscale" ]]; then
  TAILSCALE_BIN="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
elif command -v tailscale >/dev/null 2>&1; then
  TAILSCALE_BIN="$(command -v tailscale)"
fi

if [[ -n "$TAILSCALE_BIN" ]]; then
  if STATUS_OUT=$("$TAILSCALE_BIN" status 2>&1); then
    ok "Tailscale is running."
    echo "$STATUS_OUT" | head -3 | sed 's/^/    /'
  else
    warn "Tailscale CLI found but status check failed — sign-in may be incomplete."
    echo "$STATUS_OUT" | head -3 | sed 's/^/    /'
  fi
fi

# --- Step 3: Generate auth key --------------------------------------------

echo
info "Step 3 — Generate auth key for the EC2 router"

cat <<EOF

  Open: ${KEYS_PAGE}

  1. Click 'Generate auth key...'.
  2. Settings:
       ${GREEN}✓${NC} Reusable        (so we can re-create the EC2 if needed)
       ${GREEN}✓${NC} Pre-approved    (so the EC2 auto-joins without manual approval)
         Ephemeral       — leave OFF
         Expiration      — 90 days is fine; rotate as needed
         Tags            — leave empty for now
  3. Click 'Generate key'.
  4. Copy the key. It starts with '${KEY_PREFIX}' and is shown only once.

EOF

if command -v open >/dev/null 2>&1; then
  read -p "Open the Tailscale keys page in your browser now? [Y/n] " confirm
  if [[ ! "${confirm:-}" =~ ^[Nn]$ ]]; then
    open "${KEYS_PAGE}"
  fi
fi

echo
read -p "Have you generated the key and copied it? [y/N] " confirm
[[ "${confirm:-}" =~ ^[Yy]$ ]] || { info "Re-run when ready."; exit 0; }

# --- Step 4: Idempotency check --------------------------------------------

if [[ -f "$SECRETS_FILE" ]]; then
  warn "An existing secrets file was found:"
  echo "    $SECRETS_FILE"
  read -p "Overwrite? [y/N] " confirm
  [[ "${confirm:-}" =~ ^[Yy]$ ]] || { ok "Keeping existing secrets file. Done."; exit 0; }
fi

# --- Step 5: Capture key (silent input) -----------------------------------

echo
info "Step 4 — Save key to ${SECRETS_FILE}"
echo
warn "DO NOT share or paste your terminal output anywhere after this point."
warn "Exposed Tailscale auth keys must be revoked at ${KEYS_PAGE}."
echo

# -s = silent: input never echoes to terminal
read -r -s -p "Tailscale auth key (input hidden): " AUTH_KEY
echo
[[ -n "$AUTH_KEY" ]] || err "Auth key cannot be empty."

if [[ ! "$AUTH_KEY" =~ ^${KEY_PREFIX} ]]; then
  warn "Key does not start with '${KEY_PREFIX}'. Did you copy the wrong value?"
  read -p "Continue anyway? [y/N] " confirm
  [[ "${confirm:-}" =~ ^[Yy]$ ]] || { unset AUTH_KEY; err "Aborted."; }
fi

mkdir -p "$TF_DIR"

# Write with restrictive perms from the start
umask 0077
cat > "$SECRETS_FILE" <<EOF
# Auto-generated by infra/bootstrap-tailscale.sh
# DO NOT commit. Gitignored via *.tfvars rule in infra/terraform/.gitignore.
# To rotate: re-run ./infra/bootstrap-tailscale.sh

tailscale_auth_key = "${AUTH_KEY}"
EOF
chmod 600 "$SECRETS_FILE"

# Scrub from script's environment immediately
unset AUTH_KEY

ok "Key saved to ${SECRETS_FILE} (chmod 600)."

# Verify gitignore status (only if inside a git repo)
if (cd "$TF_DIR" && git rev-parse --git-dir >/dev/null 2>&1); then
  if (cd "$TF_DIR" && git check-ignore secrets.auto.tfvars >/dev/null 2>&1); then
    ok "Confirmed: secrets file is gitignored."
  else
    warn "WARNING: ${SECRETS_FILE} does NOT appear to be gitignored."
    warn "Check infra/terraform/.gitignore for a *.tfvars rule."
  fi
fi

# --- Done -----------------------------------------------------------------

cat <<EOF

${GREEN}${BOLD}✓ Tailscale bootstrap complete.${NC}

  Key file:     ${SECRETS_FILE}
  Permissions:  600 (owner read/write only)
  Auto-load:    Yes — terraform reads *.auto.tfvars on every plan/apply.

${YELLOW}${BOLD}IMPORTANT:${NC} Do not paste this terminal output anywhere — including
to AI assistants or chat tools. The auth key was hidden during input, but
treat the file path itself as sensitive.

To rotate the key later: re-run this script. To revoke an existing key:
visit ${KEYS_PAGE}.

Next: terraform plan + apply for the network, EC2 router, and RDS.

EOF
