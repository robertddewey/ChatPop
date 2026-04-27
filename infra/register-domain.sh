#!/usr/bin/env bash
# Register a domain via AWS Route 53 Domains.
#
# One-time admin operation. Walks you through:
#   1. Confirms the domain is available
#   2. Shows current pricing (registration + renewal)
#   3. Prompts for ICANN-required contact info (validated)
#   4. Final review screen
#   5. Submits the registration ($$$ — explicit confirmation required)
#   6. Polls until AWS reports completion
#   7. Verifies the domain + auto-created hosted zone
#   8. Reminds you about the ICANN verification email
#
# Usage:
#   infra/register-domain.sh <domain>
# Example:
#   infra/register-domain.sh chatmie.com
#
# Requires the chatpop-dev-admin AWS profile.

set -euo pipefail

DOMAIN="${1:-}"
[[ -n "$DOMAIN" ]] || { echo "Usage: $0 <domain>"; exit 1; }

AWS_PROFILE_ADMIN="chatpop-dev-admin"
CONTACT_FILE="$(mktemp -t "$(echo "$DOMAIN" | tr '.' '-')-contact.XXXXXX.json")"

# Always remove the contact file on exit — it has your address + phone.
trap 'rm -f "$CONTACT_FILE"' EXIT

# --- Color helpers ---------------------------------------------------------
RED=$'\033[0;31m'; GREEN=$'\033[0;32m'; YELLOW=$'\033[1;33m'; BLUE=$'\033[0;34m'
BOLD=$'\033[1m';   DIM=$'\033[2m';     NC=$'\033[0m'

err()  { printf "${RED}error:${NC} %s\n" "$*" >&2; exit 1; }
ok()   { printf "${GREEN}✓${NC} %s\n" "$*"; }
info() { printf "${BLUE}→${NC} %s\n" "$*"; }
warn() { printf "${YELLOW}!${NC} %s\n" "$*"; }
hdr()  { printf "\n${BOLD}%s${NC}\n" "$*"; }

# --- Preflight -------------------------------------------------------------
aws --profile "$AWS_PROFILE_ADMIN" sts get-caller-identity >/dev/null 2>&1 \
  || err "Admin profile '$AWS_PROFILE_ADMIN' not configured. Run: chatpop bootstrap aws"

# --- Step 1: availability --------------------------------------------------
hdr "Step 1 — Verify availability"
AVAIL=$(aws --profile "$AWS_PROFILE_ADMIN" route53domains check-domain-availability \
  --domain-name "$DOMAIN" --query Availability --output text)
[[ "$AVAIL" == "AVAILABLE" ]] || err "$DOMAIN status: $AVAIL"
ok "$DOMAIN is AVAILABLE"

# --- Step 2: pricing -------------------------------------------------------
hdr "Step 2 — Pricing"
TLD="${DOMAIN##*.}"
PRICE=$(aws --profile "$AWS_PROFILE_ADMIN" route53domains list-prices --tld "$TLD" \
  --query 'Prices[0].RegistrationPrice.Price' --output text)
RENEWAL=$(aws --profile "$AWS_PROFILE_ADMIN" route53domains list-prices --tld "$TLD" \
  --query 'Prices[0].RenewalPrice.Price' --output text)
ok "Registration:  \$${PRICE} for 1 year"
ok "Renewal:       \$${RENEWAL}/year (auto-renew will be enabled)"

# --- Step 3: contact info --------------------------------------------------
hdr "Step 3 — Contact info"
info "ICANN requires real contact details. Privacy protection will be"
info "enabled (free), so this info is hidden from public WHOIS via the"
info "Route 53 proxy. AWS still has it for verification + emergency contact."
echo
info "Press Ctrl-C any time to abort. Nothing is purchased until Step 5."
echo

read -r -p "  First name:                    " FIRST
read -r -p "  Last name:                     " LAST
read -r -p "  Street address:                " STREET
read -r -p "  City:                          " CITY
read -r -p "  State (2-letter, e.g. CA):     " STATE
read -r -p "  ZIP:                           " ZIP
read -r -p "  Phone (US, any format):        " PHONE
read -r -p "  Email:                         " EMAIL

# --- Validate inputs -------------------------------------------------------
[[ -n "$FIRST" && -n "$LAST" && -n "$STREET" && -n "$CITY" && -n "$ZIP" && -n "$EMAIL" ]] \
  || err "All fields are required."

STATE_UC=$(echo "$STATE" | tr '[:lower:]' '[:upper:]')
[[ "$STATE_UC" =~ ^[A-Z]{2}$ ]] \
  || err "State must be 2 letters (e.g., CA, NY, TX). Got: '$STATE'"

# Normalize phone to AWS's required +1.XXXXXXXXXX format.
# Accepts any common US notation: 254-459-2833, (254) 459-2833, 2544592833,
# +1 254 459 2833, etc. Strips everything except digits, then reformats.
PHONE_DIGITS=$(echo "$PHONE" | tr -cd '[:digit:]')
case "${#PHONE_DIGITS}" in
  10) PHONE="+1.${PHONE_DIGITS}" ;;
  11) [[ "${PHONE_DIGITS:0:1}" == "1" ]] \
        || err "11-digit phone must start with US country code 1. Got: '$PHONE'"
      PHONE="+1.${PHONE_DIGITS:1}" ;;
   *) err "Phone must contain 10 US digits (with or without country code). Got ${#PHONE_DIGITS} digits in: '$PHONE'" ;;
