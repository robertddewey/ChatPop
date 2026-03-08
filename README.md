# ChatPop.app

A platform that allows users to create and join chat rooms with various customization options, focusing on a mobile-first experience with excellent desktop browser support.

## Tech Stack

- **Backend:** Django 5.0 + Django REST Framework + Daphne (ASGI) + Channels (WebSockets)
- **Frontend:** Next.js + TypeScript + Tailwind CSS + shadcn/ui
- **Database:** PostgreSQL
- **Cache/Real-time:** Redis
- **Payments:** Stripe
- **Infrastructure:** Docker (PostgreSQL & Redis)

## Installation Guide

**Quick Setup:** Run `./install.sh` (macOS/Linux) or follow the manual steps below.

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- **mkcert** - For generating SSL certificates (required for voice messages)
- **ngrok** (optional) - For mobile device testing via public tunnel

#### Install mkcert (One-Time Setup)

```bash
# macOS
brew install mkcert
mkcert -install

# Linux
sudo apt install mkcert  # Debian/Ubuntu
# or
sudo yum install mkcert  # RedHat/CentOS
mkcert -install
```

#### Install ngrok (Optional - for Mobile Testing)

```bash
# macOS
brew install ngrok

# Linux
snap install ngrok
```

Sign up and connect your authtoken at https://dashboard.ngrok.com

---

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd ChatPop
```

---

### 2. Generate SSL Certificates

**⚠️ REQUIRED:** Voice message recording requires HTTPS due to browser MediaRecorder API security policies.

```bash
# Create certificates directory
mkdir -p certs
cd certs

# Generate SSL certificates for localhost
mkcert localhost 127.0.0.1 10.0.0.135 ::1

# Rename files to match project expectations
mv localhost+3.pem localhost+3.pem
mv localhost+3-key.pem localhost+3-key.pem

cd ..
```

**Result:** You should now have:
- `certs/localhost+3.pem` (certificate)
- `certs/localhost+3-key.pem` (private key)

---

### 3. Start Docker Containers

Start PostgreSQL and Redis containers:

```bash
docker-compose up -d
```

Verify containers are running:
```bash
docker ps --filter "name=chatpop"
```

You should see:
- `chatpop_postgres` on port **5435**
- `chatpop_redis` on port **6381**

---

### 4. Backend Setup (Django)

Navigate to backend directory:
```bash
cd backend
```

#### Create Virtual Environment and Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate  # Windows

# Install Python dependencies
pip install -r requirements.txt
```

#### Configure Environment Variables

```bash
# Copy environment template
cp .env.example .env

# Edit .env if needed (defaults should work for local development)
```

#### Run Database Migrations

```bash
./venv/bin/python manage.py migrate
```

#### Load Fixtures and Initialize

```bash
# Load chat themes, config settings, and gift catalog
./venv/bin/python manage.py loaddata fixtures/theme.json
./venv/bin/python manage.py loaddata fixtures/config.json
./venv/bin/python manage.py loaddata fixtures/gifts.json

# Create system user (required for AI-generated discover rooms)
./venv/bin/python manage.py create_system_user
```

#### Create Test Data (Optional)

```bash
# Creates admin user (admin@chatpop.app / demo123), test users, and sample chat rooms
./venv/bin/python manage.py create_test_data
```

#### Create a Superuser (Optional)

```bash
./venv/bin/python manage.py createsuperuser
```

#### Collect Static Files

```bash
./venv/bin/python manage.py collectstatic --noinput
```

#### Start the Backend Server (with SSL)

**⚠️ IMPORTANT:** Use Daphne with SSL, not `runserver`. Voice messages require HTTPS.

```bash
./venv/bin/daphne -e ssl:9000:privateKey=../certs/localhost+3-key.pem:certKey=../certs/localhost+3.pem -b 0.0.0.0 chatpop.asgi:application
```

ALLOWED_HOSTS and CORS_ALLOWED_ORIGINS are configured in `backend/.env`. The defaults work for localhost. For LAN/mobile testing, add your LAN IP to both settings in `.env`.

Backend API will be available at: **https://localhost:9000** (note HTTPS)

---

### 5. Frontend Setup (Next.js)

Open a new terminal and navigate to frontend directory:
```bash
cd frontend
```

#### Install Dependencies

```bash
npm install
```

#### Configure Environment Variables

```bash
# Copy environment template
cp .env.example .env.local

# Edit .env.local if needed (defaults should work for local development)
```

