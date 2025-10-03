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

**STRICT ENFORCEMENT POLICY:**
- These ports MUST be used at all times - no exceptions
- If something is already running on these ports, kill it before starting servers
- Never use ports 3000, 3002, 8000, or any other ports for this project
- All CORS configurations, API URLs, and documentation must reference ONLY these ports
- Use `lsof -ti:PORT | xargs kill` to free up ports if needed

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

### Layout Architecture
**IMPORTANT:** The `/chat` route uses a dedicated layout to isolate chat-specific styles and viewport settings.

- **Root Layout** (`/app/layout.tsx`): Applies to all pages (/, /login, /register, /create)
  - Standard viewport settings (allows zoom, scrolling)
  - Minimal global styles

- **Chat Layout** (`/app/chat/layout.tsx`): Applies only to `/chat/*` routes
  - Disables pinch-to-zoom (`maximumScale: 1`, `userScalable: false`)
  - Fixed positioning to prevent address bar bounce on mobile
  - Chat-specific CSS loaded from `chat-layout.css`

This architecture ensures that chat-specific behaviors (fixed viewport, no zoom) don't affect other pages like login, registration, or the home page.

### Version Control
- GitHub repository
- Feature branch workflow recommended

### Testing

#### Running Tests

**All Backend Tests:**
```bash
cd backend
./venv/bin/python manage.py test
```

**With Verbose Output:**
```bash
./venv/bin/python manage.py test -v 2
```

**Specific Test Modules:**
```bash
# All chat tests
./venv/bin/python manage.py test chats

# Security tests (SQL injection, XSS, session tokens, username case preservation)
./venv/bin/python manage.py test chats.tests_security

# Username validation tests (length, character restrictions, case handling)
./venv/bin/python manage.py test chats.tests_validators

# Specific test class
./venv/bin/python manage.py test chats.tests_security.ChatSessionSecurityTests

# Specific test method
./venv/bin/python manage.py test chats.tests_security.ChatSessionSecurityTests.test_message_send_requires_session_token
```

**Test Coverage:**
- `chats.tests_security` - Security tests including:
  - SQL injection and XSS prevention
  - Session token validation
  - Username case preservation (both reserved and anonymous usernames)
  - Case-insensitive uniqueness enforcement
- `chats.tests_validators` - Username validation tests covering:
  - Minimum length (5 characters)
  - Maximum length (15 characters)
  - Allowed characters (letters, numbers, underscores)
  - Invalid characters rejection (spaces, special characters, unicode)
  - Case preservation
  - Whitespace trimming
- `accounts.tests` - User registration and authentication tests

#### Username Validation Rules

**Unified Validation:** The same validation rules apply to both reserved usernames (registration) and chat usernames (anonymous users).

**Rules:**
- **Minimum Length:** 5 characters (more than 4)
- **Maximum Length:** 15 characters
- **Allowed Characters:** Letters (a-z, A-Z), numbers (0-9), and underscores (_)
- **Disallowed Characters:** Spaces and all special characters except underscore
- **Case Handling:**
  - Case is **preserved** in storage and display (e.g., "Alice" stays "Alice")
  - Uniqueness checks are **case-insensitive** (e.g., cannot have both "Alice" and "alice")

**Implementation Files:**
- **Backend Validator:** `/backend/chats/validators.py` - Shared validation function used by both registration and chat join serializers
- **Frontend Validator:** `/frontend/src/lib/validation.ts` - Client-side validation matching backend rules
- **Test Suite:** `/backend/chats/tests_validators.py` - 10 test cases covering all validation scenarios
- **Security Tests:** `/backend/chats/tests_security.py` - Includes case preservation tests for both reserved and anonymous usernames

**Usage in Serializers:**
```python
from chats.validators import validate_username

def validate_reserved_username(self, value):
    """Validate reserved username format and uniqueness"""
    if value:
        value = validate_username(value)  # Format validation
        # Check case-insensitive uniqueness
        if User.objects.filter(reserved_username__iexact=value).exists():
            raise serializers.ValidationError("This username is already reserved")
    return value
```

**Frontend Usage:**
```typescript
import { validateUsername } from '@/lib/validation';

const validation = validateUsername(username);
if (!validation.isValid) {
  setError(validation.error || 'Invalid username');
  return;
}
```

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

## Theme Development Guidelines

### Theme Classification

**IMPORTANT:** Every theme must be explicitly classified as either **Light Mode** or **Dark Mode**. This ensures consistent styling across all UI components.

### Current Themes

| Theme ID | Name | Type | Primary Colors |
|----------|------|------|----------------|
| `purple-dream` | Purple Dream | Light | Purple/Pink gradients on white |
| `ocean-blue` | Ocean Blue | Light | Blue/Cyan gradients on white |
| `dark-mode` | Dark Mode | Dark | Cyan/Yellow accents on zinc-900 |

### Adding a New Theme

When creating a new theme (e.g., `forest-green`, `sunset-orange`), follow these steps:

