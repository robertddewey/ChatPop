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

**2. Start Backend (Django with SSL/HTTPS on port 9000):**

**⚠️ CRITICAL: Backend MUST be started with SSL/HTTPS support using Daphne!**

Voice message recording requires HTTPS due to browser security policies for MediaRecorder API access. The backend must be started with Daphne and SSL certificates.

```bash
cd backend
./venv/bin/python manage.py migrate  # Run migrations (first time only)

# Start with Daphne and SSL (REQUIRED for voice messages)
ALLOWED_HOSTS=localhost,127.0.0.1,10.0.0.135 \
CORS_ALLOWED_ORIGINS="http://localhost:4000,http://127.0.0.1:4000,http://10.0.0.135:4000,https://localhost:4000,https://127.0.0.1:4000,https://10.0.0.135:4000" \
./venv/bin/daphne -e ssl:9000:privateKey=../certs/localhost+3-key.pem:certKey=../certs/localhost+3.pem -b 0.0.0.0 chatpop.asgi:application
```

Backend API: https://localhost:9000

**3. Start Frontend (Next.js with HTTPS on port 4000):**

**⚠️ CRITICAL: Frontend MUST also use HTTPS to match the backend!**

```bash
cd frontend
npm run dev:https
```

Frontend: https://localhost:4000

**Why SSL/HTTPS is Required:**
- **Voice Messages:** Browser MediaRecorder API requires a secure context (HTTPS)
- **WebSocket Security:** Secure WebSocket (WSS) connections require HTTPS
- **Mobile Testing:** iOS Safari requires HTTPS for microphone access
- **Production Parity:** Matches production environment configuration

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
./venv/bin/python manage.py test chats.tests.tests_security

# Username validation tests (10 tests)
./venv/bin/python manage.py test chats.tests.tests_validators

# Profanity filter tests (26 tests)
./venv/bin/python manage.py test chats.tests.tests_profanity

# Rate limit tests (12 tests)
./venv/bin/python manage.py test chats.tests.tests_rate_limits

# Dual sessions tests (16 tests)
./venv/bin/python manage.py test chats.tests.tests_dual_sessions

# Redis cache tests (49 tests)
./venv/bin/python manage.py test chats.tests.tests_redis_cache

# Specific test class
./venv/bin/python manage.py test chats.tests.tests_security.ChatSessionSecurityTests

# Specific test method
./venv/bin/python manage.py test chats.tests.tests_security.ChatSessionSecurityTests.test_message_send_requires_session_token
```

**Current Test Coverage:** 139+ tests across 7 test suites covering security, validation, profanity filtering, rate limiting, dual sessions, and Redis caching.

See [docs/TESTING.md](docs/TESTING.md) for detailed test documentation.

---

## Documentation

Comprehensive documentation is organized in the `docs/` directory:

- **[docs/TESTING.md](docs/TESTING.md)** - Complete test suite documentation (139 tests)
- **[docs/CACHING.md](docs/CACHING.md)** - Redis message and reaction caching architecture
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** - Dual sessions, username validation, IP rate limiting
- **[docs/AUDIO.md](docs/AUDIO.md)** - iOS Safari-compatible audio implementation
- **[docs/THEME_STYLING_GUIDE.md](docs/THEME_STYLING_GUIDE.md)** - Complete ChatTheme database field reference
- **[docs/MANAGEMENT_TOOLS.md](docs/MANAGEMENT_TOOLS.md)** - Redis cache inspection and debugging tools
- **[docs/blocking-feature-spec.md](docs/blocking-feature-spec.md)** - User blocking feature specification

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

### Database-Driven Theme System

ChatPop themes are defined in the PostgreSQL database via the `ChatTheme` model. All styling uses Tailwind CSS classes stored in database fields.

**For complete theme field reference, see:** [docs/THEME_STYLING_GUIDE.md](docs/THEME_STYLING_GUIDE.md)

This guide includes:
- All 60+ theme fields organized by category
- Implementation examples and best practices
- Voice message player styling (JSON schema)
- SVG background pattern configuration
- Mobile browser theme color integration
- Complete theme example (Emerald Green)

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
