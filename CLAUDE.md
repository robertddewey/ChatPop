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

### Testing Guidelines

**IMPORTANT:** Follow these testing practices rigorously:

1. **Update Tests When Modifying Code:** Whenever you modify backend functionality, update the corresponding tests to reflect the changes. This ensures tests remain accurate and useful.

2. **Run Tests After Backend Changes:** Always run the test suite after making changes to backend code. This catches regressions and validates that new code works correctly.

3. **Document Tests in README:** When adding new tests, update the test coverage section in README.md to document what the tests cover and their purpose.

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

# Security tests (26 tests)
./venv/bin/python manage.py test chats.tests_security

# Username validation tests (10 tests)
./venv/bin/python manage.py test chats.tests_validators

# Profanity filter tests (18 tests)
./venv/bin/python manage.py test chats.tests_profanity

# Back Room feature tests (27 tests)
./venv/bin/python manage.py test chats.tests

# Rate limit tests (12 tests)
./venv/bin/python manage.py test chats.tests_rate_limits

# Specific test class
./venv/bin/python manage.py test chats.tests_security.ChatSessionSecurityTests

# Specific test method
./venv/bin/python manage.py test chats.tests_security.ChatSessionSecurityTests.test_message_send_requires_session_token
```

#### Current Test Coverage (101+ tests)

**Security Tests (`chats.tests_security` - 26 tests):**
- JWT session security (17 tests): token validation, expiration, chat/username binding, signature verification
- Username reservation & fingerprinting (9 tests): uniqueness, persistence, case handling
- Attack prevention: SQL injection, XSS protection

**Username Validation (`chats.tests_validators` - 10 tests):**
- Format requirements: length (5-15 chars), allowed characters (letters, numbers, underscores)
- Invalid character rejection: spaces, special characters, unicode/emoji
- Edge cases: whitespace handling, case preservation, numeric-only usernames

**Profanity Filter (`chats.tests_profanity` - 26 tests):**
- Profanity checker module (5 tests): clean validation, profanity detection, leet speak variants
- Validator integration (4 tests): profanity check integration, skip flag
- Chat join API (4 tests): profanity rejection at join endpoint
- Username validation endpoint (4 tests): real-time profanity checking during username input (Join ChatPop modal)
- Check username endpoint (4 tests): real-time profanity checking during registration
- User registration (3 tests): reserved username profanity checking
- Auto-generated usernames (2 tests): suggested usernames always clean

**Back Room Feature (`chats.tests` - 27 tests):**
- Back Room messaging (15 tests): permissions, message types, access control
- Integration tests (2 tests): error handling, validation

**Rate Limiting (`chats.tests_rate_limits` - 12 tests):**
- Username suggestion rate limiting: 20/hour per fingerprint/IP per chat
- Per-fingerprint and per-chat isolation
- IP fallback, counter verification, edge cases
- Cache key format and TTL verification

**Authentication (`accounts.tests`):**
- User registration and authentication (basic template - to be expanded)

See README.md for detailed test coverage breakdown.

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

## SVG Background Patterns

### Overview

Chat themes can include subtle SVG background patterns to add visual texture without interfering with message readability. This is a standardized system that uses external SVG files with CSS filters for colorization.

### Current Implementation

**Themes with SVG backgrounds:**
- **Pink Dream**: Pink-tinted pattern (`hue-rotate(310deg)`)
- **Ocean Blue**: Blue-tinted pattern (`hue-rotate(180deg)`)

**SVG File Location:** `/frontend/public/bg-pattern.svg` (166KB optimized)

### Adding SVG Backgrounds to New Themes

#### Step 1: Prepare SVG File

1. **Optimize the SVG** using SVGO to reduce file size:
   ```bash
   npx svgo input.svg -o optimized.svg
   ```

2. **Target file size:** Aim for ~3KB for inline SVGs, or up to ~200KB for external files (cached per session)

3. **Place in public directory:** Move the optimized SVG to `/frontend/public/bg-pattern.svg` (or use a theme-specific filename)

#### Step 2: Add Background to Theme Configuration

In `/frontend/src/app/chat/[code]/page.tsx`, add the `messagesAreaBg` property to your theme:

```typescript
const designs = {
  'your-theme-name': {
    // ... other theme properties
    messagesArea: "absolute inset-0 overflow-y-auto px-4 py-4 space-y-3",
    messagesAreaBg: "bg-[url('/bg-pattern.svg')] bg-repeat bg-[length:800px_533px] opacity-[0.08] [filter:sepia(1)_hue-rotate(XXXdeg)_saturate(3)]",
    stickySection: "absolute top-0 left-0 right-0 z-20 border-b ... bg-.../80 backdrop-blur-lg px-4 py-2 space-y-2 shadow-md",
  },
};
```

**Key properties:**
- `bg-[url('/bg-pattern.svg')]` - References the SVG file in public directory
- `bg-repeat` - Tiles the pattern across the entire background
- `bg-[length:800px_533px]` - Scales the pattern (adjust based on your SVG dimensions)
- `opacity-[0.08]` - Very subtle opacity (0.08 = 8% visible, adjust as needed)
- `[filter:sepia(1)_hue-rotate(XXXdeg)_saturate(3)]` - Colorizes the pattern:
  - `sepia(1)` - Converts to sepia tone (base for colorization)
  - `hue-rotate(XXXdeg)` - Shifts color (0°=red, 120°=green, 180°=cyan, 310°=pink)
  - `saturate(3)` - Increases color intensity

#### Step 3: Implement Background Layer Structure

The background pattern must be implemented as a separate layer to avoid affecting message content:

```typescript
{/* Messages Container */}
<div className="relative flex-1 overflow-hidden">
  {/* Background Pattern Layer - Fixed behind everything */}
  <div className={`absolute inset-0 pointer-events-none ${currentDesign.messagesAreaBg}`} />

  {/* Messages Area */}
  <div
    ref={messagesContainerRef}
    onScroll={handleScroll}
    className={currentDesign.messagesArea}
  >
    {/* Messages content with proper z-index */}
    <div className={`space-y-3 relative z-10 ${(stickyHostMessages.length > 0 || stickyPinnedMessage) ? 'pt-4' : ''}`}>
      {/* Messages render here */}
    </div>
  </div>
