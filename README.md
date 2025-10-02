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

# Run a specific test class
./venv/bin/python manage.py test chats.tests_security.ChatSessionSecurityTests

# Run a specific test method
./venv/bin/python manage.py test chats.tests_security.ChatSessionSecurityTests.test_message_send_requires_session_token
```

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
