# Development & Debugging Scripts

This directory contains utility scripts for development, testing, and debugging the ChatPop application.

## Django Management Commands

These commands are integrated with Django's management system and can be run using `python manage.py <command>`.

### `clear_username_cache`

Clears all username-related Redis keys.

**Usage:**
```bash
./venv/bin/python manage.py clear_username_cache
```

**What it clears:**
- `username:generated_for_fingerprint:*` - Fingerprint tracking
- `username:reserved:*` - Global username reservations
- `username:generation_attempts:*` - Generation attempt counters
- `chat:*:recent_suggestions` - Chat-specific suggestions
- `username_suggest_limit:*` - Per-chat rate limits
- `username:rotation_index:*` - Rotation tracking

**When to use:**
- Reset username generation tracking during development
- Clear rate limits for testing
- Fix username generation issues

---

### `create_test_data`

Creates comprehensive test data for development including users, subscriptions, chat rooms, and messages.

**Usage:**
```bash
./venv/bin/python manage.py create_test_data
```

**What it creates:**
- **Superuser:** admin@chatpop.app (password: demo123)
- **Test Users:** jane@chatpop.app, john@chatpop.app, alice@chatpop.app, bob@chatpop.app (all password: demo123)
- **Subscriptions:** Alice → Jane, Bob → Jane, Alice → John
- **Chat Rooms:**
  - "Tech Talk Tuesday" (public chat)
  - "VIP Community" (private chat, access code: VIP2024)
- **Initial Messages:** Welcome messages and conversation starters

**When to use:**
- Initial development setup
- Setting up a fresh test environment
- Testing user subscription features

---

### `populate_chat`

Populates a specific chat room with a variety of test messages.

**Usage:**
```bash
./venv/bin/python manage.py populate_chat <CHAT_CODE>
```

**Example:**
```bash
./venv/bin/python manage.py populate_chat ABC123XY
```

**What it creates:**
- 3 HOST messages
- 2 PINNED messages from logged-in users
- 2 PINNED messages from anonymous users
- 5 REGULAR messages from logged-in users
- 10 REGULAR messages from anonymous users
- 6 mixed conversation messages

**Test users created:**
- testuser1@test.com (password: demo123)
- testuser2@test.com (password: demo123)
- testuser3@test.com (password: demo123)

**When to use:**
- Testing chat UI with various message types
- Testing message pinning functionality
- Testing host vs regular message display
- Testing anonymous vs logged-in user messages

---

## Debug Tools

These are standalone Python scripts for inspecting Redis data and debugging username generation issues.

### `debug/inspect_redis_usernames.py`

Inspects all username-related Redis data for a specific chat.

**Usage:**
```bash
DJANGO_SETTINGS_MODULE=chatpop.settings ./venv/bin/python scripts/debug/inspect_redis_usernames.py <CHAT_CODE>
```

**Example:**
```bash
DJANGO_SETTINGS_MODULE=chatpop.settings ./venv/bin/python scripts/debug/inspect_redis_usernames.py REWO30UI
```

**What it shows:**
- Constance configuration values (max attempts, rotation limits, etc.)
- Chat-specific recent suggestions
- Fingerprints with generated usernames
- Generation attempts and TTLs
- Per-chat rate limits
- Rotation indices
- Reserved usernames (global)

**When to use:**
- Debugging username generation failures
- Inspecting rate limit state for a chat
- Understanding why a username was suggested/rejected
- Troubleshooting fingerprint tracking

---

### `debug/list_all_username_keys.py`

Lists ALL Redis keys related to username generation/reservation across the entire system.

**Usage:**
```bash
DJANGO_SETTINGS_MODULE=chatpop.settings ./venv/bin/python scripts/debug/list_all_username_keys.py
```

**Key patterns searched:**
- `username:*`
- `chat:*:recent_suggestions`
- `username_suggest_limit:*`

**When to use:**
- Getting a system-wide view of username tracking
- Debugging cross-chat username issues
- Understanding Redis key structure
- Identifying orphaned keys

---

## Test Suites

Integration and security test suites are located in `chats/tests/`:

### `chats/tests/tests_blocking_e2e.py`

End-to-end test suite for user blocking feature.

**Tests:**
- User registration and authentication
- Blocking/unblocking users via API
- PostgreSQL persistence
- Redis caching
- WebSocket message filtering
- Real-time block updates via WebSocket

**Run:**
```bash
./venv/bin/python manage.py test chats.tests.tests_blocking_e2e
```

---

### `chats/tests/tests_blocking_adversarial.py`

Security-focused adversarial test suite designed to expose vulnerabilities.

**Attack vectors tested:**
- Case sensitivity bypass
- Unicode/homoglyph attacks
- Whitespace manipulation
- SQL injection attempts
- Token forgery/manipulation
- Rate limiting bypass
- Cross-user data leakage
- Authorization bypass
- Race conditions
- Username enumeration

**Run:**
```bash
./venv/bin/python manage.py test chats.tests.tests_blocking_adversarial
```

**Note:** These tests are designed to FAIL if vulnerabilities are found. Passing tests mean the system is secure against these attack vectors.

---

## Tips

**View all available management commands:**
```bash
./venv/bin/python manage.py help
```

**Get help for a specific command:**
```bash
./venv/bin/python manage.py help populate_chat
```

**Running multiple commands in sequence:**
```bash
# Fresh test environment setup
./venv/bin/python manage.py clear_username_cache
./venv/bin/python manage.py create_test_data
# Get a chat code from the output, then:
./venv/bin/python manage.py populate_chat <CHAT_CODE>
```

**Debugging Redis issues:**
```bash
# First, list all username keys to see what exists
DJANGO_SETTINGS_MODULE=chatpop.settings ./venv/bin/python scripts/debug/list_all_username_keys.py

# Then, inspect a specific chat
DJANGO_SETTINGS_MODULE=chatpop.settings ./venv/bin/python scripts/debug/inspect_redis_usernames.py <CHAT_CODE>

# If needed, clear everything
./venv/bin/python manage.py clear_username_cache
```
