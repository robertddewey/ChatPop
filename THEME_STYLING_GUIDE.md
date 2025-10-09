# ChatPop Theme Styling Guide

**Complete Reference for ChatTheme Database Model**

This document provides a comprehensive guide to all styling fields in the `ChatTheme` model and what each field controls in the UI.

---

## Table of Contents

1. [Theme Metadata](#theme-metadata)
2. [Layout & Container](#layout--container)
3. [Message Types](#message-types)
4. [Voice Message Players](#voice-message-players)
5. [Reply Context Bubbles](#reply-context-bubbles)
6. [Icon Colors](#icon-colors)
7. [Username & Timestamp Styling](#username--timestamp-styling)
8. [Filter Buttons](#filter-buttons)
9. [Input Area](#input-area)
10. [Complete Theme Example](#complete-theme-example)

---

## Theme Metadata

### `theme_id` (CharField, max_length=50, unique, indexed)
**Purpose:** Unique identifier for the theme
**Format:** Kebab-case string (e.g., `dark-mode`, `emerald-green`, `ocean-blue`)
**Usage:** Used in URLs, localStorage, and theme selection
**Example:** `"dark-mode"`

### `name` (CharField, max_length=100)
**Purpose:** Human-readable display name
**Format:** Title case string
**Usage:** Shown in theme picker UI
**Example:** `"Emerald Green"`

### `is_dark_mode` (BooleanField, default=True)
**Purpose:** Classifies theme as light or dark mode
**Impact:** Affects modal backgrounds, text colors, and overlay opacity
**Values:**
- `True` - Dark theme (modals use dark backgrounds)
- `False` - Light theme (modals use light backgrounds)

### `theme_color_light` (CharField, max_length=7)
**Purpose:** Mobile browser address bar color for light system mode
**Format:** Hex color code (e.g., `#ffffff`, `#f8fafc`)
**Usage:** Sets `<meta name="theme-color">` for mobile browsers
**Best Practice:** Match your header background color
**Example:** `"#ffffff"` (white header) or `"#18181b"` (dark header)

### `theme_color_dark` (CharField, max_length=7)
**Purpose:** Mobile browser address bar color for dark system mode
**Format:** Hex color code
**Usage:** Sets `<meta name="theme-color" media="(prefers-color-scheme: dark)">` for mobile browsers
**Example:** `"#1f2937"` (gray-800) or `"#18181b"` (zinc-900)

---

## Layout & Container

### `container` (TextField)
**Purpose:** Main chat container styling
**Applied to:** Root chat container div
**Expected Classes:** Background, height, positioning, overflow
**Example:**
```
min-h-screen bg-zinc-900 flex flex-col
```

### `header` (TextField)
**Purpose:** Chat header bar styling
**Applied to:** Top navigation bar with chat name and back button
**Expected Classes:** Background, border, padding, positioning, backdrop-blur
**Example:**
```
bg-zinc-900 border-b border-zinc-700 sticky top-0 z-30 backdrop-blur-lg
```

### `header_title` (TextField)
**Purpose:** Chat room name text styling
**Applied to:** Main title text in header
**Expected Classes:** Font size, weight, color
**Example:**
```
text-lg font-bold text-white
```

### `header_title_fade` (TextField)
**Purpose:** Gradient fade effect on title (for long names)
**Applied to:** Overlay gradient on title text
**Expected Classes:** Gradient direction, colors
**Example:**
```
bg-gradient-to-r from-transparent via-transparent to-zinc-900
```

### `header_subtitle` (TextField)
**Purpose:** Subtitle or secondary text in header (e.g., participant count)
**Applied to:** Smaller text below or next to title
**Expected Classes:** Font size, color, opacity
**Example:**
```
text-sm text-zinc-400
```

### `sticky_section` (TextField)
**Purpose:** Container for sticky messages (host messages and pinned messages at top)
**Applied to:** Fixed section at top of messages area
**Expected Classes:** Background, border, padding, shadow, z-index (must be z-20 or higher)
**Critical:** Must include `z-20` to appear above background patterns
**Example:**
```
absolute top-0 left-0 right-0 z-20 border-b border-zinc-600 bg-zinc-800/80 backdrop-blur-lg px-4 py-2 space-y-2 shadow-md
```

### `messages_area` (TextField)
**Purpose:** Scrollable messages container
**Applied to:** Main scrolling div containing all messages
**Expected Classes:** Position, overflow, padding, spacing
**Example:**
```
absolute inset-0 overflow-y-auto px-4 py-4 space-y-3
```

### `messages_area_container` (TextField)
**Purpose:** Background color for messages area parent container (behind pattern layer)
**Applied to:** Outer container that holds both pattern layer and messages
**Expected Classes:** Background color only (solid, no patterns)
**Why separate:** Background patterns need a solid base color
**Example:**
```
bg-zinc-900
```

### `messages_area_bg` (TextField, blank=True)
**Purpose:** Optional SVG background pattern configuration
**Applied to:** Separate absolute layer behind messages (pointer-events-none)
**Expected Classes:** Background image URL, repeat, size, opacity, filters
**Implementation:** Applied to a separate `<div>` with `absolute inset-0 pointer-events-none`
**Example:**
```
bg-[url('/bg-pattern.svg')] bg-repeat bg-[length:800px_533px] opacity-[0.08] [filter:sepia(1)_hue-rotate(310deg)_saturate(3)]
```
**Leave blank if no pattern desired**

---

## Message Types

Messages in ChatPop come in four distinct types, each with specific styling requirements:

### 1. Your Messages (Current User)

**Message Bubble:**

#### `my_message` (TextField)
**Purpose:** Message bubble for current user's own messages
**Applied to:** Outer wrapper of your messages (right-aligned)
**Expected Classes:** Width, border-radius, padding, background, shadow, text color
**Structure:** Contains text content OR voice player wrapper
**Example:**
```
max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-3 bg-emerald-600 text-white shadow-md
```

#### `my_text` (TextField)
**Purpose:** Text color for message content
**Applied to:** Text inside message bubble
**Expected Classes:** Text color only
**Example:**
```
text-white
```

**Voice Message Player:**

#### `my_voice_message_styles` (JSONField)
**Purpose:** Complete styling for voice message audio player
**Structure:** JSON object with nested styling properties
**Applied to:** Voice player inside `my_message` bubble

**Schema:**
```json
{
  "containerBg": "bg-emerald-800/70",
  "playButton": "bg-emerald-800/70",
  "playButtonActive": "bg-emerald-400",
  "playIconColor": "text-white",
  "waveformActive": "bg-white/80",
  "waveformInactive": "bg-white/20",
  "durationTextColor": "text-white/60"
}
```

**Field Definitions:**
- `containerBg` - Background for inner container wrapping the player (`px-3 py-2 rounded-lg`)
- `playButton` - Background for play/pause button circle (default state)
- `playButtonActive` - Background for play/pause button when active/playing
- `playIconColor` - Color for play/pause icon (SVG fill)
- `waveformActive` - Color for played portion of waveform bars
- `waveformInactive` - Color for unplayed portion of waveform bars
- `durationTextColor` - Color for time display (e.g., "0:05")

**Visual Structure:**
```html
<div class="my_message">  <!-- Outer bubble: bg-emerald-600 -->
  <div class="px-3 py-2 rounded-lg containerBg">  <!-- Inner container: bg-emerald-800/70 -->
    <VoiceMessagePlayer />  <!-- Play button, waveform, duration -->
  </div>
</div>
```

---

### 2. Other User Messages (Regular Participants)

**Message Bubble:**

#### `regular_message` (TextField)
**Purpose:** Message bubble for other users' messages
**Applied to:** Outer wrapper of other users' messages (left-aligned)
**Expected Classes:** Width, border-radius, padding, background, shadow
**Example:**
```
max-w-[85%] rounded-xl px-4 py-3 bg-zinc-700 shadow-md
```

#### `regular_text` (TextField)
**Purpose:** Text color for message content
**Applied to:** Text inside message bubble
**Example:**
```
text-white
```

**Voice Message Player:**

#### `voice_message_styles` (JSONField)
**Purpose:** Styling for other users' voice messages
**Schema:** Same as `my_voice_message_styles`
**Example:**
```json
{
  "containerBg": "bg-zinc-600/40",
  "playButton": "bg-zinc-600/40",
  "playButtonActive": "bg-zinc-500",
  "playIconColor": "text-white",
  "waveformActive": "bg-white/80",
  "waveformInactive": "bg-white/20",
  "durationTextColor": "text-white/60"
}
```

---

### 3. Pinned Messages (Paid Highlights)

**Message Bubble:**

#### `pinned_message` (TextField)
**Purpose:** Message bubble for pinned messages in regular flow
**Applied to:** Outer wrapper of pinned messages (left-aligned)
**Expected Classes:** Width, border-radius, padding, background, border accent, shadow
**Note:** Use **solid colors** (no transparency like `/20` or `/30`) to work with SVG patterns
**Example:**
```
max-w-[85%] rounded-xl px-4 py-3 bg-yellow-700 border-l-4 border-yellow-400 shadow-lg
```

#### `sticky_pinned_message` (TextField)
**Purpose:** Message bubble for pinned messages in sticky section (top of chat)
**Applied to:** Pinned messages displayed in `sticky_section`
**Expected Classes:** Similar to `pinned_message` but optimized for compact sticky display
**Example:**
```
rounded-xl px-4 py-3 bg-yellow-700 border-l-4 border-yellow-400 shadow-lg
```

#### `pinned_text` (TextField)
**Purpose:** Text color for pinned message content
**Expected Classes:** Text color (often lighter for readability on dark backgrounds)
**Example:**
```
text-white
```

#### `pinned_message_fade` (TextField)
**Purpose:** Gradient fade for long pinned messages
**Applied to:** Overflow gradient overlay
**Example:**
```
bg-gradient-to-r from-transparent via-transparent to-yellow-700
```

**Voice Message Player:**

#### `pinned_voice_message_styles` (JSONField)
**Purpose:** Styling for pinned voice messages
**Schema:** Same as `my_voice_message_styles`
**Example (Emerald Green theme - uses amber for pins):**
```json
{
  "containerBg": "bg-amber-800",
  "playButton": "bg-amber-800",
  "playButtonActive": "bg-amber-500",
  "playIconColor": "text-white",
  "waveformActive": "bg-white/80",
  "waveformInactive": "bg-white/20",
  "durationTextColor": "text-white/60"
}
```

---

### 4. Host Messages (Chat Creator)

**Message Bubble:**

#### `host_message` (TextField)
**Purpose:** Message bubble for host messages in regular flow
**Applied to:** Outer wrapper of host messages (left-aligned)
**Expected Classes:** Width, border-radius, padding, background, shadow
**Note:** Use **solid colors** to work with SVG patterns
**Example:**
```
max-w-[85%] rounded-xl px-4 py-3 bg-teal-600 shadow-lg
```

#### `sticky_host_message` (TextField)
**Purpose:** Message bubble for host messages in sticky section
**Applied to:** Host messages displayed at top in `sticky_section`
**Example:**
```
rounded-xl px-4 py-3 bg-teal-600 shadow-lg
```

#### `host_text` (TextField)
**Purpose:** Text color for host message content
**Example:**
```
text-white
```

#### `host_message_fade` (TextField)
**Purpose:** Gradient fade for long host messages
**Example:**
```
bg-gradient-to-r from-transparent via-transparent to-teal-600
```

**Voice Message Player:**

#### `host_voice_message_styles` (JSONField)
**Purpose:** Styling for host voice messages
**Schema:** Same as `my_voice_message_styles`
**Example:**
```json
{
  "containerBg": "bg-teal-800",
  "playButton": "bg-teal-800",
  "playButtonActive": "bg-teal-500",
  "playIconColor": "text-white",
  "waveformActive": "bg-white/80",
  "waveformInactive": "bg-white/20",
  "durationTextColor": "text-white/60"
}
```

---

## Voice Message Players

### Architecture

Voice messages have a **nested container structure**:

```html
<div class="message_bubble">        <!-- my_message, regular_message, pinned_message, host_message -->
  <div class="voice_container">     <!-- px-3 py-2 rounded-lg + containerBg -->
    <button class="play_button">    <!-- w-8 h-8 rounded-full + playButton/playButtonActive -->
      <PlayIcon />                  <!-- playIconColor -->
    </button>
    <div class="waveform">          <!-- flex gap-0.5 -->
      <div class="bar" />           <!-- waveformActive or waveformInactive -->
      <div class="bar" />
      ...
    </div>
    <span class="duration">         <!-- durationTextColor, font-mono text-xs -->
      0:05
    </span>
  </div>
</div>
```

### Voice Message Styles JSON Schema

All four voice message style fields (`voice_message_styles`, `my_voice_message_styles`, `host_voice_message_styles`, `pinned_voice_message_styles`) use the same schema:

```typescript
{
  containerBg?: string;          // Background for wrapper div (px-3 py-2 rounded-lg)
  playButton?: string;           // Background for play button (default state)
  playButtonActive?: string;     // Background for play button (playing state)
  playIconColor?: string;        // Color for play/pause icon
  waveformActive?: string;       // Color for played waveform bars
  waveformInactive?: string;     // Color for unplayed waveform bars
  durationTextColor?: string;    // Color for time display (e.g., "0:05")
}
```

### Component Layout Specifications

**Play Button:**
- Size: `w-8 h-8` (32px circle)
- Shape: `rounded-full`
- Icon: Play (when paused) or Pause (when playing)
- Icon Size: `w-4 h-4` (16px)
- Icon Color: Controlled by `playIconColor`

**Waveform:**
- Container: `flex items-center gap-0.5` (2px between bars)
- Bar Style: `rounded-full` (vertical bars with rounded ends)
- Bar Width: `min-width: 2px`, flex to fill space
- Bar Heights: Variable (3px to 12px) for organic look
- Active Bars: Use `waveformActive` color (80% opacity white recommended)
- Inactive Bars: Use `waveformInactive` color (20% opacity white recommended)

**Duration Display:**
- Font: `font-mono` (monospace for consistent width)
- Size: `text-xs` (12px)
- Color: Controlled by `durationTextColor` (60% opacity recommended)
- Format: `M:SS` (e.g., "0:05", "1:23")

**Container:**
- Padding: `px-3 py-2`
- Border Radius: `rounded-lg`
- Layout: `flex items-center gap-3` (between button and waveform)
- Background: Controlled by `containerBg`

---

## Reply Context Bubbles

Reply context bubbles appear **inside** message bubbles to show which message is being replied to. They do NOT have dedicated database fields - their styling is derived from the message type and hardcoded in the frontend.

### Current Implementation (Hardcoded in MainChatView.tsx)

**Your Messages:**
```tsx
<div className="bg-black/60 backdrop-blur-sm border border-white/10 mb-2 p-2 rounded-lg">
  <Reply icon + username + truncated content />
</div>
```

**Other User Messages:**
```tsx
<div className="bg-zinc-800/60 backdrop-blur-sm border border-zinc-600 mb-2 p-2 rounded-lg">
  <Reply icon + username + truncated content />
</div>
```

**Pinned Messages:**
```tsx
<div className="bg-amber-900 border border-amber-700 mb-2 p-2 rounded-lg">
  <Reply icon + username + truncated content />
</div>
```

**Host Messages:**
```tsx
<div className="bg-teal-900 border border-teal-700 mb-2 p-2 rounded-lg">
  <Reply icon + username + truncated content />
</div>
```

### Future Consideration

If reply styling needs to be theme-customizable, consider adding these JSONFields to the model:
- `my_reply_styles`
- `regular_reply_styles`
- `pinned_reply_styles`
- `host_reply_styles`

---

## Icon Colors

Icons appear next to usernames and in various UI elements. All use simple Tailwind color classes.

### `pin_icon_color` (CharField, max_length=100)
**Purpose:** Color for pin icon (pushpin) in sticky pinned messages
**Icon Component:** `<Pin>` from lucide-react
**Applied to:** Icon next to username in sticky pinned messages, pin indicators
**Expected Format:** Tailwind text color class
**Example:** `"text-amber-400"`

### `crown_icon_color` (CharField, max_length=100)
**Purpose:** Color for crown icon next to host username
**Icon Component:** `<Crown>` from lucide-react
**Applied to:** Icon next to host username in all host messages
**Example:** `"text-teal-400"`

### `badge_icon_color` (CharField, max_length=100)
**Purpose:** Color for verified/reserved username badge
**Icon Component:** `<BadgeCheck>` from lucide-react
**Applied to:** Icon next to usernames that match registered `reserved_username`
**Example:** `"text-emerald-400"`

### `reply_icon_color` (CharField, max_length=100)
**Purpose:** Color for reply arrow icon in reply context bubbles
**Icon Component:** `<Reply>` from lucide-react
**Applied to:** Small icon in reply preview showing which message is being replied to
**Example:** `"text-emerald-300"`

---

## Username & Timestamp Styling

Each message type has independent styling for usernames and timestamps, allowing fine-grained control over typography, sizing, and opacity.

**Design Pattern:** Username and timestamp fields control **size and weight**, while message text color fields (`host_text`, `pinned_text`, `regular_text`, `my_text`) control **color**.

**Usage in components:** Applied as `className={`${currentDesign.STYLEFIELD} ${currentDesign.COLORFIELD}`}`

### Username Styling Fields

#### `my_username` (CharField, max_length=200)
**Purpose:** Styling for current user's username
**Applied to:** Username displayed above current user's messages (first in thread)
**Expected Classes:** Text size, font weight, color (optional - usually inherits from `my_text`)
**Default:** `"text-xs font-semibold text-gray-400"`
**Example:** `"text-xs font-semibold text-emerald-300"`

#### `regular_username` (CharField, max_length=200)
**Purpose:** Styling for other users' usernames
**Applied to:** Username displayed above other users' messages (first in thread)
**Expected Classes:** Text size, font weight, color
**Default:** `"text-xs font-semibold text-gray-400"`
**Example:** `"text-xs font-semibold text-gray-300"`

#### `host_username` (CharField, max_length=200)
**Purpose:** Styling for host username
**Applied to:** Username inside host message bubbles (combined with `host_text` for color)
**Expected Classes:** Text size, font weight (color from `host_text`)
**Default:** `"text-sm font-semibold"`
**Example:** `"text-sm font-semibold"` (with color from `host_text: "text-white"`)

#### `pinned_username` (CharField, max_length=200)
**Purpose:** Styling for pinned message username
**Applied to:** Username inside pinned message bubbles (combined with `pinned_text` for color)
**Expected Classes:** Text size, font weight (color from `pinned_text`)
**Default:** `"text-sm font-semibold"`
**Example:** `"text-sm font-semibold"` (with color from `pinned_text: "text-white"`)

### Timestamp Styling Fields

#### `my_timestamp` (CharField, max_length=200)
**Purpose:** Styling for current user's message timestamp
**Applied to:** Timestamp displayed with current user's messages
**Expected Classes:** Text size, opacity (color inherited from `my_text` or specified)
**Default:** `"text-xs opacity-60"`
**Example:** `"text-xs opacity-60"` (inherits color from `my_text`)

#### `regular_timestamp` (CharField, max_length=200)
**Purpose:** Styling for other users' message timestamp
**Applied to:** Timestamp displayed with other users' messages (next to username header)
**Expected Classes:** Text size, opacity, color
**Default:** `"text-xs opacity-60"`
**Example:** `"text-xs opacity-80 text-gray-400"`

#### `host_timestamp` (CharField, max_length=200)
**Purpose:** Styling for host message timestamp
**Applied to:** Timestamp inside host message bubbles (combined with `host_text` for color)
**Expected Classes:** Text size, opacity (color from `host_text`)
**Default:** `"text-xs opacity-60"`
**Example:** `"text-xs opacity-60"` (with color from `host_text: "text-white"`)

#### `pinned_timestamp` (CharField, max_length=200)
**Purpose:** Styling for pinned message timestamp
**Applied to:** Timestamp inside pinned message bubbles (combined with `pinned_text` for color)
**Expected Classes:** Text size, opacity (color from `pinned_text`)
**Default:** `"text-xs opacity-60"`
**Example:** `"text-xs opacity-60"` (with color from `pinned_text: "text-white"`)

**Note:** Timestamps typically use `opacity-60` or `opacity-70` to de-emphasize them relative to usernames and message content.

### Tailwind CSS Purging and Dynamic Classes

**CRITICAL:** Tailwind CSS purges (removes) classes during build that don't appear in your source code. Since username and timestamp styling is loaded dynamically from the database, color classes like `text-white` or `!text-white` will be purged and won't render.

**Solution:** Username and timestamp colors are applied using **inline styles** instead of Tailwind classes. The component uses a `getTextColor()` helper function that extracts color values from Tailwind class strings and converts them to hex codes for use in `style={{ color: ... }}`.

**Implementation Details:**
- `getTextColor()` function in `MainChatView.tsx` parses Tailwind classes (e.g., `"text-xs font-semibold text-white"`) and extracts the color value (`#ffffff`)
- Colors are applied via inline styles: `<span style={{ color: getTextColor(currentDesign.regularUsername) || '#ffffff' }}>`
- This bypasses Tailwind's build-time purging entirely
- Size and weight classes (`text-xs`, `font-semibold`, `opacity-60`) are hardcoded in the component and safe from purging

**Do NOT** add color classes to username/timestamp database fields expecting them to work. They will be extracted and converted to inline styles automatically.

---

## Filter Buttons

Filter buttons appear in the chat UI to filter message types (e.g., "All", "Pinned", "Host").

### `filter_button_active` (TextField)
**Purpose:** Styling for active/selected filter button
**Expected Classes:** Background, text color, border, padding, border-radius
**Example:**
```
bg-cyan-600 text-white px-4 py-2 rounded-lg font-semibold
```

### `filter_button_inactive` (TextField)
**Purpose:** Styling for inactive filter buttons
**Expected Classes:** Background, text color, border, padding, border-radius, hover state
**Example:**
```
bg-zinc-700 text-gray-300 px-4 py-2 rounded-lg hover:bg-zinc-600
```

---

## Input Area

### `input_area` (TextField)
**Purpose:** Container for message input section at bottom of chat
**Applied to:** Wrapper div containing input field and send button
**Expected Classes:** Background, border, padding, positioning
**Example:**
```
bg-zinc-800 border-t border-zinc-700 p-4 flex items-center gap-3
```

### `input_field` (TextField)
**Purpose:** Text input field styling
**Applied to:** `<input>` or `<textarea>` element for typing messages
**Expected Classes:** Background, text color, border, padding, border-radius, focus state
**Example:**
```
flex-1 bg-zinc-900 text-white border border-zinc-600 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500
```

---

## Complete Theme Example

Here's a complete Emerald Green theme configuration as a reference:

```json
{
  "theme_id": "emerald-green",
  "name": "Emerald Green",
  "is_dark_mode": true,
  "theme_color_light": "#18181b",
  "theme_color_dark": "#18181b",

  "container": "min-h-screen bg-zinc-900 flex flex-col",
  "header": "bg-zinc-900 border-b border-zinc-700 sticky top-0 z-30 backdrop-blur-lg px-4 py-3",
  "header_title": "text-lg font-bold text-white",
  "header_title_fade": "bg-gradient-to-r from-transparent via-transparent to-zinc-900",
  "header_subtitle": "text-sm text-zinc-400",

  "sticky_section": "absolute top-0 left-0 right-0 z-20 border-b border-zinc-600 bg-zinc-800/80 backdrop-blur-lg px-4 py-2 space-y-2 shadow-md",
  "messages_area": "absolute inset-0 overflow-y-auto px-4 py-4 space-y-3",
  "messages_area_container": "bg-zinc-900",
  "messages_area_bg": "",

  "my_message": "max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-3 bg-emerald-600 text-white shadow-md",
  "my_text": "text-white",

  "regular_message": "max-w-[85%] rounded-xl px-4 py-3 bg-zinc-700 text-white shadow-md",
  "regular_text": "text-white",

  "pinned_message": "max-w-[85%] rounded-xl px-4 py-3 bg-yellow-700 border-l-4 border-yellow-400 text-white shadow-lg",
  "sticky_pinned_message": "rounded-xl px-4 py-3 bg-yellow-700 border-l-4 border-yellow-400 text-white shadow-lg",
  "pinned_text": "text-white",
  "pinned_message_fade": "bg-gradient-to-r from-transparent via-transparent to-yellow-700",

  "host_message": "max-w-[85%] rounded-xl px-4 py-3 bg-teal-600 text-white shadow-lg",
  "sticky_host_message": "rounded-xl px-4 py-3 bg-teal-600 text-white shadow-lg",
  "host_text": "text-white",
  "host_message_fade": "bg-gradient-to-r from-transparent via-transparent to-teal-600",

  "voice_message_styles": {
    "containerBg": "bg-zinc-600/40",
    "playButton": "bg-zinc-600/40",
    "playButtonActive": "bg-zinc-500",
    "playIconColor": "text-white",
    "waveformActive": "bg-white/80",
    "waveformInactive": "bg-white/20",
    "durationTextColor": "text-white/60"
  },

  "my_voice_message_styles": {
    "containerBg": "bg-emerald-800/70",
    "playButton": "bg-emerald-800/70",
    "playButtonActive": "bg-emerald-400",
    "playIconColor": "text-white",
    "waveformActive": "bg-white/80",
    "waveformInactive": "bg-white/20",
    "durationTextColor": "text-white/60"
  },

  "host_voice_message_styles": {
    "containerBg": "bg-teal-800",
    "playButton": "bg-teal-800",
    "playButtonActive": "bg-teal-500",
    "playIconColor": "text-white",
    "waveformActive": "bg-white/80",
    "waveformInactive": "bg-white/20",
    "durationTextColor": "text-white/60"
  },

  "pinned_voice_message_styles": {
    "containerBg": "bg-amber-800",
    "playButton": "bg-amber-800",
    "playButtonActive": "bg-amber-500",
    "playIconColor": "text-white",
    "waveformActive": "bg-white/80",
    "waveformInactive": "bg-white/20",
    "durationTextColor": "text-white/60"
  },

  "filter_button_active": "bg-emerald-600 text-white px-4 py-2 rounded-lg font-semibold",
  "filter_button_inactive": "bg-zinc-700 text-gray-300 px-4 py-2 rounded-lg hover:bg-zinc-600",

  "input_area": "bg-zinc-800 border-t border-zinc-700 p-4 flex items-center gap-3",
  "input_field": "flex-1 bg-zinc-900 text-white border border-zinc-600 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-emerald-500",

  "pin_icon_color": "text-amber-400",
  "crown_icon_color": "text-teal-400",
  "badge_icon_color": "text-emerald-400",
  "reply_icon_color": "text-emerald-300"
}
```

---

## Style Guide Compliance Checklist

When creating or updating a theme, verify:

- [ ] **Theme Metadata**
  - [ ] `theme_id` is unique and kebab-case
  - [ ] `name` is descriptive and title case
  - [ ] `is_dark_mode` correctly set
  - [ ] `theme_color_light` and `theme_color_dark` match header background

- [ ] **Message Types**
  - [ ] All 4 message types have bubble styles defined
  - [ ] All 4 message types have text color defined
  - [ ] All 4 message types have voice player styles (if voice enabled)
  - [ ] Pinned and host messages use solid colors (no transparency)

- [ ] **Voice Players**
  - [ ] All 4 voice style JSONFields populated
  - [ ] `containerBg` defined for nested structure
  - [ ] `playButton` and `playButtonActive` are distinct colors
  - [ ] Waveform colors provide good contrast (80/20 opacity recommended)

- [ ] **Icons**
  - [ ] Pin icon color matches pinned message accent
  - [ ] Crown icon color matches host message theme
  - [ ] Badge icon color matches "your message" theme
  - [ ] Reply icon color is subtle but visible

- [ ] **Visual Hierarchy**
  - [ ] Sticky section has `z-20` or higher
  - [ ] Background pattern (if used) is subtle (opacity 0.05-0.10)
  - [ ] Text colors have sufficient contrast for accessibility
  - [ ] Border colors are visible on theme background

---

## Design Principles

1. **Consistency:** Related elements (e.g., all pinned message components) should share color families
2. **Hierarchy:** Host > Pinned > Your Messages > Other Messages
3. **Accessibility:** Maintain WCAG AA contrast ratios (4.5:1 for normal text, 3:1 for large text)
4. **Mobile-First:** Test on mobile devices to ensure touch targets and readability
5. **Performance:** Avoid excessive shadows, blurs, and animations
6. **Solid Backgrounds:** Pinned and host messages must use solid colors for SVG pattern compatibility

---

## Additional Resources

- **Tailwind CSS Documentation:** https://tailwindcss.com/docs
- **Lucide Icons:** https://lucide.dev/icons
- **Theme Utilities:** `/frontend/src/lib/themes.ts`
- **ChatTheme Model:** `/backend/chats/models.py` (lines 15-89)
- **Theme Serializer:** `/backend/chats/serializers.py` (lines 9-34)
- **Main Chat View Component:** `/frontend/src/components/MainChatView.tsx`

---

**Last Updated:** 2025-01-10
**Version:** 1.1
**Maintainer:** ChatPop Development Team