**Note:** If `.env.example` doesn't exist, create `.env.local` with:
```bash
# Backend API URL (use https for SSL)
NEXT_PUBLIC_API_URL=https://localhost:9000

# WebSocket URL (use wss for secure websockets)
NEXT_PUBLIC_WS_URL=wss://localhost:9000

# Frontend server port (MUST be 4000 per project standards)
PORT=4000
```

#### Start the Frontend Server (with HTTPS)

**⚠️ IMPORTANT:** Frontend must also use HTTPS to match the backend.

```bash
npm run dev:https
```

Frontend will be available at: **https://localhost:4000** (note HTTPS)

---

### 6. Access the Application

- **Frontend:** https://localhost:4000
- **Backend API:** https://localhost:9000
- **Django Admin:** https://localhost:9000/admin

**Browser Security Warning:** You may see a security warning because mkcert uses a self-signed certificate. Click "Advanced" → "Proceed to localhost" to continue. This is safe for local development.

---

### 7. Mobile Testing with ngrok (Optional)

ngrok creates a public HTTPS tunnel to your local frontend, allowing you to test on mobile devices without LAN configuration.

```bash
# With a static domain (configured in backend/.env)
ngrok http https://localhost:4000 --url=your-domain.ngrok-free.app

# Without a static domain (ngrok assigns a random URL)
ngrok http https://localhost:4000
```

Get a free static domain at https://dashboard.ngrok.com/cloud-edge/domains

See [NGROK-README.txt](NGROK-README.txt) for quick reference.

---

### Quick Start Summary

For experienced developers, here's the quick version:

```bash
# 1. Install mkcert and generate certificates
brew install mkcert && mkcert -install
mkdir -p certs && cd certs && mkcert localhost 127.0.0.1 ::1 && cd ..

# 2. Start Docker services
docker-compose up -d

# 3. Backend setup
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
./venv/bin/python manage.py migrate
./venv/bin/python manage.py loaddata fixtures/theme.json
./venv/bin/python manage.py loaddata fixtures/config.json
./venv/bin/python manage.py loaddata fixtures/gifts.json
./venv/bin/python manage.py create_system_user
./venv/bin/python manage.py collectstatic --noinput

# 4. Frontend setup (in new terminal)
cd frontend
npm install
cp .env.example .env.local  # Create if doesn't exist

# 5. Start servers (in separate terminals)
# Terminal 1 - Backend
./venv/bin/daphne -e ssl:9000:privateKey=../certs/localhost+3-key.pem:certKey=../certs/localhost+3.pem -b 0.0.0.0 chatpop.asgi:application

# Terminal 2 - Frontend
npm run dev:https
```

---

## Development URLs

- **Frontend:** https://localhost:4000
- **Backend API:** https://localhost:9000
- **Django Admin:** https://localhost:9000/admin
- **PostgreSQL:** localhost:5435
- **Redis:** localhost:6381

## Project Structure

```
ChatPop/
├── backend/              # Django backend
│   ├── chatpop/         # Main Django project
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
├── certs/               # SSL certificates (generated by mkcert)
├── docs/                # Documentation
├── docker-compose.yml   # PostgreSQL & Redis
├── install.sh           # Automated setup script
├── NGROK-README.txt     # ngrok quick reference
├── CLAUDE.md            # Project documentation for Claude
└── README.md
```

## Environment Variables

Environment files are already configured with defaults:

**Backend:** `backend/.env` (created from `backend/.env.example`)
**Frontend:** `frontend/.env.local`

Key variables:
- `DJANGO_PORT=9000` - Django server port
- `PORT=4000` - Next.js server port
- `POSTGRES_PORT=5435` - PostgreSQL port
- `REDIS_PORT=6381` - Redis port
- `NGROK_DOMAIN` - Your ngrok static domain (optional, for mobile testing)
- `STRIPE_SECRET_KEY` - Add your Stripe keys for payment features
- `OPENAI_API_KEY` - For media analysis (photo descriptions)
- `ACRCLOUD_ACCESS_KEY` / `ACRCLOUD_SECRET_KEY` - For music identification

## Documentation

Comprehensive documentation is organized in the `docs/` directory:

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
- **[CLAUDE.md](CLAUDE.md)** - Complete project documentation for AI assistants

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

**For complete test documentation, see [docs/TESTING.md](docs/TESTING.md)**

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
