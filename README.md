# ChatPop.app

A platform that allows users to create and join chat rooms with various customization options, focusing on a mobile-first experience with excellent desktop browser support.

## Tech Stack

- **Backend:** Django 5.0 + Django REST Framework + Daphne (ASGI) + Channels (WebSockets)
- **Frontend:** Next.js + TypeScript + Tailwind CSS + shadcn/ui
- **Database:** PostgreSQL
- **Cache/Real-time:** Redis
- **Payments:** Stripe
- **Infrastructure:** Docker (PostgreSQL & Redis)

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose

### 1. Start Docker Containers

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

### 2. Backend Setup (Django)

Navigate to backend directory:
```bash
cd backend
```

The virtual environment and dependencies are already set up. Run database migrations:
```bash
./venv/bin/python manage.py migrate
```

Create a superuser (optional):
```bash
./venv/bin/python manage.py createsuperuser
```

Start the Django development server on port **9000**:
```bash
./venv/bin/python manage.py runserver 9000
```

Backend will be available at: `http://localhost:9000`

### 3. Frontend Setup (Next.js)

Open a new terminal and navigate to frontend directory:
```bash
cd frontend
```

Dependencies are already installed. Start the Next.js development server:
```bash
npm run dev
```

Frontend will be available at: `http://localhost:4000`

## Development URLs

- **Frontend:** http://localhost:4000
- **Backend API:** http://localhost:9000
- **Django Admin:** http://localhost:9000/admin
- **PostgreSQL:** localhost:5435
- **Redis:** localhost:6381

## Project Structure

```
ChatPop/
├── backend/              # Django backend
│   ├── chatpop/         # Main Django project
│   ├── chats/           # Chat app
│   ├── .env             # Backend environment variables
│   ├── .env.example     # Backend environment template
│   ├── manage.py
│   ├── requirements.txt
│   └── venv/
├── frontend/            # Next.js frontend
│   ├── src/
│   ├── public/
│   ├── .env.local       # Frontend environment variables
│   └── package.json
├── docker-compose.yml   # PostgreSQL & Redis
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
- `STRIPE_SECRET_KEY` - Add your Stripe keys for payment features

## Stopping Services

Stop Docker containers:
```bash
docker-compose down
```

Stop backend: `Ctrl+C` in the Django terminal
Stop frontend: `Ctrl+C` in the Next.js terminal

## Running Tests

### Backend Tests

Run all Django tests:
```bash
cd backend
./venv/bin/python manage.py test
```

Run tests with verbose output:
```bash
./venv/bin/python manage.py test -v 2
```

Run specific test modules:
```bash
# Run all chat tests
./venv/bin/python manage.py test chats

# Run security tests only
./venv/bin/python manage.py test chats.tests_security

# Run username validation tests
./venv/bin/python manage.py test chats.tests_validators

# Run profanity filter tests
./venv/bin/python manage.py test chats.tests_profanity

# Run Back Room feature tests
./venv/bin/python manage.py test chats.tests

# Run rate limit tests
./venv/bin/python manage.py test chats.tests_rate_limits

# Run a specific test class
./venv/bin/python manage.py test chats.tests_security.ChatSessionSecurityTests