esac

[[ "$EMAIL" =~ ^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$ ]] \
  || err "Email looks invalid. Got: '$EMAIL'"

# --- Step 4: write contact file --------------------------------------------
# Use Python for safe JSON encoding (handles quotes, special chars in addresses).
FIRST="$FIRST" LAST="$LAST" STREET="$STREET" CITY="$CITY" STATE="$STATE_UC" \
ZIP="$ZIP" PHONE="$PHONE" EMAIL="$EMAIL" CONTACT_FILE="$CONTACT_FILE" \
python3 -c '
import json, os
contact = {
    "ContactType":  "PERSON",
    "FirstName":    os.environ["FIRST"],
    "LastName":     os.environ["LAST"],
    "AddressLine1": os.environ["STREET"],
    "City":         os.environ["CITY"],
    "State":        os.environ["STATE"],
    "CountryCode":  "US",
    "ZipCode":      os.environ["ZIP"],
    "PhoneNumber":  os.environ["PHONE"],
    "Email":        os.environ["EMAIL"],
}
with open(os.environ["CONTACT_FILE"], "w") as f:
    json.dump(contact, f, indent=2)
'
chmod 600 "$CONTACT_FILE"

# --- Step 5: review + confirm ----------------------------------------------
hdr "Step 5 — Review"
ok "Domain:    ${DOMAIN}"
ok "Cost:      \$${PRICE} now, \$${RENEWAL}/year going forward (auto-renew ON)"
ok "Contact:   $FIRST $LAST <$EMAIL>"
ok "Address:   $STREET, $CITY, $STATE_UC $ZIP, US"
ok "Phone:     $PHONE"
ok "Privacy:   ON (free; hides above from public WHOIS)"
echo
warn "About to charge \$${PRICE} to your AWS bill. This is irreversible."
warn "Refunds for misclicks aren't a thing in domain registration."
echo
read -r -p "  Type 'yes' to register (anything else aborts): " CONFIRM
[[ "$CONFIRM" == "yes" ]] || { echo "Aborted. No charge."; exit 0; }

# --- Step 6: register ------------------------------------------------------
hdr "Step 6 — Submit registration"
RESULT=$(aws --profile "$AWS_PROFILE_ADMIN" route53domains register-domain \
  --domain-name "$DOMAIN" \
  --duration-in-years 1 \
  --auto-renew \
  --admin-contact      "file://$CONTACT_FILE" \
  --registrant-contact "file://$CONTACT_FILE" \
  --tech-contact       "file://$CONTACT_FILE" \
  --privacy-protect-admin-contact \
  --privacy-protect-registrant-contact \
  --privacy-protect-tech-contact 2>&1) \
  || err "register-domain failed: $RESULT"

OPERATION_ID=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['OperationId'])")
ok "Submitted. Operation ID: $OPERATION_ID"

# --- Step 7: poll ----------------------------------------------------------
hdr "Step 7 — Wait for completion (typical: 5-15 min for .com)"
ELAPSED=0
while true; do
  STATUS=$(aws --profile "$AWS_PROFILE_ADMIN" route53domains get-operation-detail \
    --operation-id "$OPERATION_ID" --query Status --output text)
  case "$STATUS" in
    SUCCESSFUL)
      ok "Registration complete! (after ${ELAPSED}s)"
      break
      ;;
    FAILED|ERROR)
      MSG=$(aws --profile "$AWS_PROFILE_ADMIN" route53domains get-operation-detail \
        --operation-id "$OPERATION_ID" --query Message --output text)
      err "Registration failed: $MSG"
      ;;
    *)
      info "Status: $STATUS — checking again in 30s… (${ELAPSED}s elapsed)"
      sleep 30
      ELAPSED=$((ELAPSED + 30))
      ;;
  esac
done

# --- Step 8: verify --------------------------------------------------------
hdr "Step 8 — Verify"
aws --profile "$AWS_PROFILE_ADMIN" route53domains list-domains \
  --query "Domains[?DomainName=='${DOMAIN}']" --output table

HZ=$(aws --profile "$AWS_PROFILE_ADMIN" route53 list-hosted-zones-by-name \
  --dns-name "${DOMAIN}." \
  --query "HostedZones[?Name=='${DOMAIN}.']|[0].Id" --output text 2>/dev/null || echo "")
if [[ -n "$HZ" && "$HZ" != "None" ]]; then
  ok "Hosted zone: $HZ"
else
  warn "Hosted zone not found yet (sometimes lags by a minute or two)."
fi

# --- Step 9: ICANN reminder ------------------------------------------------
echo
printf "${YELLOW}${BOLD}IMPORTANT — check your email NOW${NC}\n"
printf "ICANN sends a verification link to ${BOLD}${EMAIL}${NC} from\n"
printf "${BOLD}noreply@registrar.amazon.com${NC} within minutes of registration.\n"
printf "Click the link within ${BOLD}15 days${NC} or the domain auto-suspends.\n"
echo
ok "Done. Domain is yours."
info "Next: ping Claude to write the CloudFront / ACM / Route 53 alias terraform."