</div>
```

**Critical implementation details:**
- Background layer uses `absolute inset-0` to fill the entire container
- `pointer-events-none` prevents the background from blocking clicks/touches
- Background layer is positioned **outside** the scrollable messages container
- Messages content wrapper uses `relative z-10` to appear above background
- Sticky section uses `z-20` to appear above both background and messages

#### Step 4: Z-Index Layer Structure

Ensure proper stacking order:

```
z-index: none  → Background pattern layer (absolute, pointer-events-none)
z-index: 10    → Messages content (relative)
z-index: 20    → Sticky section (host messages, pinned messages)
```

**Important:** The `stickySection` in your theme config **must** use `z-20` to ensure sticky messages appear above the background pattern.

### Color Customization Examples

**Hue rotation values for common colors:**
- Red/Pink: `310deg - 350deg`
- Orange: `20deg - 40deg`
- Yellow: `50deg - 70deg`
- Green: `100deg - 140deg`
- Cyan/Blue: `170deg - 200deg`
- Purple: `260deg - 290deg`

**Opacity guidelines:**
- Very subtle (recommended): `0.05 - 0.10`
- Moderate: `0.10 - 0.15`
- Visible: `0.15 - 0.25`

### Performance Considerations

**File size impact:**
- External SVG loaded once per chat session
- Cached by browser (HTTP caching headers)
- Gzip/Brotli compression reduces size by ~70% (166KB → ~50KB)
- No re-download on theme switch within same session

**Optimization tips:**
- Use SVGO to remove unnecessary metadata and optimize paths
- Consider using simpler SVG patterns for better performance
- Test on mobile devices to ensure smooth scrolling

### Testing Checklist

Before merging a theme with SVG background:
- [ ] Background visible but subtle (doesn't interfere with messages)
- [ ] Pattern tiles seamlessly across entire chat area
- [ ] Color matches theme aesthetic (test hue-rotate values)
- [ ] Sticky messages appear above background (z-20)
- [ ] Scrolling performance is smooth on mobile devices
- [ ] Background doesn't receive click/touch events
- [ ] File size is optimized (run SVGO)

---

## Dual Sessions Architecture & IP Rate Limiting

### Overview

ChatPop implements a dual sessions architecture that allows users to have separate anonymous and logged-in participations in the same chat. This enables flexible user journeys while preventing abuse through IP-based rate limiting.

### Dual Sessions Architecture

**Key Principle:** Logged-in and anonymous users are treated as separate entities, even when using the same device/fingerprint.

**Implementation Details:**

1. **Anonymous Users** (`views.py:544-565`)
   - Identified by browser fingerprint
   - Participation has `user=null` and stores `fingerprint`
   - Can join any chat without registration
   - Username persists across sessions via fingerprint

2. **Logged-In Users** (`views.py:544-565`)
   - Identified by authenticated user account
   - Participation has `user=<User>` (fingerprint optional)
   - Reserved username with verified badge available
   - Username persists via user account

3. **Participation Priority** (`views.py:550-565`)
   - `MyParticipationView` checks for logged-in participation first
   - If authenticated: only check for `user`-based participation
   - If anonymous: only check for `fingerprint`-based participation where `user__isnull=True`
   - **No fallback** from logged-in to anonymous

4. **Username Coexistence** (`views.py:139-155`)
   - Anonymous user "robert" and logged-in user "Robert" can coexist
   - Separate participation records in same chat
   - Case-insensitive matching within each user type (anonymous vs logged-in)
   - Enables upgrade path: join anonymously → register → get verified badge

### Reserved Username Badge

**Badge Logic** (`views.py:570-573`):
```python
username_is_reserved = (participation.username.lower() == participation.user.reserved_username.lower())
```

- Badge shown when participation username matches user's reserved_username (case-insensitive)
- Only applies to logged-in users (anonymous users never have badge)
- Displayed in UI with BadgeCheck icon (frontend)

### IP-Based Rate Limiting

**Purpose:** Prevent abuse by limiting anonymous username creation from a single IP address.

**Implementation** (`views.py:98-125`):

```python
MAX_ANONYMOUS_USERNAMES_PER_IP_PER_CHAT = 3
```

**Rules:**
1. **Limit Scope:** 3 anonymous usernames per IP per chat
2. **Exemptions:**
   - Returning users (existing fingerprint) can always rejoin
   - Logged-in users not affected by limit
3. **Enforcement:**
   - Check runs before creating new anonymous participation
   - Returns 400 Bad Request with clear error message
4. **IP Storage:**
   - Raw IP addresses stored in `ChatParticipation.ip_address`
   - Updated on every join/rejoin
   - Used for rate limiting queries

**Example Use Cases:**

- ✅ User joins as "alice" → joins as "bob" → joins as "charlie" (3rd username, allowed)
- ❌ User tries to join as "david" (4th username, blocked)
- ✅ User with fingerprint for "alice" rejoins (returning user, allowed)
- ✅ User logs in and joins as "eve" (logged-in user, not counted)
- ✅ Different IP can create 3 new usernames (per-IP limit)

### User Journey Examples

**Scenario 1: Anonymous → Registered with Same Username**
1. User joins chat anonymously as "robert" (no badge)
2. User registers account with reserved_username="robert"
3. User returns to chat as logged-in user
4. `MyParticipationView` shows no participation (logged-in session doesn't see anonymous)
5. User joins as "Robert" (creates new logged-in participation)
6. Badge displays because "Robert" matches reserved_username (case-insensitive)
7. Both participations coexist: anonymous "robert" and verified "Robert"

**Scenario 2: IP Rate Limiting**
1. Anonymous user from IP 192.168.1.100 joins as "user1"
2. Same IP joins as "user2" (fingerprint2)
3. Same IP joins as "user3" (fingerprint3)
4. Same IP tries to join as "user4" → **BLOCKED** (max 3 reached)
5. Original user (fingerprint1) tries to rejoin → **ALLOWED** (returning user)
6. User logs in and joins → **ALLOWED** (logged-in users exempt)

### Testing

Comprehensive test suite in `backend/chats/tests_dual_sessions.py` (16 tests):

**Dual Sessions Tests (6 tests):**
- Anonymous and logged-in join create separate participations
- Same username coexistence (case-insensitive)
- Participation priority and no-fallback logic

**Reserved Username Badge Tests (4 tests):**
- Exact and case-insensitive match detection
- Badge not shown for different usernames or anonymous users

**IP Rate Limiting Tests (6 tests):**
- 3-username limit enforcement
- Returning user exemption
- Logged-in user exemption
- Per-IP and per-chat isolation

Run tests:
```bash
./venv/bin/python manage.py test chats.tests_dual_sessions
```

### Database Schema

**ChatParticipation Model** (`models.py:253-270`):
```python
user = ForeignKey(User, null=True, blank=True)  # Logged-in user
fingerprint = CharField(max_length=255, null=True, blank=True)  # Anonymous identifier
username = CharField(max_length=15)  # Chat username (may differ from reserved_username)
ip_address = GenericIPAddressField(null=True, blank=True)  # For rate limiting
```

**Unique Constraint** (`models.py:289-294`):
- User-based participation: unique per (chat_room, user)
- Anonymous participation: unique per (chat_room, fingerprint) where user is null

---

## Redis Message Caching Architecture

### Overview

ChatPop uses a **hybrid Redis/PostgreSQL message storage strategy** to optimize real-time chat performance while maintaining data persistence and integrity.

**Key Principle:** PostgreSQL is the source of truth, Redis is the fast cache for recent messages.

### Architecture Components

**PostgreSQL (Permanent Storage)**
- **Role:** Long-term message log, source of truth
- **Stores:** All messages permanently with full metadata
- **Use Cases:** Message history, search, analytics, compliance

**Redis (Fast Cache)**
- **Role:** Hot cache for real-time message delivery
- **Stores:** Recent messages (last 500 or 24 hours per chat)
- **Use Cases:** Real-time WebSocket broadcasts, initial message load, scroll pagination

### Message Flow

**On Message Send (Dual-Write Pattern):**
1. User sends message via WebSocket
2. **Write to PostgreSQL** (permanent record, includes all fields)
3. **Write to Redis** (cached copy with `username_is_reserved` badge status)
4. Broadcast to all connected clients via WebSocket

**On Message Load (Read-First Pattern):**
1. Frontend requests recent messages (GET `/api/chats/{code}/messages/`)
2. **Check Redis first** (sorted set with timestamp scores)
3. **Fallback to PostgreSQL** if Redis miss (old messages, cache expired)
4. Return messages with source indicator (`"source": "redis"` or `"source": "postgresql"`)

### Redis Data Structures

**Regular Messages:**
```
Key: chat:{chat_code}:messages
Type: Sorted Set (ZADD)
Score: Unix timestamp (microseconds for ordering)
Value: JSON message object
TTL: 24 hours OR last 500 messages (whichever is larger)
```

**Pinned Messages:**
```
Key: chat:{chat_code}:pinned
Type: Sorted Set (ZADD)
Score: pinned_until timestamp (for auto-expiry)
Value: JSON message object
TTL: 7 days
```

**Back Room Messages:**
```
Key: chat:{chat_code}:backroom:messages
Type: Sorted Set (ZADD)
Score: Unix timestamp
Value: JSON message object
TTL: 24 hours OR last 500 messages
```

### Message Serialization

Messages in Redis include the `username_is_reserved` flag for frontend badge display:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "chat_code": "ABC123",
  "username": "Robert",
  "username_is_reserved": true,
  "user_id": 42,
  "message_type": "normal",
  "content": "Hello everyone!",
  "reply_to_id": null,
  "is_pinned": false,
  "created_at": "2025-01-04T12:34:56.789Z",
  "is_deleted": false
}
```

