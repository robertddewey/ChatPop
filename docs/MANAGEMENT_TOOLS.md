# Management Tools

ChatPop includes several Django management commands for inspecting, debugging, and maintaining the application.

## Table of Contents

- [Redis Cache Inspector](#redis-cache-inspector)
  - [List All Caches](#list-all-caches)
  - [Inspect Specific Chat](#inspect-specific-chat)
  - [Show Messages](#show-messages)
  - [Show Reactions](#show-reactions)
  - [Compare Cache vs Database](#compare-cache-vs-database)
  - [Clear Cache](#clear-cache)
  - [Monitor Real-Time](#monitor-real-time)
  - [Show Statistics](#show-statistics)

---

## Redis Cache Inspector

**Command:** `inspect_redis`
**Location:** `backend/chats/management/commands/inspect_redis.py`

Inspect and debug Redis message cache, including messages, pinned messages, backroom messages, and reaction caches.

### List All Caches

List all chat caches currently in Redis:

```bash
./venv/bin/python manage.py inspect_redis --list
```

**Output Example:**
```
📦 Redis Chat Caches:

  chat:ZCMLY634:messages (150 messages, TTL: 23h 45m)
  chat:ZCMLY634:pinned (2 messages, TTL: 6d 23h)
  chat:ZCMLY634:reactions:550e8400-e29b-41d4-a716-446655440000 (TTL: 23h 45m)
```

### Inspect Specific Chat

Get detailed information about a specific chat's cache:

```bash
./venv/bin/python manage.py inspect_redis --chat ZCMLY634
```

**Output Example:**
```
🔍 Chat: ZCMLY634 (Movie Discussion)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📨 Main Messages (150 cached)
  Key: chat:ZCMLY634:messages
  TTL: 23h 45m
  Oldest: 2025-01-11T14:30:00.000Z
  Newest: 2025-01-12T10:15:30.500Z

📌 Pinned Messages (2 cached)
  Key: chat:ZCMLY634:pinned
  TTL: 6d 23h

🏠 Backroom Messages (0 cached)
  Key: chat:ZCMLY634:backroom
  [Empty]

😀 Reaction Caches
  Pattern: chat:ZCMLY634:reactions:*
  Count: 15 messages with cached reactions
  TTL: 23h 45m
```

### Show Messages

Display the actual cached messages:

```bash
./venv/bin/python manage.py inspect_redis --chat ZCMLY634 --show-messages --limit 20
```

**Output Example:**
```
📨 Last 10 Messages in Redis:

[2025-01-12 10:10:00] alice (VERIFIED ✓)
  "I loved that movie! The ending was perfect."
  📌 Pinned ($5.00)

[2025-01-12 10:12:15] bob
  "Agreed! Can't wait for the sequel."

[2025-01-12 10:15:30] charlie (HOST 👑)
  "Thanks everyone for joining the discussion!"
```

### Show Reactions

Display cached emoji reactions for messages:

```bash
./venv/bin/python manage.py inspect_redis --chat ZCMLY634 --show-reactions --limit 10
```

**Output Example:**
```
😀 Reaction Cache Details (showing up to 10):

Message ID: 550e8400-e29b-41d4-a716-446655440000
  From: alice
  Content: "I loved that movie! The ending was perfect."
  Reactions: 👍 (12), ❤️ (8), 😂 (3)

Message ID: 6ba7b810-9dad-11d1-80b4-00c04fd430c8
  From: bob
  Content: "Agreed! Can't wait for the sequel."
  Reactions: 👍 (5), 🔥 (2)
```

### Compare Cache vs Database

Compare Redis cache with PostgreSQL to check sync status:

```bash
./venv/bin/python manage.py inspect_redis --chat ZCMLY634 --compare
```

**Output Example:**
```
🔄 PostgreSQL vs Redis Comparison:

PostgreSQL: 500 messages
Redis:      150 messages
Difference: 350 messages

Latest in PostgreSQL: 2025-01-12T10:15:30.500Z (id: abc-123)
Latest in Redis:      2025-01-12T10:15:30.500Z (id: abc-123)
Sync Status:          ✓ Up to date

Missing in Redis:     0 messages
Extra in Redis:       0 messages
```

### Inspect Specific Message

Inspect a single message by ID:

```bash
./venv/bin/python manage.py inspect_redis --message 550e8400-e29b-41d4-a716-446655440000
```

**Output Example:**
```
🔍 Message: 550e8400-e29b-41d4-a716-446655440000

PostgreSQL:
  ✓ Found
  Type: normal
  Username: alice
  Content: "I loved that movie!"
  Created: 2025-01-12 10:10:00+00:00

Redis:
  ✓ Found in chat:ZCMLY634:messages
  Serialized data:
    {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "username": "alice",
        "username_is_reserved": true,
        "content": "I loved that movie!",
        ...
    }
```

### Clear Cache

Clear all Redis cache for a specific chat:

```bash
# With confirmation prompt
./venv/bin/python manage.py inspect_redis --chat ZCMLY634 --clear

# Force clear without confirmation
./venv/bin/python manage.py inspect_redis --chat ZCMLY634 --clear --force
```

**Output Example:**
```
⚠️  About to clear Redis cache for chat ZCMLY634:
  - chat:ZCMLY634:messages (150 messages)
  - chat:ZCMLY634:pinned (2 messages)

Are you sure? [y/N]: y

✓ Cleared 2 keys:
  - chat:ZCMLY634:messages (150 messages)
  - chat:ZCMLY634:pinned (2 messages)
```

### Monitor Real-Time

Monitor cache changes in real-time (press Ctrl+C to stop):

```bash
./venv/bin/python manage.py inspect_redis --chat ZCMLY634 --monitor
```

**Output Example:**
```
🔴 Monitoring chat:ZCMLY634:messages (Press Ctrl+C to stop)

10:15:30 | 150 messages | TTL: 23h 45m
10:15:32 | 151 messages | TTL: 23h 59m  ← NEW MESSAGE (+1)
10:15:34 | 151 messages | TTL: 23h 59m
10:15:36 | 150 messages | TTL: 23h 59m  ← DELETED (-1)
```

### Show Statistics

Display overall Redis statistics across all chats:

```bash
./venv/bin/python manage.py inspect_redis --stats
```

**Output Example:**
```
📊 Redis Statistics:

Total chats cached:     25
Total messages cached:  3,450
Pinned message caches:  8
Backroom caches:        3
Reaction caches:        127

Max messages per cache: 500
Default TTL:            24 hours
```

---

## Usage Patterns

### Debugging Cache Issues

1. Check if chat exists in cache:
   ```bash
   ./venv/bin/python manage.py inspect_redis --list
   ```

2. Inspect specific chat for anomalies:
   ```bash
   ./venv/bin/python manage.py inspect_redis --chat ZCMLY634
   ```

3. Compare with database to find mismatches:
   ```bash
   ./venv/bin/python manage.py inspect_redis --chat ZCMLY634 --compare
   ```

4. Clear cache if corrupted:
   ```bash
   ./venv/bin/python manage.py inspect_redis --chat ZCMLY634 --clear --force
   ```

### Monitoring Production

1. Check overall health:
   ```bash
   ./venv/bin/python manage.py inspect_redis --stats
   ```

2. Monitor active chat in real-time:
   ```bash
   ./venv/bin/python manage.py inspect_redis --chat ZCMLY634 --monitor
   ```

### Investigating Message Issues

1. Check if specific message is cached:
   ```bash
   ./venv/bin/python manage.py inspect_redis --message <message-id>
   ```

2. View recent messages with reactions:
   ```bash
   ./venv/bin/python manage.py inspect_redis --chat ZCMLY634 --show-messages --show-reactions
   ```

---

## Technical Details

### Redis Key Patterns

- **Messages:** `chat:{chat_code}:messages` (sorted set, score = timestamp)
- **Pinned:** `chat:{chat_code}:pinned` (sorted set, score = pinned_until)
- **Backroom:** `chat:{chat_code}:backroom` (sorted set, score = timestamp)
- **Reactions:** `chat:{chat_code}:reactions:{message_id}` (hash, emoji → count)

### Cache Configuration

- **Max Messages:** 500 per chat (configurable via `MESSAGE_CACHE_MAX_COUNT`)
- **TTL:** 24 hours (configurable via `MESSAGE_CACHE_TTL_HOURS`)
- **Pinned TTL:** 7 days
- **Reaction TTL:** 24 hours (matches message TTL)

### Data Source Priority

1. **Read:** Redis first, PostgreSQL fallback
2. **Write:** Dual-write (PostgreSQL + Redis)
3. **Truth:** PostgreSQL is always the source of truth

---

## See Also

- [Redis Cache Architecture](../CLAUDE.md#redis-message-caching-architecture) - System design documentation
- [Message Reaction Cache](../CLAUDE.md#message-reaction-cache-architecture) - Reaction caching details
- [Testing Documentation](./TESTING.md) - Test coverage for cache functionality
