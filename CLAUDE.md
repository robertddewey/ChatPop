# CLAUDE.md

## Project Overview

**Name:** ChatPop.app
**Purpose:** A platform that allows users to create and join chat rooms with various customization options, focusing on a mobile-first experience with excellent desktop browser support.

---

## MVP Features

### Core Chat Creation
- **Simple front page** with "Create a ChatPop" button
- Generates unique URL for each chat
- Creator becomes the host/admin of the chat
- Users only need usernames (no registration required for participants)

### Chat Access Options
- **Private Mode:** Requires access code to enter
- **Public Mode:** Open to everyone with the link

### Back Room Feature (Paid)
- Exclusive chat area with more direct access to the host
- Host sets price per seat
- Host defines seat limit
- Separate chat interface for Back Room participants

### Rich Media Support
- Optional feature to enable voice, video, or photo sharing
- Configurable by host during chat creation

### Message Features
- **Paid Message Pinning:** Users can pay to pin messages at the top for a period of time
  - Dynamic pricing: other users can bump pins by paying more
  - Base rate when no pinned messages exist
- **Host Messages:** Always highlighted and pinned above other pinned messages
- **Tip the Host:** Direct tipping functionality for participants

---

## Tech Stack

### Backend
- **Framework:** Django with Django REST Framework (DRF)
- **Server:** Daphne (ASGI server)
- **Database:** PostgreSQL (long-term message storage and general tables)
- **Cache/Real-time:** Redis (fast message read/writes, WebSockets)

### Frontend
- **Framework:** Next.js (React)
- **Styling:** Tailwind CSS
- **UI Components:** [ui.shadcn.com](https://ui.shadcn.com), Radix UI
- **Caching:** Frontend/browser caching for optimal performance

### Payments
- **Provider:** Stripe integration

### Infrastructure
- **Containers:** Docker for PostgreSQL and Redis
- **Monorepo:** Backend and frontend in same repository
- **Version Control:** GitHub

---

## Design Considerations

### UI/UX Philosophy
- **Mobile-First:** Optimized for incredible mobile experience, inspired by [Chat SDK Demo](https://demo.chat-sdk.dev/)
- **Responsive Design:** Scales beautifully to desktop with Tailwind's breakpoint system
- **Performance:** Aggressive caching and optimization for fast loading
- **Accessibility:** Radix UI primitives ensure accessible components

### UI Frameworks
- **shadcn/ui:** Pre-built, customizable components
- **Radix UI:** Unstyled, accessible component primitives
- **Consistent Design Language:** Clean, minimalist chat interface

---

## Development Practices

### Environment Setup
- `.env` for local configuration
- `.env.example` for template/documentation
- Docker Compose for local PostgreSQL and Redis instances

### Port Configuration
**IMPORTANT:** This project uses custom ports to avoid conflicts with other projects:
- **Frontend (Next.js):** Port **4000** (http://localhost:4000)
- **Backend (Django):** Port **9000** (http://localhost:9000)
- **PostgreSQL:** Port **5435** (localhost:5435)
- **Redis:** Port **6381** (localhost:6381)

### Starting the Development Servers

**1. Start Docker Containers (PostgreSQL & Redis):**
```bash
docker-compose up -d
```

Verify containers are running:
```bash
docker ps --filter "name=chatpop"
```

**2. Start Backend (Django on port 9000):**
```bash
cd backend
./venv/bin/python manage.py migrate  # Run migrations (first time only)
./venv/bin/python manage.py runserver 9000
```

Backend API: http://localhost:9000

**3. Start Frontend (Next.js on port 4000):**
```bash
cd frontend
npm run dev
```

Frontend: http://localhost:4000

### Repository Structure
- Monorepo containing both backend and frontend
- Clear separation of concerns between services
- `backend/` - Django project with DRF, Channels, WebSockets
- `frontend/` - Next.js with TypeScript, Tailwind, shadcn/ui

### Version Control
- GitHub repository
- Feature branch workflow recommended

---

## Audio Implementation (iOS Safari Compatible)

### Critical Implementation Details

**IMPORTANT:** iOS Safari has strict audio playback restrictions. The current implementation uses a proven approach that works reliably on iOS.

### Current Implementation
- **Location:** `/frontend/src/lib/sounds.ts`
- **Method:** HTML5 `<audio>` elements with dynamically generated WAV files (base64 data URLs)
- **Initialization:** AudioContext unlocked during "Join Chat" button click in `JoinChatModal`

### Why This Approach?
1. **Web Audio API alone DOES NOT work on iOS Safari** - even with a "running" AudioContext, iOS silently blocks output
2. **HTML5 Audio elements work reliably** - iOS treats them differently than Web Audio API
3. **One-time unlock** - The initial join gesture unlocks audio for the entire session

### How to Add New Sounds

To add sounds for pins, tips, or other events:

```typescript
// 1. Create a sound generator function in sounds.ts
const generatePinChime = (): string => {
  // Generate WAV file with higher frequency notes for urgency
  const notes = [783.99, 987.77]; // G5, B5
  // Use same WAV generation pattern as generateSuccessChime()
};

// 2. Export a play function
export const playPinSound = async () => {
  const audio = new Audio();
  audio.src = generatePinChime();
  audio.volume = 0.7;
  await audio.play();
};

// 3. Call from event handlers (WebSocket, etc.)
if (message.type === 'message_pinned') {
  playPinSound(); // No user gesture needed - already unlocked!
}
```

### DO NOT:
- ❌ Use Web Audio API oscillators directly (silent on iOS)
- ❌ Require additional user gestures for each sound
- ❌ Use external audio files (slower, requires network)

### DO:
- ✅ Use HTML5 Audio elements
- ✅ Generate WAV files programmatically as base64 data URLs
- ✅ Unlock audio during the join gesture
- ✅ Reuse the unlocked state for all future sounds

---

## Future Enhancements
- **Custom Themes:** Option to set specific themes/branding for chats
- **Enhanced Engagement:** Additional tipping options and gamification
- **Analytics:** Chat metrics and host dashboards

---

## Contribution Guidelines
If this is an open project, please follow these contribution practices:
1. Fork the repository and create feature branches for new work.
2. Submit pull requests with clear descriptions and references to related issues.
3. Ensure code follows project linting/formatting rules and passes tests.
4. Document new features or configuration options in the README or relevant files. 
