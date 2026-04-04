# Session-Primary Anonymous Identity + Tiered Ban System

## Context

Anonymous users are currently identified by browser fingerprints (FingerprintJS), which have a ~1-in-200 collision rate. Two users on the same device model/browser/OS can share the same fingerprint, causing false ban matches and identity confusion. This migration switches to Django session keys as the primary anonymous identifier (zero collisions) and retains fingerprints only for ban enforcement. The PIN system is removed since fingerprint is no longer the identity — there's nothing to protect from spoofing.

## Key Decisions

- **Session = primary anonymous ID** (unique per browser, no collisions)
- **Clearing cookies = start fresh** (new session, new username, no recovery)
- **Fingerprint = ban enforcement only** (collected at join, stored on participation)
- **PIN system removed** (fingerprint is no longer the identity, nothing to protect from spoofing)
- **Three ban tiers** (host chooses): session, fingerprint+IP, total IP
- **Host is never affected by any ban** in their own chat

## Phase 1: Backend Model & Config Changes

### 1a. Add session_key fields
**File:** `backend/chats/models.py`

- `ChatParticipation`: add `session_key = CharField(max_length=40, null=True, blank=True, db_index=True)`. Add `UniqueConstraint('chat_room', 'session_key', condition=Q(session_key__isnull=False, user__isnull=True), name='unique_chat_session_key')`
- `MessageReaction`: add `session_key = CharField(max_length=40, null=True, blank=True, db_index=True)`
- `ChatBlock`: add `blocked_session_key = CharField(max_length=40, null=True, blank=True)` and `ban_tier = CharField(max_length=20, choices=[('session','Session'),('fingerprint_ip','Device+IP'),('ip','IP')], default='session')`
- `SiteBan`: add `banned_session_key = CharField(max_length=40, null=True, blank=True, db_index=True)`

### 1b. Migration
**File:** `backend/chats/migrations/0005_add_session_key_fields.py`
Auto-generate with `makemigrations`. Schema only, no data migration.

### 1c. Session config
**File:** `backend/chatpop/settings.py`
```python
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 14 * 24 * 60 * 60  # 14 days
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = True
```

### 1d. JWT changes
**File:** `backend/chats/utils/security/auth.py`
- `create_session_token()`: add `session_key` param, include in JWT payload alongside fingerprint
- Remove `verify_anonymous_pin()` entirely
- Keep `decode_token_ignore_expiry()` for refresh flow

## Phase 2: Backend View Migration

### 2a. ChatRoomJoinView
**File:** `backend/chats/views.py` (~line 290)
- Ensure session exists: `if not request.session.session_key: request.session.create()`
- Store `session_key` on `ChatParticipation`
- **Remove PIN verification** from join flow (PIN system removed)
- Participation lookup: session_key only (no fingerprint fallback — clearing cookies = new identity)
- Old fingerprint-only participation records become orphaned (acceptable)
- Username generation Redis keys: `generated_for_session:{session_key}`
- Include `session_key` in JWT
- Keep collecting `fingerprint` from request for ban data storage

### 2b. Ban enforcement with tiers
**File:** `backend/chats/utils/security/blocking.py`
- `block_participation()`: store `ban_tier` and `blocked_session_key` from participation
- `check_if_blocked()`: add `session_key` param, implement tier logic:
  - `session` tier: match `blocked_session_key` only
  - `fingerprint_ip` tier: match `blocked_fingerprint` AND `blocked_ip_address`
  - `ip` tier: match `blocked_ip_address` only
- **Host exemption**: at top of `check_if_blocked()`, if requesting user is `chat_room.host`, return `(False, None)` immediately
- Same exemption in `SiteBan.is_banned()` — accept optional `chat_room` param, skip if user is host

### 2c. BlockUserView
**File:** `backend/chats/views.py` (~line 3173)
- Accept `ban_tier` in request data (default: `'session'`)
- Pass tier to `block_participation()`
- Host lookup: use `session_key` from JWT for anonymous host (currently uses fingerprint at line 3218)

### 2d. Other views switching to session_key
All anonymous lookups change from `fingerprint=X, user__isnull=True` to `session_key=X, user__isnull=True` (no fingerprint fallback):
- `RefreshSessionView` — validate by session_key, remove PIN requirement
- `MyParticipationView` — lookup by session_key, remove fingerprint param
- `MessageReactionToggleView` — reactions keyed by session_key
- `MessageListView` — has_reacted queries use session_key
- `SuggestUsernameView` — rate limiting by session_key
- `UpdateMyThemeView`, `DismissIntroView` — lookup by session_key
- `FingerprintUsernameView` — deprecate (return 503), remove in cleanup phase

