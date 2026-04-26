# Cloud Development

ChatPop's development environment runs against AWS RDS (Postgres) and S3 (media), connected via Tailscale. This document covers the workflows for everyday use, onboarding new developers, admin operations, and managing shared secrets.

For the high-level architecture and decisions ("why these tools?"), see [CLAUDE.md](../CLAUDE.md). For getting started, see the [README](../README.md).

---

## Table of contents

- [Architecture](#architecture)
- [Daily workflow](#daily-workflow)
- [The `chatpop` CLI](#the-chatpop-cli)
- [First-dev infrastructure setup](#first-dev-infrastructure-setup)
- [Joining an existing team](#joining-an-existing-team)
- [Admin operations — managing the team roster](#admin-operations--managing-the-team-roster)
- [Shared API keys (Secrets Manager)](#shared-api-keys-secrets-manager)
- [CI / GitHub Actions](#ci--github-actions)
- [Cost](#cost)

---

## Architecture

```
laptop ── Tailscale tunnel ──> EC2 subnet router ──> VPC ──> RDS Postgres
                                                       └──> S3 (media)
```

- **No public RDS endpoint.** Connection is via Tailscale through a tiny EC2 router in the VPC.
- **Per-developer isolation:** databases and S3 prefixes are namespaced as `<dev>_<branch>` / `<dev>/<branch>/`.
- **Per-branch isolation:** every git branch gets its own DB (cloned from `<dev>_main` via Postgres `CREATE DATABASE … TEMPLATE`, ~1-3 seconds) and its own S3 prefix.
- **`dev_seed`** is the canonical clone source — refreshed whenever the team agrees on a known-good baseline.

Cloud-only by design. There is no `use local` toggle. If you need to develop against local Docker (rare; only when AWS is genuinely unreachable), the path requires manual setup outside the standard flow. Daily development assumes Tailscale is up and RDS is reachable.

### Local Docker — Redis only

`docker-compose up -d` starts a single container: `chatpop_redis`. Django needs it for the WebSocket channel layer + cache.

There is **no local Postgres container.** All Postgres data lives on AWS RDS, accessed via Tailscale. Tests run via CI (`.github/workflows/test.yml`) using ephemeral Postgres + pgvector service containers in the runner — not locally.

### Connecting a database client (DBeaver, psql, etc)

`chatpop status` now prints a "Database Connection" section with everything except the password. To plug into DBeaver:

```
Host:      chatpop-dev-postgres.ckbkui2yghxp.us-east-1.rds.amazonaws.com
Port:      5432
Database:  <whichever shows in `chatpop status`>
Username:  chatpop_admin
SSL Mode:  require   (RDS enforces force_ssl=1)
Password:  chatpop password    ← copies to clipboard; paste into DBeaver
```

Tailscale must be up — RDS has no public endpoint. `chatpop check` confirms the tunnel is working before you try DBeaver.

In DBeaver, you can either create one connection per branch DB or connect to the `postgres` maintenance DB and navigate to whichever you need from the database tree. The chatpop_admin user has full Postgres access (no per-dev role isolation today — see CLAUDE.md), so be careful not to operate on someone else's `<name>_main`.

### Two AWS profiles (least-privilege model)

Every machine has at least one AWS profile; admin machines have both:

| Profile | Keys it holds | Used by |
|---|---|---|
| `chatpop-dev` | `dev-<name>` (scoped per-developer) | Django runtime (boto3), branch hooks (read master DB password, S3 read/write own prefix), most chatpop subcommands |
| `chatpop-dev-admin` | `chatpop-dev-deploy` (AdministratorAccess) | Terraform, `chatpop admin *`, `chatpop seed refresh` |

This means **Django runs with scoped keys**, not admin keys. If the laptop is compromised, the blast radius is the developer's own DBs and S3 prefix — not the whole AWS account.

Non-admin developers (Alice) only have `chatpop-dev`. If they try to run an admin command, they get a clear error: "AWS profile chatpop-dev-admin not configured. This command requires admin credentials."

---

## Daily workflow

Branch operations are automatic via git hooks (`post-checkout`, `post-merge`):

```bash
git checkout -b feat/something
# [hook] cloning robert_main → robert_feat_something
# [hook] s3 sync .../robert/main/ → .../robert/feat_something/
# [hook] backend/.env updated; Daphne killed (restart it)

git pull origin main
# [post-merge] migrate runs if migration files changed
# [post-merge] loaddata runs if fixture files changed
# [post-merge hint] if HEAD is a merge commit and a feature branch was just
#                   merged in, prints a hint about chatpop replace-main

git checkout main
# [hook] .env switches back; Daphne killed

git branch -D feat/something
# Branch deleted; DB+S3 become orphans (cleanup with `chatpop clean`)
```

### Bringing branch data forward after a merge

By design, **per-branch DBs isolate data** — your test rooms / users / messages on `feat/foo` live in `robert_feat_foo`, not in `robert_main`. When you merge `feat/foo` into git main, only the *code and migrations* go through git. The hand-built test data stays on the branch DB.

If you want that data carried forward into `<dev>_main`:

```bash
# After PR merge has hit your local main
git checkout main
git pull
# post-merge hook prints a hint suggesting replace-main if it sees the merge commit
chatpop replace-main feat/foo
# robert_main is now what was robert_feat_foo (data + schema + media).
# robert_feat_foo is preserved; remove with `chatpop clean --apply` after deleting the branch.
```

`chatpop replace-main` is destructive — it requires you to type the target DB name (`<dev>_main`) to confirm. Use only when you specifically want the branch's data to BE your new main.

**Periodic cleanup** of orphan DBs and S3 prefixes for branches you've deleted:

```bash
./bin/chatpop clean              # Dry-run: list orphans
./bin/chatpop clean --apply      # Drop them
```

---

## The `chatpop` CLI

A single entry point at `bin/chatpop` exposes every dev operation as a subcommand. Run with no args from a TTY for an interactive menu.

| Subcommand | Purpose |
|---|---|
| `chatpop status` | Show current dev/branch/DB/S3/services state (passive — reads .env / processes) |
| `chatpop check` | Active health checks: AWS auth, Tailscale, RDS connect, S3 read/write, pgvector, hooks, Daphne response |
| `chatpop password` | Copy RDS Postgres password to clipboard (for DBeaver / psql / etc). `--print` writes to stdout instead. |
| `chatpop join` | Interactive: paste AWS creds + Tailscale sign-in + DB+S3 + hooks (joiner / second machine) |
| `chatpop setup` | Activate hooks only (subset of `join`) |
| `chatpop use cloud [name]` | Configure `backend/.env` for AWS on current branch |
| `chatpop seed refresh` | Rebuild `dev_seed` from current branch's migrations + fixtures (run from `main`) |
| `chatpop replace-main [BRANCH]` | **DESTRUCTIVE.** Replace your `<dev>_main` DB and S3 prefix with a feature branch's contents. Use after merging a feature branch into git main when you want that branch's hand-built test data carried forward into your main. |
| `chatpop fixtures load` | Load `fixtures/*.json` into current branch's DB |
| `chatpop sync-secrets` | Pull team's shared API keys from Secrets Manager into `backend/.env` |
| `chatpop clean [--apply]` | Find/drop orphan branch DBs and S3 prefixes |
| `chatpop admin list` | Show team roster (IAM users + access key IDs) |
| `chatpop admin add <name>` | Provision IAM user `dev-<name>`, print credentials once |
| `chatpop admin remove <name>` | Drop dev's databases + S3 + IAM user (typed confirm) |
| `chatpop admin recover` | Set up admin's machine after a wipe / on a new laptop. Configures BOTH profiles (chatpop-dev-admin + chatpop-dev). |
| `chatpop admin install-dev-keys [name]` | Pull dev-`<name>` keys from terraform state and write to `chatpop-dev` profile. Used during admin recovery and one-shot setups. |
| `chatpop admin set-secret <K>` | Set/update one shared API key (silent input) |
| `chatpop admin list-secrets` | List shared API keys (values masked) |
| `chatpop admin import-env` | One-time: push current `backend/.env` shared keys to Secrets Manager |
| `chatpop bootstrap aws` | Configure admin AWS CLI profile (first dev only) |
| `chatpop bootstrap tailscale` | Capture EC2 router auth key (first dev only) |

`seed refresh` rebuilds `dev_seed` from migrations + fixtures only — clean schema, reference data, no curated test data. Use after merging schema changes; designed to eventually run via GitHub Actions on every push to `main`. (There is no `seed from-local` anymore; local Postgres is no longer part of the dev environment.)

---

## First-dev infrastructure setup

This is **one-time per AWS account** when standing up the cloud environment for the first time. After this, future developers use the joiner flow below.

```bash
./bin/chatpop bootstrap aws          # Configure chatpop-dev-admin profile (admin keys)
./bin/chatpop bootstrap tailscale    # Install Tailscale + capture EC2 router auth key
cd infra/terraform && terraform init && terraform apply
./bin/chatpop admin add <your-name>  # Create per-dev IAM user (yourself)
./bin/chatpop admin install-dev-keys <your-name>  # Install dev keys into chatpop-dev
./bin/chatpop join                   # Tailscale signin, identity, cloud config, hooks
./bin/chatpop seed refresh --force   # Populate dev_seed from migrations + fixtures
./bin/chatpop admin import-env       # Push current backend/.env shared keys to AWS
```

After this, you have:
- AWS account fully provisioned for the team
- Canonical `dev_seed` everyone clones from
- Your own per-dev IAM user (e.g., `dev-robert`) — its keys live in `chatpop-dev` profile
- Admin keys (`chatpop-dev-deploy`) — live in `chatpop-dev-admin` profile
- Shared API keys (Stripe, OpenAI, etc.) centralized in Secrets Manager

---

## Joining an existing team

Once infrastructure exists, new developers run a much smaller flow on each machine:

```bash
./install.sh                         # Prerequisites + workspace prep, then calls chatpop join
```

`chatpop join` is idempotent. Use it for the same flow on a second machine — it detects existing DBs/S3 prefixes and reuses them rather than recreating.

What `chatpop join` walks through:
1. AWS credentials (paste from the admin's secure share)
2. Tailscale (install + sign in to the team's tailnet)
3. Developer identity (your name, written to `.dev-identity`)
4. Cloud config (clones `<your-name>_main` from `dev_seed` if first time on this machine)
5. Sync shared API keys from Secrets Manager
6. Activate git hooks

---

## Admin operations — managing the team roster

The `chatpop admin` subcommands manage IAM users for the team:

| Command | What it does |
|---|---|
| `chatpop admin list` | Show team roster (IAM users + access key IDs) |
| `chatpop admin add <name>` | Provision IAM user `dev-<name>` with scoped policies; print credentials once for secure handoff |
| `chatpop admin remove <name>` | Drop all `<name>_*` databases, delete `s3://.../<name>/`, destroy IAM user. Requires typed confirmation. |
| `chatpop admin recover` | Set up admin's machine after a wipe / on a new laptop. Like `chatpop join` but uses the `chatpop-dev-deploy` admin keys (so admin ops keep working). |

Each developer's IAM user has scoped permissions:

- Read/write S3 only under `<name>/*`
- Read-only on `dev_seed/*`
- Read the master DB password from Secrets Manager — but Postgres-level isolation is *not* enforced; see [CLAUDE.md → Layered authentication](../CLAUDE.md).

After `admin add`, send the new dev:

1. Their access key + secret (via 1Password, Signal, encrypted email — never plain Slack/email)
2. A Tailscale invite from https://login.tailscale.com/admin/users
3. Their developer name (matches what you typed into `admin add`)

---

## Shared API keys (Secrets Manager)

Third-party API keys (OpenAI, Stripe, Google Places, etc.) are stored centrally in AWS Secrets Manager (`chatpop-dev/api-keys`) as a single JSON blob. Devs pull them into their local `backend/.env`; rotation is one admin action + a team-wide sync.

### Initial setup (admin, one-time)

```bash
chatpop admin import-env       # Push current backend/.env shared keys to Secrets Manager
chatpop admin list-secrets     # Verify (values are masked)
```

### Onboarding a new dev

Automatic — `chatpop join` runs `sync-secrets` as part of the flow. Their `.env` is populated from Secrets Manager without anyone having to share keys directly.

### Rotating a key

```bash
# Admin
chatpop admin set-secret OPENAI_API_KEY    # Silent input, push to Secrets Manager
# Tell the team:
#   chatpop sync-secrets
#   restart Daphne
```

`sync-secrets` shows a masked diff for any key whose local `.env` value differs from the cloud value, so devs notice if they had a local edit they wanted to preserve:

```
⚠  1 key(s) overwritten (your local value -> cloud value):
  OPENAI_API_KEY: my-l...lue -> sk-c...oud
```

### Production retrieval (when prod exists)

`backend/chatpop/settings.py` detects `ENV=production` and pulls keys directly from Secrets Manager via `boto3` (no `.env` on prod hosts). The `aws-secretsmanager-caching` library refreshes every hour automatically; rolling restarts pick up rotation immediately. Same secret name pattern — `chatpop-prod/api-keys` instead of `chatpop-dev/api-keys`.

### Which keys are shared

The shared API keys are listed in `bin/chatpop` as `SHARED_KEYS`. Per-environment / per-developer values (`ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `NGROK_DOMAIN`, etc.) stay in local `.env` and don't go to Secrets Manager.

---

## CI / GitHub Actions

Workflow files live in `.github/workflows/` with a `.disabled` suffix — committed but inactive. Rename to enable when the team grows. See `.github/workflows/README.md` for setup steps. Two workflows are scaffolded:

- **`refresh-dev-seed.yml.disabled`** — On push to `main`, refreshes `dev_seed` on RDS via Tailscale + AWS OIDC.
- **`test.yml.disabled`** — On PR, runs the test suite against an ephemeral Postgres+pgvector container in the runner.

Until enabled, `chatpop seed refresh` and local `manage.py test` are the manual equivalents.

---

## Cost

Monthly AWS spend for a small team:

| Item | Monthly |
|---|---|
| RDS db.t4g.small (Postgres + pgvector) | ~$25 |
| RDS storage 20GB gp3 | ~$2.30 |
| RDS automated backups (7-day retention) | ~$1.50 |
| EC2 t4g.nano (Tailscale router) + 8GB EBS | ~$3.80 |
| Secrets Manager (2 secrets: rds/master + api-keys) | ~$0.80 |
| S3 (media, ~500MB total) | <$0.05 |
| Data transfer | ~$1 |
| **Total** | **~$35/month** |

Tailscale itself is free for up to 3 users / 100 devices on the personal plan.
