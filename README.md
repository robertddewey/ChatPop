# ChatPop.app

A platform that allows users to create and join chat rooms with various customization options, focusing on a mobile-first experience with excellent desktop browser support.

## Tech Stack

- **Backend:** Django 5.0 + Django REST Framework + Daphne (ASGI) + Channels (WebSockets)
- **Frontend:** Next.js + TypeScript + Tailwind CSS + shadcn/ui
- **Database:** PostgreSQL on AWS RDS (with pgvector)
- **Cache/Real-time:** Redis (local Docker)
- **Payments:** Stripe
- **Infrastructure:** AWS (RDS + S3 + EC2 Tailscale router + Secrets Manager) + local Docker for Redis

## Installation

ChatPop's development environment runs against **AWS RDS** (Postgres + pgvector) and **S3** (media), connected via **Tailscale**. Each developer has their own per-branch databases and S3 prefix, isolated from other developers. Local Docker is used only for Redis (the WebSocket channel layer + cache); there is no local Postgres.

There are three onboarding paths depending on your role:

- 🏃 **[New developer joining the team](#-new-developer-joining-the-team-alice)** (most common)
- 👑 **[First-time admin setting up infrastructure](#-first-time-admin-setting-up-infrastructure)** (one-time, you only do this once for the entire team)
- 🛟 **[Admin returning to a wiped or new machine](#-admin-returning-to-a-wiped-or-new-machine)**

All three converge on the **`chatpop` CLI** for daily operations.

### Prerequisites (all paths)

```bash
# macOS
brew install git python node mkcert awscli libpq
brew install --cask docker tailscale
brew tap hashicorp/tap && brew install hashicorp/tap/terraform
mkcert -install
```

| Tool | Purpose |
|---|---|
| `git`, `python`, `node` | Source control + backend + frontend runtimes |
| `docker` | Local Redis (required for the app). No local Postgres — RDS is used via Tailscale. |
| `mkcert` | Locally-trusted SSL certs (required for voice messages) |
| `awscli` | Talk to AWS services |
| `libpq` | `psql` and `pg_dump` for branch-DB cloning |
| `terraform` | AWS infrastructure provisioning |
| `tailscale` | Encrypted tunnel to the AWS VPC |

`ngrok` is optional — only needed if you'll test the app from a mobile device over the internet.

---

### 🏃 New developer joining the team (`alice`)

Your admin will give you (out of band — 1Password, Signal, etc.):
- AWS access key ID + secret access key
- A Tailscale invite to the team's tailnet (separate email)
- Your developer name (e.g., `alice`)
- The repository URL (and access to it)

```bash
# 1. Authenticate with GitHub (any of these works)
gh auth login                                     # easiest if you have gh
# OR set up an SSH key on github.com
# OR generate a Personal Access Token at github.com/settings/tokens

# 2. Run the installer (it will clone the repo)
./install.sh

# 3. When prompted, accept defaults (or paste a different repo URL)
# 4. install.sh will then automatically run 'chatpop join' which prompts for:
#    - Your AWS access key ID + secret (from your admin's secure share)
#    - Your developer name (e.g., 'alice')
#    Tailscale needs to be signed in interactively (browser will open).
#    chatpop join then automatically opts this device into the VPC subnet route
#    (tailscale set --accept-routes=true) — no manual config needed.

# 5. Verify
chatpop status
```

After that, start the servers in two terminals:

```bash
# Backend (Daphne, SSL on port 9000)
cd backend
./venv/bin/daphne -e ssl:9000:privateKey=../certs/localhost+3-key.pem:certKey=../certs/localhost+3.pem -b 0.0.0.0 chatpop.asgi:application

# Frontend (Next.js, SSL on port 4000)
cd frontend
npm run dev:https
```

Visit https://localhost:4000.

**Day-to-day from here:** the git hooks handle per-branch DB and S3 cloning automatically. `git checkout -b feat/foo` creates `<your-name>_feat_foo` on RDS and `s3://…/<your-name>/feat_foo/`. `git pull` runs `migrate` if migrations changed. See [docs/CLOUD_DEV.md](docs/CLOUD_DEV.md) for the full workflow.

---

### 👑 First-time admin setting up infrastructure

This is **one-time per AWS account** — you only do this when standing up the cloud environment for the first time. After this, future developers use the joiner flow above.

```bash
# Install prerequisites (same list as above)

# Clone the repo
git clone <repo-url>
cd ChatPop

# Step 1: Admin AWS profile (chatpop-dev-admin → chatpop-dev-deploy IAM user)
chatpop bootstrap aws

# Step 2: Tailscale on your laptop + EC2 router auth key
chatpop bootstrap tailscale

# Step 3: Provision AWS infrastructure (RDS, S3, EC2 router, Secrets Manager, IAM)
cd infra/terraform
terraform init && terraform apply
cd ../..

# Step 4: Provision your own per-developer IAM user
chatpop admin add robert                # creates dev-robert in IAM

# Step 5: Install dev-robert keys into your chatpop-dev profile
chatpop admin install-dev-keys robert

# Step 6: Tailscale signin (auto-enables --accept-routes), identity file,
#         cloud .env config, git hooks
chatpop join

# Step 7: Populate dev_seed (migrations + fixtures) so per-dev clones inherit it
chatpop seed refresh --force

# Step 8: Push current backend/.env shared API keys to AWS Secrets Manager
chatpop admin import-env

# Verify everything is wired up
chatpop status
chatpop check
```

After this you have **two AWS profiles** on the machine:
- `chatpop-dev-admin` (admin keys) — used by terraform and `chatpop admin *`
- `chatpop-dev` (dev-robert scoped keys) — used by Django and daily ops

Once this is done, you've got:
- An AWS account fully provisioned for the team
- A canonical `dev_seed` everyone clones from
- Your own per-dev IAM user (`dev-robert`) for daily work
- Shared API keys (Stripe, OpenAI, etc.) centralized in Secrets Manager

To onboard the next developer (Alice), just:

```bash
chatpop admin add alice
# Send Alice the printed credentials (1Password share, Signal, etc.)
# Invite alice@email.com to your tailnet at https://login.tailscale.com/admin/users
# Tell Alice: install.sh + chatpop join (the joiner flow above)
```

---

### 🛟 Admin returning to a wiped or new machine

Your IAM users (`chatpop-dev-deploy` admin and `dev-robert` developer) and infrastructure still exist in AWS — you just need to set up *this machine* to talk to them.

```bash
# Install prerequisites (same list as above)

# Clone the repo
git clone <repo-url>
cd ChatPop

# Recover — sets up BOTH chatpop-dev-admin and chatpop-dev profiles in one shot
chatpop admin recover
# Step A: paste admin keys (from 1Password) → chatpop-dev-admin profile
# Step B: confirm/enter your dev name (e.g. robert)
# Step C: dev-robert keys auto-pulled from terraform → chatpop-dev profile
# Step D: Tailscale signin (auto-enables --accept-routes) + cloud config + hooks
#         (delegates to chatpop join)

# Verify
chatpop status
chatpop check
```

If you've lost your admin keys, regenerate them in the AWS Console first:
https://console.aws.amazon.com/iam/home#/users/details/chatpop-dev-deploy → Security credentials → Deactivate old key → Create access key. Then run `chatpop admin recover`.

`install.sh` also offers admin recovery: when prompted "developer or admin?", pick `a`. It runs `chatpop admin recover` for you.

---

### `chatpop` CLI quick reference

```bash
chatpop                  # interactive menu (TTY)
chatpop status           # current dev / branch / DB / S3 / services
chatpop check            # active health checks across the stack
chatpop --help           # all commands
```

| Command | When |
|---|---|
| `chatpop status` | Show current state (passive read of `.env` + processes) |
| `chatpop check` | Active probes: AWS auth, Tailscale, RDS, S3 read/write, hooks, Daphne |
| `chatpop join` | Set up a developer machine (joiner / second machine) |
| `chatpop admin recover` | Set up an admin machine (wiped / new laptop) |
| `chatpop admin add <name>` | Provision a new developer (admin only) |
| `chatpop admin install-dev-keys [name]` | Pull dev-`<name>` keys from terraform into your `chatpop-dev` profile (admin only) |
| `chatpop admin remove <name>` | Tear down a developer's resources (admin only) |
| `chatpop admin replace-seed [DB]` | **Destructive, team-wide** — replace `dev_seed` (DB + S3) with contents of any source DB; defaults to `<dev>_main` (admin only) |
| `chatpop admin list` | Show team roster |
| `chatpop admin set-secret <K>` | Update a shared API key in Secrets Manager (admin) |
| `chatpop admin list-secrets` | List shared API keys (values masked) |
| `chatpop sync-secrets` | Pull latest shared API keys into local `.env` |
| `chatpop seed refresh` | Rebuild `dev_seed` from current branch's migrations + fixtures (admin) |
| `chatpop replace-main [BRANCH]` | **Destructive** — replace `<dev>_main` DB+S3 with a feature branch's contents. Use after a PR merge to keep the branch's test data |
| `chatpop fixtures load` | Re-load all `fixtures/*.json` into current DB |
| `chatpop clean [--apply]` | Sweep orphan branch DBs and S3 prefixes |
| `chatpop setup` | Activate git hooks (subset of `join`) |
| `chatpop bootstrap aws` | Initial admin AWS profile (first-time-admin only) |
| `chatpop bootstrap tailscale` | Capture EC2 router Tailscale key (first-time-admin only) |

See [docs/CLOUD_DEV.md](docs/CLOUD_DEV.md) for the full workflow guide. [CLAUDE.md](CLAUDE.md) has the architectural decisions and the conventions that guide AI assistant behavior.

---

## Development URLs

- **Frontend:** https://localhost:4000
- **Backend API:** https://localhost:9000
- **Django Admin:** https://localhost:9000/admin
- **Redis:** localhost:6381

## Project Structure

```
ChatPop/
├── backend/              # Django backend
│   ├── chatpop/         # Main Django project (settings.py with prod-aware secrets)
│   ├── chats/           # Chat app (models, views, WebSocket consumers)
│   ├── fixtures/        # Reference data (themes, config, gifts)
│   ├── .env             # Backend environment variables
│   ├── .env.example     # Backend environment template
│   ├── manage.py
│   ├── requirements.txt
│   └── venv/
├── frontend/            # Next.js frontend
│   ├── src/
│   ├── public/
│   ├── server.js        # Custom HTTPS server with WebSocket proxy
│   ├── .env.local       # Frontend environment variables
│   └── package.json
├── bin/                 # Daily-use CLI
│   └── chatpop          # Unified CLI for status / join / admin / clean / etc.
├── infra/               # Infrastructure tooling
│   ├── bootstrap.sh             # First-dev: AWS admin profile setup
│   ├── bootstrap-tailscale.sh   # First-dev: capture EC2 router auth key
│   ├── configure-env.sh         # Cloud .env writer (called by chatpop + hooks)
│   └── terraform/               # AWS infrastructure as code
│       ├── network.tf, database.tf, tailscale.tf, media.tf, developers.tf
│       └── developers.auto.tfvars  # Team roster (committed)
├── .githooks/           # Git hooks (post-checkout / post-merge) — branch DB+S3 automation
├── .github/workflows/   # GitHub Actions (refresh-dev-seed, tests — currently .disabled)
├── certs/               # SSL certificates (generated by mkcert)
├── docs/                # Documentation
├── docker-compose.yml   # Redis only (Postgres lives on AWS RDS)
├── install.sh           # Automated setup script (calls chatpop join)
├── NGROK-README.txt     # ngrok quick reference
├── CLAUDE.md            # Project documentation for Claude / detailed workflows
└── README.md
```

## Environment Variables

Environment values are split between **local config** (in `.env` files) and **shared secrets** (in AWS Secrets Manager).

### Local config — `backend/.env` and `frontend/.env.local`

Per-developer / per-machine values that don't make sense to share:

| Variable | Where | Purpose |
|---|---|---|
| `POSTGRES_*` | backend | RDS connection (set automatically by `chatpop use cloud`) |
| `AWS_PROFILE`, `AWS_STORAGE_BUCKET_NAME`, `AWS_LOCATION` | backend | S3 access (set by `chatpop use cloud`) |
| `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS` | backend | Per-dev (your LAN IP for mobile testing) |
| `NGROK_DOMAIN` | backend | Optional, your personal ngrok tunnel |
| `NEXT_PUBLIC_API_URL`, `PORT` | frontend | URLs and ports |

### Shared secrets — AWS Secrets Manager (`chatpop-dev/api-keys`)

Third-party API keys shared across the team:

| Variable | Source |
|---|---|
| `OPENAI_API_KEY` | Secrets Manager |
| `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY` | Secrets Manager |
| `GOOGLE_PLACES_API_KEY`, `TOMTOM_API_KEY` | Secrets Manager |
| `SERPAPI_API_KEY` | Secrets Manager |
| `ACRCLOUD_ACCESS_KEY`, `ACRCLOUD_SECRET_KEY`, `ACRCLOUD_HOST`, `ACRCLOUD_BEARER_TOKEN` | Secrets Manager |
| `CLOUDFLARE_TURNSTILE_SECRET_KEY` | Secrets Manager |
| `DJANGO_SECRET_KEY` | Secrets Manager |

**Pulling them into your `.env`:**

```bash
chatpop sync-secrets   # writes them into backend/.env
# (restart Daphne to pick up new values)
```

**Updating one (admin only):**

```bash
chatpop admin set-secret OPENAI_API_KEY    # silent input
# Tell the team to run: chatpop sync-secrets
```

**In production:** Django reads these directly from Secrets Manager via `boto3` (no `.env` on prod hosts) — see `backend/chatpop/settings.py`. Same secret naming pattern, just `chatpop-prod/api-keys` instead of `chatpop-dev/api-keys`.

## Documentation

Comprehensive documentation is organized in the `docs/` directory:

### Cloud development (start here)
- **[docs/CLOUD_DEV.md](docs/CLOUD_DEV.md)** - Cloud architecture, daily workflow, `chatpop` CLI reference, onboarding, admin operations, secrets management

### Core Documentation
- **[docs/MANAGEMENT_COMMANDS.md](docs/MANAGEMENT_COMMANDS.md)** - All 13 manage.py commands with examples
- **[docs/TESTING.md](docs/TESTING.md)** - Testing framework and Allure reports
- **[docs/CACHING.md](docs/CACHING.md)** - Redis message and reaction caching architecture
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Dual sessions, username validation, IP rate limiting
- **[docs/AUDIO.md](docs/AUDIO.md)** - iOS Safari-compatible audio implementation
- **[docs/THEME_STYLING_GUIDE.md](docs/THEME_STYLING_GUIDE.md)** - Complete ChatTheme database field reference
- **[docs/MONITORING.md](docs/MONITORING.md)** - Real-time cache & database monitoring system

### Deployment & Scaling
- **[docs/AWS_DEPLOYMENT_SCALING.md](docs/AWS_DEPLOYMENT_SCALING.md)** - AWS ECS Fargate deployment and scaling guide

### Project Documentation
- **[CLAUDE.md](CLAUDE.md)** - Conventions and architecture context that guide AI assistant behavior

## Stopping Services

Stop Docker containers:
```bash
docker-compose down
```

Stop backend: `Ctrl+C` in the Django terminal
Stop frontend: `Ctrl+C` in the Next.js terminal

## Running Tests

ChatPop uses pytest with Allure Framework for self-documenting tests and beautiful HTML reports.

### Quick Start

```bash
cd backend

# Run all tests
./run_tests.sh

# Run tests and view HTML report
./run_tests.sh --open

# Run with code coverage
./run_tests.sh --coverage

# Run specific tests
./run_tests.sh chats/tests/tests_security.py

# See all options
./run_tests.sh --help
```

### Test Suite Overview

- **Security Tests (26 tests)** - JWT sessions, XSS/SQL injection prevention
- **Username Validation (10 tests)** - Format rules, profanity filtering
- **Profanity Filter (26 tests)** - Context-aware detection, leet speak variants
- **Rate Limiting (12 tests)** - API abuse prevention, per-user/per-chat limits
- **Dual Sessions (16 tests)** - Anonymous + logged-in coexistence, IP limits
- **Redis Cache (49 tests)** - Hybrid storage, performance validation
- **Cache Performance Suite (78 tests)** - Factories, regression guards, protected-SET, index registry, batch eviction, bulk hydration. See `chats/tests/tests_factories.py`, `tests_cache_regressions.py`, `tests_protected_set.py`, `tests_index_registry.py`, `tests_batch_eviction.py`, `tests_bulk_hydration.py`.
- **Cache Load Suite (8 tests, `@tag('slow')`)** - 5000-message stress tests; excluded from default `manage.py test`. Run with `--tag=slow`.

**For complete test documentation, see [docs/TESTING.md](docs/TESTING.md)**
**For cache architecture details, see [docs/CACHING.md](docs/CACHING.md) and [docs/CACHE_PERFORMANCE_PLAN.md](docs/CACHE_PERFORMANCE_PLAN.md)**

## Theme Development

### SVG Background Patterns

Chat themes can include subtle SVG background patterns to add visual texture without interfering with message readability.

#### Current Implementation

**Themes with SVG backgrounds:**
- **Light Mode**: Light pattern with 30% opacity
- **Dark Mode (Emerald Green)**: Inverted cyan-tinted pattern (`invert(1)` + `hue-rotate(180deg)`, 6% opacity)

**SVG File:** `/frontend/public/bg-pattern.svg` (166KB optimized)

#### Adding SVG Backgrounds to Themes

**Step 1: Prepare SVG File**

Optimize the SVG using SVGO:
```bash
npx svgo input.svg -o optimized.svg
```

Place in public directory: `/frontend/public/bg-pattern.svg`

**Step 2: Configure Theme**

In `/frontend/src/app/chat/[code]/page.tsx`, add `messagesAreaBg` property:

```typescript
const designs = {
  'your-theme-name': {
    messagesArea: "absolute inset-0 overflow-y-auto px-4 py-4 space-y-3",
    messagesAreaBg: "bg-[url('/bg-pattern.svg')] bg-repeat bg-[length:800px_533px] opacity-[0.04] [filter:sepia(1)_hue-rotate(XXXdeg)_saturate(3)]",
    stickySection: "absolute top-0 left-0 right-0 z-20 ...",
  },
};
```

**For dark themes**, add `invert(1)` to reverse the SVG colors (light backgrounds):
```typescript
messagesAreaBg: "bg-[url('/bg-pattern.svg')] bg-repeat bg-[length:800px_533px] opacity-[0.03] [filter:invert(1)_sepia(1)_hue-rotate(180deg)_saturate(3)]",
```

**Key CSS properties:**
- `bg-[url('/bg-pattern.svg')]` - References SVG in public directory
- `bg-repeat` - Tiles pattern across background
- `bg-[length:800px_533px]` - Scales pattern (adjust for your SVG)
- `opacity-[0.04]` - Very subtle (4% visible for light themes)
- `[filter:sepia(1)_hue-rotate(XXXdeg)_saturate(3)]` - Colorizes pattern
  - `invert(1)` - (Optional) Reverses colors for dark themes
  - `sepia(1)` - Base sepia tone
  - `hue-rotate(XXXdeg)` - Color shift (0°=red, 120°=green, 180°=cyan, 310°=pink)
  - `saturate(3)` - Increases color intensity

**Step 3: Implement Layer Structure**

Background must be separate layer to avoid affecting messages:

```typescript
{/* Messages Container */}
<div className="relative flex-1 overflow-hidden">
  {/* Background Pattern - Fixed behind everything */}
  <div className={`absolute inset-0 pointer-events-none ${currentDesign.messagesAreaBg}`} />

  {/* Messages Area */}
  <div className={currentDesign.messagesArea}>
    {/* Messages with proper z-index */}
    <div className="space-y-3 relative z-10">
      {/* Messages render here */}
    </div>
  </div>
</div>
```

**Z-Index Layers:**
```
z-index: none  → Background pattern (absolute, pointer-events-none)
z-index: 10    → Messages content (relative)
z-index: 20    → Sticky section (host/pinned messages)
```

**Color Customization:**
- Red/Pink: `310deg - 350deg`
- Orange: `20deg - 40deg`
- Yellow: `50deg - 70deg`
- Green: `100deg - 140deg`
- Cyan/Blue: `170deg - 200deg`
- Purple: `260deg - 290deg`

**Opacity Guidelines:**
- **Light themes** (white/light backgrounds): `0.03 - 0.05` (very subtle)
- **Dark themes** (dark backgrounds with inverted SVG): `0.02 - 0.04` (extremely subtle)
- Moderate visibility: `0.05 - 0.08`
- High visibility: `0.08 - 0.15`

**Current production values:**
- Light Mode: `0.30` (30%)
- Dark Mode (Emerald Green): `0.06` (6%, with `invert(1)`)

**Performance:**
- External SVG loaded once per session
- Cached by browser
- Gzip/Brotli compression: 166KB → ~50KB
- No re-download on theme switch

See `CLAUDE.md` for complete theme development guidelines.

## Features Roadmap

### MVP Features
- ✅ Project structure and infrastructure
- ✅ Core chat room creation with unique URLs
- ✅ Public/Private chat modes (access codes)
- ✅ WebSocket real-time messaging
- ✅ Rich media support (voice, video, photo)
- ✅ Message reactions (multi-emoji)
- ✅ Paid message pinning (tiered pricing, outbid system)
- ✅ Host tipping
- ✅ Database-driven theme system (Dark Mode, Light Mode)
- ⏳ Back Room (paid seats)

## License

All rights reserved.