### Cache Retention Policy

**Hybrid Retention:** Keep last **500 messages** OR **24 hours**, whichever is larger.

**Implementation:**
- On each new message, trim old messages if count exceeds 500
- Redis key TTL set to 24 hours (refreshed on each message)
- Expired messages automatically removed by Redis

**Benefits:**
- Active chats: Last 500 messages always available (even if >24h old)
- Inactive chats: Auto-cleanup after 24h to free memory
- No manual cleanup jobs needed

### Pinned Message Handling

**When a message gets pinned:**
1. Update message in PostgreSQL (`is_pinned=True`, set `pinned_until`)
2. Add to Redis pinned cache (`chat:{chat_code}:pinned`)
3. Score = `pinned_until` timestamp (enables auto-expiry)
4. Broadcast pin event via WebSocket

**When pin expires:**
- Automatic: Redis removes by score (`ZREMRANGEBYSCORE`)
- Manual: API endpoint calls `MessageCache.remove_pinned_message()`

**Old Message Pinning:**
- Messages beyond Redis retention can still be pinned
- System loads from PostgreSQL and adds to pinned cache
- No need to check if message exists in regular cache

### Performance Characteristics

**Expected Latencies:**
- **Message Send:** ~25ms (5ms Redis + 20ms PostgreSQL)
- **Load Recent (Redis hit):** <2ms
- **Load Recent (PostgreSQL fallback):** <100ms
- **WebSocket Broadcast:** <2ms (reads from Redis)
- **Scroll Pagination (Redis):** <2ms
- **Scroll Pagination (PostgreSQL):** <100ms

