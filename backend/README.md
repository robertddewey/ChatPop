# ChatPop Backend

Django backend for ChatPop - a real-time chat platform with monetization features.

## Architecture Overview

### Message Storage Strategy

ChatPop uses a **hybrid storage architecture** to optimize for both performance and reliability:

#### PostgreSQL (Source of Truth)
- **Purpose**: Permanent message storage and complete message history
- **Usage**:
  - All REST API queries (`GET /api/chats/{code}/messages/`)
  - Message pagination and scrollback
  - Data integrity and long-term persistence
- **Why**: Ensures complete message history with no gaps, reliable pagination, and ACID compliance

#### Redis (WebSocket Broadcast Cache)
- **Purpose**: Temporary cache for real-time WebSocket message broadcasting
- **Usage**:
  - WebSocket message broadcast to connected clients
  - Dual-write on message send (PostgreSQL + Redis)
  - Sliding window of last 500 messages (24-hour TTL)
- **Why**: Instant message delivery to active chat participants, reduces PostgreSQL load for real-time updates

### Message Flow

#### 1. Sending a Message (WebSocket)
```
User → WebSocket → Django Channels Consumer
                         ↓
                    PostgreSQL (save)
                         ↓
                    Redis (cache)
                         ↓
                    Broadcast to all WebSocket clients
```

**Implementation**: `chats/consumers.py:68-88`
- Saves message to PostgreSQL (authoritative)
- Caches to Redis (dual-write pattern)
- Broadcasts from Redis to all connected clients

#### 2. Loading Messages (REST API)
```
User → REST API → Django View
                      ↓
                 PostgreSQL (query)
                      ↓
                 Return messages
```

**Implementation**: `chats/views.py:264-267`
- Always queries PostgreSQL directly
- No Redis lookup (prevents cache gaps/incomplete history)
- Supports infinite scrollback with pagination

#### 3. Real-Time Updates (Active Chat)
```
WebSocket Connected → New message arrives
                           ↓
                      Redis broadcast
                           ↓
                      Instant delivery to client
```

**Why This Works**:
- Active chat users receive messages via WebSocket (fast, Redis-backed)
- Page refreshes/new users load from PostgreSQL (complete, reliable)
- No message loss, no complexity, minimal performance impact

### Key Design Decisions

**Q: Why not use Redis for REST API queries?**

A: Redis is a **sliding window cache** (last 500 messages). If a chat has 1000 messages:
- Redis: Messages 501-1000 ✅
- PostgreSQL: Messages 1-1000 ✅

If REST API used Redis:
- Initial load: Returns messages 951-1000 ✅
- User scrolls back to message 400: **Cache miss** → returns incomplete results ❌

By always using PostgreSQL for REST API, we guarantee complete history.

**Q: What about performance?**

- PostgreSQL queries: ~5-20ms with proper indexing (acceptable for page load/pagination)
- WebSocket broadcast: ~1ms via Redis (critical for real-time feel)
- Most active users get messages via WebSocket (not REST API)
- REST API is only used for: page refresh, new user join, history scrollback (infrequent operations)

### Configuration

**Redis Settings** (`settings.py`):
```python
MESSAGE_CACHE_MAX_COUNT = 500  # Max messages in Redis per chat
MESSAGE_CACHE_TTL_HOURS = 24   # Auto-expire after 24 hours
```

**Redis Keys**:
- `chat:{chat_code}:messages` - Main chat messages (sorted set)
- `chat:{chat_code}:backroom:messages` - Back room messages (sorted set)
- `chat:{chat_code}:pinned` - Pinned messages (sorted set with expiry)

## Development

### Running Tests

```bash
# Quick start - run all tests
./run_tests.sh

# Generate and view HTML report
./run_tests.sh --open

# See all options
./run_tests.sh --help
```

For complete testing documentation, see **[docs/TESTING.md](../docs/TESTING.md)**.

### Inspecting Redis Cache
```bash
# View cached messages for a chat
./venv/bin/python manage.py inspect_redis --chat CHATCODE --show-messages

# View cache statistics
./venv/bin/python manage.py inspect_redis --chat CHATCODE
```

## WebSocket Integration

### Frontend Connection
```typescript
// WebSocket URL format
ws://localhost:9000/ws/chat/{chatCode}/?session_token={token}

// Message format (send)
{
  "message": "Hello world",
  "session_token": "jwt_token_here"
}

// Message format (receive)
{
  "id": "uuid",
  "chat_code": "ABC123",
  "username": "alice",
  "content": "Hello world",
  "created_at": "2024-01-01T12:00:00Z",
  ...
}
```

### Auto-Reconnection
The frontend WebSocket hook (`useChatWebSocket.ts`) automatically reconnects up to 5 times with 2-second delay on connection failure.

## Database Models

### Message
- `id` (UUID) - Primary key
- `chat_room` (FK) - Associated chat room
- `user` (FK, nullable) - Logged-in user (if any)
- `username` (str) - Display username
- `content` (text) - Message text
- `message_type` (str) - normal/host/system
- `reply_to` (FK, nullable) - Reply to another message
- `is_pinned` (bool) - Pinned status
- `created_at` (datetime) - Timestamp (used for ordering and pagination)

**Indexes**:
- `(chat_room, created_at)` - For pagination queries
- `(chat_room, is_pinned)` - For pinned message lookups

## See Also

### Documentation
- **[CLAUDE.md](../CLAUDE.md)** - Full project documentation and development guidelines
- **[docs/TESTING.md](../docs/TESTING.md)** - Testing framework and Allure reports
- **[docs/CACHING.md](../docs/CACHING.md)** - Redis message and reaction caching architecture
- **[docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)** - Dual sessions, username validation, IP rate limiting

### Source Code
- [chats/redis_cache.py](chats/redis_cache.py) - Redis cache implementation
- [chats/consumers.py](chats/consumers.py) - WebSocket consumer implementation
- [chats/views.py](chats/views.py) - REST API views