#### 1. Determine Theme Type
Decide if the theme is **Light Mode** or **Dark Mode** based on:
- Primary background color (light = white/gray-50, dark = zinc-900/gray-900)
- Overall visual appearance
- User expectations (e.g., "Midnight Theme" would be dark)

#### 2. Apply Consistent Modal Styling

All modals and overlays must match the theme type. Update these components:

**Components requiring theme-specific styling:**
- `MessageActionsModal.tsx` - Long-press action menu
- `JoinChatModal.tsx` - Chat join dialog
- `ChatSettingsSheet.tsx` - Settings drawer
- Any future modals/drawers/overlays

**Light Mode Pattern:**
```typescript
overlay: 'bg-black/20 backdrop-blur-sm',
container: 'bg-white',
messagePreview: 'bg-gray-50 border border-gray-200',
messageText: 'text-gray-800',
actionButton: 'bg-gray-100 hover:bg-gray-200 text-gray-900',
```

**Dark Mode Pattern:**
```typescript
overlay: 'bg-black/60 backdrop-blur-sm',
container: 'bg-zinc-900',
messagePreview: 'bg-zinc-800 border border-zinc-600',
messageText: 'text-zinc-50',
actionButton: 'bg-zinc-700 hover:bg-zinc-600 text-zinc-50',
```

#### 3. Implementation Pattern

Use the centralized theme utilities from `/frontend/src/lib/themes.ts`:

```typescript
import { isDarkTheme, migrateLegacyTheme, type ThemeId } from '@/lib/themes';

// Check if theme is dark
const isDark = isDarkTheme(currentTheme);
className={isDark ? 'bg-zinc-900 text-white' : 'bg-white text-black'}

// Migrate legacy theme names (design1/2/3) to new names
const theme = migrateLegacyTheme(urlParam);
```

#### 4. Define Mobile Browser Theme Colors

**IMPORTANT:** Every theme must define `themeColor` in TWO locations for native mobile browser integration (URL bar/address bar coloring).

**Step 1:** Add the `themeColor` property to the theme's design configuration in `/frontend/src/app/chat/[code]/page.tsx`:

```typescript
const designs = {
  'your-theme-name': {
    themeColor: {
      light: '#ffffff',  // Hex color for light system mode
      dark: '#1f2937',   // Hex color for dark system mode
    },
    container: "...",
    header: "...",
    // ... rest of theme config
  },
};
```

**Step 2:** Add the theme to the `themeColors` mapping in `/frontend/src/app/chat/layout.tsx`:

```typescript
const themeColors = {
  'purple-dream': { light: '#ffffff', dark: '#1f2937' },
  'ocean-blue': { light: '#ffffff', dark: '#1f2937' },
  'dark-mode': { light: '#18181b', dark: '#18181b' },
  'your-theme-name': { light: '#ffffff', dark: '#1f2937' }, // Add your new theme here
};
```

**How to Choose Theme Colors:**
- Match the **header background color** of your theme
- Convert Tailwind CSS classes to hex values:
  - `bg-white` → `#ffffff`
  - `bg-gray-800` → `#1f2937`
  - `bg-zinc-900` → `#18181b`
  - `bg-purple-900` → `#581c87`
  - Use a Tailwind color reference or browser inspector to find exact hex values

**Examples:**
- **Purple Dream**: Uses `bg-white/80 dark:bg-gray-800/80` header → `{ light: '#ffffff', dark: '#1f2937' }`
- **Ocean Blue**: Uses `bg-white/80 dark:bg-gray-800/80` header → `{ light: '#ffffff', dark: '#1f2937' }`
- **Dark Mode**: Uses `bg-zinc-900` header (always dark) → `{ light: '#18181b', dark: '#18181b' }`

**Why This Matters:**
Mobile browsers use the `<meta name="theme-color">` tag to color the URL bar/address bar to match your app's design. This creates a native app-like experience similar to Discord, where the browser chrome seamlessly extends your theme's header color.

**How It Works:**
- Theme colors are set at page load (before React hydration) by reading from URL parameter or localStorage
- When user changes theme, the page reloads to apply new theme-color meta tags (iOS Safari requirement)
- The layout script detects system light/dark mode preference automatically
- Body background is set immediately to prevent color flash

#### 5. Validation Checklist

Before merging a new theme, verify:
- [ ] Theme type (Light/Dark) is documented in this file
- [ ] `themeColor` property defined with both light and dark hex values
- [ ] Theme colors match header background (test on mobile device)
- [ ] All modals use appropriate light/dark styling
- [ ] Text contrast meets accessibility standards
- [ ] Border colors are visible on theme background
- [ ] Icons and buttons are visible and properly styled
- [ ] Theme switch in ChatSettingsSheet displays correctly
- [ ] Mobile URL bar updates correctly on theme change (test on iOS Safari, Chrome Mobile)

### Why This Matters

Inconsistent modal styling creates a jarring user experience. A dark theme with white popups (or vice versa) breaks visual coherence and feels unpolished. Similarly, a mismatched URL bar color breaks the immersive mobile experience. By following these guidelines, we ensure every theme provides a cohesive, professional appearance across all devices and UI components.

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