**Cache Hit Rates:**
- **Active Chats:** ~95-99% (most loads from Redis)
- **Inactive Chats:** ~0-50% (depends on message age)

### Configuration Settings

Located in `backend/chatpop/settings.py`:

```python
# Django Cache (django-redis)
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "PARSER_CLASS": "redis.connection.HiredisParser",
            "CONNECTION_POOL_KWARGS": {"max_connections": 50}
        }
    }
}

# Message Cache Settings
MESSAGE_CACHE_MAX_COUNT = 500  # Max messages per chat in Redis
MESSAGE_CACHE_TTL_HOURS = 24   # Auto-expire after 24 hours
```

**Environment Variables:**
- `MESSAGE_CACHE_MAX_COUNT` (default: 500)
- `MESSAGE_CACHE_TTL_HOURS` (default: 24)

### Implementation Files

**Core Modules:**
- `backend/chats/redis_cache.py` - MessageCache utility class
- `backend/chats/consumers.py` - WebSocket consumer (dual-write on send)
- `backend/chats/views.py` - MessageListView (Redis-first read)

**Key Methods:**
- `MessageCache.add_message()` - Add message to Redis cache
- `MessageCache.get_messages()` - Fetch recent messages (Redis)
- `MessageCache.get_messages_before()` - Pagination support
- `MessageCache.add_pinned_message()` - Cache pinned message
- `MessageCache.get_pinned_messages()` - Fetch active pins (auto-expires)

### Edge Cases & Error Handling

**Redis Failure:**
- Write errors: Log but don't crash (PostgreSQL has the data)
- Read errors: Automatic fallback to PostgreSQL
- No impact on data integrity (PostgreSQL is source of truth)

**Cache Inconsistency:**
- Redis cleared: PostgreSQL backfills on next read
- Message edited: Update both stores (dual-write)
- Message deleted: Remove from both stores

**Race Conditions:**
- Use microsecond timestamps for ordering
- PostgreSQL `created_at` matches Redis score
- Ensures consistent message ordering across stores

### Monitoring & Debugging

**Cache Health Metrics:**
- Track `source` field in API responses (`redis` vs `postgresql`)
- Monitor cache hit rate (% of loads from Redis)
- Alert if hit rate drops below 90% for active chats

**Debug Tools:**
- `MessageCache.clear_chat_cache(chat_code)` - Manual cache invalidation
- Redis CLI: `ZRANGE chat:ABC123:messages 0 -1` - Inspect cached messages
- PostgreSQL: Compare message counts with Redis (`ZCARD`)

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