# Run a specific test method
./venv/bin/python manage.py test chats.tests_security.ChatSessionSecurityTests.test_message_send_requires_session_token
```

### Test Coverage

#### Security Tests (`chats.tests_security` - 26 tests)
**Purpose:** Comprehensive security testing to prevent common vulnerabilities and unauthorized access

**JWT Session Security Tests (17 tests):**
- Session token requirement validation
- Invalid/forged token rejection
- Expired token handling
- Chat-specific token validation (tokens can't be used across different chats)
- Username-specific token validation (tokens tied to specific usernames)
- Token signature verification (wrong secret keys rejected)
- Token payload tampering prevention
- Future-dated token rejection
- Empty/null token handling
- Private chat access code protection

**Username Reservation & Fingerprinting Tests (9 tests):**
- Anonymous user username uniqueness enforcement
- Reserved username protection (registered users)
- Anonymous + registered user coexistence with same name
- Fingerprint-based username persistence for anonymous users
- Username persistence for registered users
- Case-insensitive uniqueness with case preservation (both reserved & chat usernames)
- Case preservation in message display

**Attack Prevention Tests:**
- SQL injection attempts in usernames (blocked by validation)
- XSS attacks in usernames (blocked by validation)

#### Username Validation Tests (`chats.tests_validators` - 10 tests)
**Purpose:** Ensure username format requirements are properly enforced

**Validation Rules Tested:**
- Valid username patterns (letters, numbers, underscores only)
- Minimum length requirement (5 characters)
- Maximum length requirement (15 characters)
- Invalid character rejection (spaces, special characters, unicode/emoji)
- Whitespace handling (leading/trailing stripped, internal spaces rejected)
- Empty/None value handling
- Case preservation (original case maintained)
- Unicode/emoji character rejection
- Underscore positioning (allowed at any position)
- Numeric-only usernames (allowed)

#### Profanity Filter Tests (`chats.tests_profanity` - 18 tests)
**Purpose:** Prevent inappropriate usernames while avoiding false positives

**Profanity Checker Module Tests (5 tests):**
- Clean username validation
- Obvious profanity detection and blocking
- Leet speak variant detection (case variations, separators)
- Legitimate words with banned substrings allowed (e.g., "password", "assistant")
- ValidationResult structure verification

**Validator Integration Tests (4 tests):**
- Clean usernames pass profanity check
- Profane usernames fail validation
- Skip flag bypasses profanity filter (for auto-generated usernames)
- Legitimate words pass validation

**Chat Join API Tests (4 tests):**
- Clean usernames accepted
- Profane usernames rejected at join
- Leet speak profanity rejected
- Legitimate words with substrings accepted

**User Registration Tests (3 tests):**
- Clean reserved usernames accepted
- Profane reserved usernames rejected
- Registration without reserved username works

**Auto-generated Username Tests (2 tests):**
- Suggested usernames are always clean
- Suggest endpoint returns valid usernames

#### Back Room Feature Tests (`chats.tests` - 27 tests)
**Purpose:** Test paid Back Room functionality and access control

**Back Room Message Tests (15 tests):**
- BackRoom and BackRoomMessage model creation
- Host message viewing permissions
- Member message viewing permissions
- Non-member access blocking (403 Forbidden)
- Host message sending with HOST message type
- Member message sending with NORMAL message type
- Non-member send blocking
- Member list viewing (host-only)
- Non-host member list access blocking
- Back room full status calculation
- Message reply functionality

**Back Room Integration Tests (2 tests):**
- Accessing non-existent back room (404 handling)
- Empty message validation

#### Rate Limit Tests (`chats.tests_rate_limits` - 12 tests)
**Purpose:** Validate API rate limiting to prevent abuse and ensure fair usage

**Username Suggestion Rate Limiting (12 tests):**
- 20 requests per hour limit enforcement
- 21st request blocking with proper error response
- Per-fingerprint isolation (separate limits for different users)
- Per-chat isolation (separate limits for different chat rooms)
- IP-based fallback when fingerprint unavailable
- Counter increment verification (remaining count decrements correctly)
- Error message format validation
- Successful generation-only counting (failures don't count against limit)
- Non-existent chat handling (404, not rate limit)
- Independent limits for different fingerprints
- Cache key format verification
- Edge case: exactly 20 requests (boundary testing)

**Rate Limit Details:**
- Limit: 20 username suggestions per hour
- Scope: Per chat room, per fingerprint/IP
- Duration: 1 hour (3600 seconds)
- Response: 429 Too Many Requests when limit exceeded
- Tracking: Redis cache with auto-expiration

#### Authentication Tests (`accounts.tests`)
**Purpose:** User registration and authentication (basic template - to be expanded)

### Frontend Tests

Run Next.js tests (when test suite is added):
```bash
cd frontend
npm test
```

## Features Roadmap

### MVP Features
- ✅ Project structure and infrastructure
- ⏳ Core chat room creation
- ⏳ Public/Private chat modes
- ⏳ WebSocket real-time messaging
- ⏳ Back Room (paid seats)
- ⏳ Paid message pinning
- ⏳ Host tipping
- ⏳ Rich media support (voice, video, photo)

## License

All rights reserved.