### 2e. WebSocket consumer
**File:** `backend/chats/consumers.py`
- Extract `session_key` from JWT payload in `connect()`
- Pass to `check_if_banned()` alongside fingerprint
- Host exemption: skip ban checks if user_id matches chat_room.host_id

## Phase 3: Frontend Migration

### 3a. Remove PIN UI
**File:** `frontend/src/components/JoinChatModal.tsx`
- Remove all PIN state, PIN screen, PIN completion handlers
- Remove `showPinScreen`/`onPinScreenChange` props
- Remove `pinToSubmitRef`, `pinInputRefs`, `pinScreenRef`, `pinOverlayRef`
- Remove PIN-related error handling in `handleJoin`

### 3b. API layer cleanup
**File:** `frontend/src/lib/api.ts`
- Remove `pin` param from `joinChat()` and `refreshSession()`
- Remove `fingerprint` param from: `getMyParticipation()`, `suggestUsername()`, `validateUsername()`, `checkRateLimit()`, `updateMyTheme()`, `toggleReaction()`
- Keep `fingerprint` on `joinChat()` only (ban data collection)
- Session cookie sent automatically via `withCredentials: true` on axios

### 3c. usernameStorage.ts
**File:** `frontend/src/lib/usernameStorage.ts`
- Remove fingerprint-based username lookup/save (the fallback API call)
- Keep localStorage/sessionStorage as primary username cache
- Move `getFingerprint()` to a separate `frontend/src/lib/fingerprint.ts` utility

### 3d. page.tsx changes
**File:** `frontend/src/app/chat/[username]/[...code]/page.tsx`
- Remove `showPinScreen` state and popstate PIN handling
- Remove PIN error detection in `handleJoinChat`
- Remove `pin` param from `handleJoinChat` and `onJoin` prop
- Remove fingerprint from non-join API calls
- Keep `getFingerprint()` at join time for ban data

### 3e. Ban tier UI
**File:** `frontend/src/components/MessageActionsModal.tsx` (or block action component)
- When host blocks a user, show tier selector:
  - "Ban this session" (default)
  - "Ban device + IP"
  - "Ban IP address"
- Send `ban_tier` to `block-user/` endpoint

## Phase 4: Cleanup (after transition period)

- Delete `AnonymousPIN` model + migration
- Delete `AnonymousUserFingerprint` model + migration
- Remove `FingerprintUsernameView` entirely
- Remove fingerprint fallback logic from all views
- Remove `ANON_PIN_MAX_ATTEMPTS`, `ANON_PIN_LOCKOUT_MINUTES` constance settings
- Clean up old Redis keys (`generated_for_fingerprint:*`)
- Update tests

## Files Modified (Summary)

| File | Changes |
|------|---------|
| `backend/chats/models.py` | Add session_key to 4 models, add ban_tier to ChatBlock |
| `backend/chats/migrations/0005_*.py` | New schema migration |
| `backend/chatpop/settings.py` | Add session config settings |
| `backend/chats/utils/security/auth.py` | Add session_key to JWT, remove PIN verification |
| `backend/chats/utils/security/blocking.py` | 3-tier ban system, host exemption |
| `backend/chats/views.py` | ~12 views: session_key-primary lookups, remove PIN, ban tiers |
| `backend/chats/consumers.py` | session_key from JWT, host exemption |
| `frontend/src/components/JoinChatModal.tsx` | Remove PIN UI entirely |
| `frontend/src/components/MessageActionsModal.tsx` | Ban tier selector for host |
| `frontend/src/app/chat/[username]/[...code]/page.tsx` | Remove PIN state, fingerprint from non-join calls |
| `frontend/src/lib/api.ts` | Remove pin/fingerprint params, keep fingerprint on join only |
| `frontend/src/lib/usernameStorage.ts` | Remove fingerprint username lookup |

## Verification

1. **Anonymous join**: user gets session cookie, joins chat, username persists on reload
2. **Clear cookies**: user gets new session, new username — old identity gone
3. **Session ban**: host bans user → user blocked. User clears cookies → can rejoin (new session)
4. **Fingerprint+IP ban**: host bans user → user blocked. User clears cookies → still blocked (same fingerprint+IP)
5. **Total IP ban**: all anonymous users from that IP blocked, except the host
6. **Host exemption**: host is never affected by any ban type in their own chat
7. **Fingerprint collision**: two users with same fingerprint get different sessions, can coexist without conflict
8. **Logged-in users**: unaffected by all session changes (use auth_token as before)
