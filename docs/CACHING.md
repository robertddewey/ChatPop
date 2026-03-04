# Redis Caching Architecture

ChatPop uses a **hybrid Redis/PostgreSQL storage strategy** to optimize real-time chat performance while maintaining data persistence and integrity.

**Key Principle:** PostgreSQL is the source of truth, Redis is the fast cache for recent data.

---

## Table of Contents

1. [Message Caching Architecture](#message-caching-architecture)
2. [Filter Index Architecture](#filter-index-architecture)
3. [Reaction Caching Architecture](#reaction-caching-architecture)
4. [Performance Characteristics](#performance-characteristics)
5. [Configuration](#configuration)
6. [Monitoring & Debugging](#monitoring--debugging)

---

## Message Caching Architecture

### Overview

ChatPop caches recent messages in Redis for fast delivery while storing all messages permanently in PostgreSQL.

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

**On Message Send (Conditional Dual-Write Pattern):**
1. User sends message via WebSocket
2. **Write to PostgreSQL** (permanent record, includes all fields)
3. **Conditionally write to Redis** (only if `REDIS_CACHE_ENABLED=True`)
4. Broadcast to all connected clients via WebSocket

**On Message Load (Conditional Read-First Pattern with Cache Backfill & Partial Cache Hits):**
1. Frontend requests recent messages (GET `/api/chats/{code}/messages/?limit=50`)
2. **Check Constance setting** (`REDIS_CACHE_ENABLED`)
3. If enabled: **Check Redis first** (sorted set with timestamp scores)
4. **Partial Cache Hit Detection:** If cache has fewer messages than requested (e.g., cache has 30, request is 50):
   - Use the 30 messages from cache
   - Fetch remaining 20 messages from PostgreSQL (before oldest cached timestamp)
   - Merge results (older messages prepended to cached messages)
   - Return combined result with source indicator: `"hybrid_redis_postgresql"`
5. **Full Cache Miss:** If Redis has 0 messages, fallback to PostgreSQL and backfill cache
6. **Cache Hit:** If cache has enough messages, return from Redis only
7. Return messages with source indicator:
   - `"redis"` - All messages from cache
   - `"postgresql"` - Direct PostgreSQL query (pagination or cache disabled)
   - `"postgresql_fallback"` - Cache miss with automatic backfill
   - `"hybrid_redis_postgresql"` - Partial cache hit (cache + database)

### Redis Data Structures

**Note:** Keys use the room UUID (not chat code) to avoid collisions between rooms with the same code owned by different users.

**Message Data (Hash):**
```
Key: room:{room_id}:msg_data
Type: Hash (HSET)
Field: message_id (UUID string)
Value: JSON message object
TTL: 24 hours (refreshed on each write)
```

**Timeline Index (Sorted Set):**
```
Key: room:{room_id}:timeline
Type: Sorted Set (ZADD)
Score: Unix timestamp
Member: message_id (UUID string)
TTL: 24 hours
```

**Filter Indexes (Sorted Sets):**
```
room:{room_id}:idx:host             → Host messages
room:{room_id}:idx:focus:{username}  → Per-user focus view (own messages + replies to them + host messages they triggered)
room:{room_id}:idx:gifts             → All gift messages
room:{room_id}:idx:gifts:{username}  → Per-user gifts (sent + received)
```

**Pinned Messages:**
```
Key: room:{room_id}:pinned:{message_id}  → Individual pinned message data
Key: room:{room_id}:pinned_order          → Pin ordering (score = pin_amount_paid)
```

**Reaction Caches:**
```
Key: room:{room_id}:reactions:{message_id}
Type: Hash (emoji → JSON reaction summary)
TTL: 24 hours
```

This **hash + index** architecture separates message data (stored once in the hash) from chronological ordering and filter routing (stored as lightweight ID references in sorted sets). A message write is a single pipelined operation that writes to the hash, timeline, and all applicable filter indexes atomically.

### Message Serialization

Messages in Redis include all fields needed by the frontend, including badge status, avatar URLs, gift metadata, and media URLs:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "chat_code": "ABC123",
  "username": "Robert",
  "username_is_reserved": true,
  "user_id": "42",
  "message_type": "normal",
  "is_from_host": false,
  "content": "Hello everyone!",
  "reply_to_id": null,
  "reply_to_message": null,
  "is_pinned": false,
  "pinned_at": null,
  "sticky_until": null,
  "pin_amount_paid": "0.00",
  "current_pin_amount": "0.00",
  "avatar_url": "https://...",
  "voice_url": null,
  "photo_url": null,
  "video_url": null,
  "gift_recipient": null,
  "is_gift_acknowledged": false,
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

### Implementation Files

**Core Modules:**
- `backend/chats/utils/performance/cache.py` - MessageCache utility class (hash + index architecture)
- `backend/chats/utils/performance/monitoring.py` - Cache monitoring and metrics
- `backend/chats/consumers.py` - WebSocket consumer (dual-write on send)
- `backend/chats/views.py` - MessageListView (Redis-first read with filter routing)

**Key Methods:**
- `MessageCache.add_message()` - Add message to hash + timeline + filter indexes (pipelined)
- `MessageCache.update_message()` - Update message in hash (O(1), no index changes)
- `MessageCache.get_messages()` - Fetch recent messages from timeline → hash
- `MessageCache.get_messages_before()` - Pagination via timeline index
- `MessageCache.get_focus_messages()` - Merge user focus index + host index
- `MessageCache.get_gift_messages()` - Read from gifts index (all or per-user)
- `MessageCache.add_pinned_message()` - Cache pinned message
- `MessageCache.get_pinned_messages()` - Fetch active pins (auto-expires)
- `MessageCache.remove_message()` - Remove from hash, timeline, all indexes, pinned, reactions
- `MessageCache.clear_room_cache()` - SCAN and delete all `room:{id}:*` keys
- `MessageListView._backfill_cache()` - Automatically populate cache on miss (internal)

### Edge Cases & Error Handling

**Redis Failure:**
- Write errors: Log but don't crash (PostgreSQL has the data)
- Read errors: Automatic fallback to PostgreSQL
- No impact on data integrity (PostgreSQL is source of truth)

**Cache Inconsistency & Automatic Backfill:**
- Redis cleared: PostgreSQL automatically backfills on next read (first user sees `postgresql_fallback`, all subsequent users see `redis`)
- New messages added while cache disabled: Automatically backfilled when cache is re-enabled
- Message edited: Update both stores (dual-write)
- Message deleted: Remove from both stores

**Cache Backfill Behavior:**
- Triggered automatically on cache miss during initial page load (not pagination)
- Fetches messages from PostgreSQL and populates Redis cache
- Subsequent requests hit the cache (no repeated misses)
- Prevents thundering herd problem when cache expires or is cleared

**Partial Cache Hit Detection (Industry-Standard Pattern):**

When the cache contains fewer messages than requested, the system intelligently combines cached and database data in a single request:

**Example Scenario:**
```
- Cache contains: 30 most recent messages
- User requests: 50 messages
- System behavior:
  1. Fetches 30 messages from Redis (newest messages)
  2. Extracts oldest cached timestamp (message #21's created_at)
  3. Queries PostgreSQL for 20 messages BEFORE that timestamp
  4. Merges results: [20 DB messages] + [30 cached messages]
  5. Returns 50 total messages with source: "hybrid_redis_postgresql"
```

**Performance Benefits:**
- **Hybrid Query (30 cache + 20 DB):** ~17ms  (~50% faster than full DB query)
- **Full DB Query (50 from DB):**            ~34ms
- **Pure Cache (50 from cache):**            ~5ms  (~86% faster than full DB query)

Real-world test results (`chats/tests_partial_cache_hits.py`):
- 30 cache + 20 DB: 16.77ms (50.4% speedup vs full DB)
- Pure cache:       4.77ms  (85.9% speedup vs full DB)

**Why This Matters:**
- Prevents incomplete responses (no "only 30 messages available" errors)
- Optimizes common scenario: User 1 backfills 30 messages, User 2 requests 50
- Industry-standard "Cache-Aside with Partial Fill" pattern (used by Twitter, GitHub, Discord)
- Graceful degradation: Even partial cache hits provide significant performance benefits

**Implementation:** `views.py:297-331` (MessageListView.get)

**Test Coverage:** 8 tests in `chats/tests_partial_cache_hits.py`

**Race Conditions:**
- Use microsecond timestamps for ordering
- PostgreSQL `created_at` matches Redis score
- Ensures consistent message ordering across stores

---

## Filter Index Architecture

### Overview

ChatPop supports **filtered room views** (Focus Mode and Gift History) powered by pre-computed Redis indexes. When a message is written, it is routed to all applicable filter indexes in the same pipelined operation as the main timeline write. This means filter reads are O(1) index lookups — no scanning or filtering at read time.

### Filter Modes

**Focus Mode** (`?filter=focus&filter_username=alice`):
Shows messages relevant to a specific user — their own messages, messages that reply to them, and host messages connected to their conversation threads.

**Gift History** (`?filter=gifts&filter_username=alice`):
Shows gift messages involving a specific user — gifts they sent and gifts they received. Uses the denormalized `gift_recipient` field on the Message model (added in migration 0066) for efficient indexing.

### Fan-Out Routing Logic

When `MessageCache.add_message()` is called, the message is routed to indexes based on its properties:

```
Message arrives
  │
  ├─→ msg_data hash     (always — stores full JSON)
  ├─→ timeline          (always — chronological order)
  │
  ├─→ idx:host          (if message_type == 'host')
  │
  ├─→ idx:focus:{sender}    (always — user sees own messages)
  ├─→ idx:focus:{parent}    (if reply — parent author sees replies to them)
  │   └─→ Also adds PARENT message to focus (if host replied to someone,
  │       so user sees what triggered the host's reply)
  │
  ├─→ idx:gifts              (if message_type == 'gift')
  ├─→ idx:gifts:{sender}     (if gift — sender sees their sent gifts)
  └─→ idx:gifts:{recipient}  (if gift_recipient set — recipient sees received gifts)
```

### Focus Mode Read Path

`get_focus_messages()` merges two indexes:
1. `idx:focus:{username}` — user's personal focus (own messages + replies to them)
2. `idx:host` — all host messages (always visible in focus)

These are combined via `ZUNIONSTORE` into a temporary key, then read with `ZRANGE` for pagination. The temporary key has a 60-second TTL for reuse across rapid page loads.

### Gift History Read Path

`get_gift_messages()` reads from:
- `idx:gifts:{username}` — user-specific gifts (sent + received)
- Falls back to `idx:gifts` — all gifts in the room (if no username specified)

### Eviction & Cleanup

When the timeline exceeds `REDIS_CACHE_MAX_COUNT`, overflow messages are evicted from:
- The message hash (`msg_data`)
- The timeline sorted set
- **All filter indexes** (via `SCAN` for `room:{id}:idx:*` pattern)

`remove_message()` (soft delete) similarly removes from hash, timeline, and all discovered index keys.

### Database Fallback

When Redis cache is disabled or on cache miss, `MessageListView._fetch_from_db()` applies equivalent Django ORM filters:

```python
# Focus mode
queryset.filter(
    Q(message_type='host') |
    Q(username__iexact=filter_username) |
    Q(reply_to__username__iexact=filter_username)
)

# Gift mode
queryset.filter(
    Q(message_type='gift') & (
        Q(username__iexact=filter_username) |
        Q(gift_recipient__iexact=filter_username)
    )
)
```

### Frontend Room Navigation

The frontend uses a unified `currentRoom` state (`'main' | 'focus' | 'gifts' | 'backroom'`) to manage room switching. Room transitions use `history.replaceState()` (lateral navigation) while only the Settings overlay uses `pushState()`. Each room switch fetches fresh messages from the API with the appropriate `?filter=` parameter — no client-side firehose caching.

---

## Reaction Caching Architecture

### Overview

Message reactions (emoji reactions on chat messages) use a **separate Redis cache** alongside the main message cache to achieve optimal performance and scalability.

**Key Principle:** Reactions are stored in PostgreSQL for persistence, and cached separately in Redis for fast batch retrieval.

### Architecture Rationale

**Problem Identified:**
- N+1 query problem: Loading 50 messages = 51 database queries (1 for messages + 50 for reactions)
- Estimated 500ms load time for 50 messages
- System cannot scale beyond ~100 concurrent users
- Reactions on cached messages become stale without cache invalidation

**Solution: Separate Reaction Cache**
- Create dedicated Redis keys per message for reaction summaries
- Use pipelined batch fetching to load reactions for multiple messages in one round-trip
- Update cache immediately when reactions change
- Broadcast full reaction summary via WebSocket for real-time updates
- 24-hour TTL with PostgreSQL fallback on cache miss

### Redis Data Structure

**Reaction Cache Keys:**
```
Key: room:{room_id}:reactions:{message_id}
Type: Redis Hash
Fields: emoji → JSON reaction summary
TTL: 24 hours
```

**Example:**
```redis
HSET room:abc123-uuid:reactions:550e8400-uuid
  "👍" '{"emoji":"👍","count":5,"users":["alice","bob"]}'
  "❤️" '{"emoji":"❤️","count":3,"users":["charlie"]}'
```

### Data Flow Scenarios

#### 1. Initial Message Load (First Page)
```
Frontend: GET /api/chats/{code}/messages/ (limit=50)
Backend:
  1. MessageCache.get_messages() → 50 messages from Redis
  2. MessageCache.batch_get_reactions([msg_ids]) → reactions for all 50 messages (1 pipelined call)
  3. Merge reactions into message objects
  4. Return: messages with reactions
Performance: ~12ms (vs 500ms without cache)
```

#### 2. Infinite Scroll (Load Older Messages)
```
Frontend: GET /api/chats/{code}/messages/?before={timestamp}&limit=50
Backend:
  1. MessageCache.get_messages_before() → next 50 messages
  2. MessageCache.batch_get_reactions([msg_ids]) → reactions (1 pipelined call)
  3. Merge and return
Performance: ~12ms per batch
```

#### 3. Real-Time Reaction Added (WebSocket Broadcast)
```
User clicks emoji → POST /api/chats/{code}/messages/{id}/react/
Backend:
  1. Create/update MessageReaction in PostgreSQL
  2. Update Redis cache: MessageCache.set_message_reactions(msg_id, summary)
  3. Broadcast via WebSocket: {type: 'reaction', action: 'added', message_id, summary: [...]}
Frontend WebSocket handler:
  1. Receive reaction event
  2. Update local state immediately (no API call needed)
Performance: <50ms end-to-end
```

#### 4. Page Refresh
```
Same as Initial Message Load (reactions reload from Redis cache)
Performance: ~12ms
```

#### 5. Cache Miss (Message Older Than 24 Hours)
```
Backend:
  1. MessageCache.batch_get_reactions() returns empty for some messages
  2. Fallback: Query PostgreSQL for missing reactions
  3. Rebuild cache: MessageCache.set_message_reactions()
  4. Return merged data
Performance: ~100ms (PostgreSQL fallback), subsequent loads are fast
```

### Implementation Components

**File: `backend/chats/utils/performance/cache.py`**

Reaction methods on `MessageCache` class:

```python
@classmethod
def set_message_reactions(cls, room_id, message_id, reactions) -> bool:
    """Cache reaction summary for a message (room:{id}:reactions:{msg_id})."""

@classmethod
def get_message_reactions(cls, room_id, message_id) -> List[Dict]:
    """Get cached reactions for a single message. Empty list on cache miss."""

@classmethod
def batch_get_reactions(cls, room_id, message_ids) -> Dict[str, List[Dict]]:
    """Batch fetch reactions for multiple messages using Redis pipeline."""
```

**File: `backend/chats/views.py`**

Updated views:
- `MessageListView`: Calls `batch_get_reactions()` after fetching messages
- `MessageReactionToggleView`: Updates cache after modifying reaction in PostgreSQL

**File: `backend/chats/consumers.py`**

WebSocket consumer broadcasts full reaction summary (not just emoji) to enable instant frontend updates without API calls.

### Frontend WebSocket Integration

Reactions are fully implemented in the frontend with real-time WebSocket updates.

#### WebSocket Event Format

The backend broadcasts reaction updates via WebSocket:

```json
{
  "type": "reaction",
  "action": "added",
  "message_id": "550e8400-uuid",
  "emoji": "👍",
  "username": "alice",
  "summary": [
    {"emoji": "👍", "count": 5, "has_reacted": true},
    {"emoji": "❤️", "count": 3, "has_reacted": false}
  ]
}
```

#### Data Flow

1. User taps emoji → `POST /api/chats/{code}/messages/{id}/react/` with optimistic UI update
2. Backend toggles reaction in PostgreSQL + updates Redis cache
3. WebSocket broadcasts `summary` to all connected clients
4. Frontend updates `messageReactions` state from WebSocket event (no additional API call)
5. On page load, reactions are batch-fetched via `MessageCache.batch_get_reactions()` (single pipelined Redis call)

### Cache Invalidation Strategy

**When to Update Cache:**
1. **Reaction Added:** Immediately update Redis + broadcast
2. **Reaction Removed:** Immediately update Redis + broadcast
3. **Reaction Changed:** Immediately update Redis + broadcast
4. **Message Deleted:** Remove reaction cache key (see Message Deletion below)
5. **Cache Expired:** Rebuild from PostgreSQL on next access

**Consistency Guarantee:**
- PostgreSQL is source of truth
- Redis cache can be cleared anytime (auto-rebuilds from PostgreSQL)
- Cache misses are transparent to frontend (slower but correct)

---

## Message Deletion & Cache Invalidation

### Overview

When messages are soft-deleted (marked with `is_deleted=True`), the Redis cache must be immediately cleared to prevent deleted messages from appearing via cached data.

**Key Principle:** Message deletion triggers comprehensive cache cleanup across all related cache layers (messages, pinned messages, reactions).

### Cache Invalidation Flow

**On Message Delete (Host-Only Action):**
1. User (host) long-presses message → "Delete Message" option
2. Frontend calls `POST /api/chats/{code}/messages/{message_id}/delete/` with session token
3. Backend validates authorization (host + valid session)
4. **Soft delete:** Set `is_deleted=True` in PostgreSQL (message preserved for audit)
5. **Cache invalidation:** Call `MessageCache.remove_message(chat_code, message_id)`
6. **WebSocket broadcast:** Notify all connected clients via `{type: 'message_deleted', message_id}`
7. Frontend removes message from local state immediately

### Multi-Layer Cache Cleanup

`MessageCache.remove_message()` performs **complete cache cleanup** across three layers:

```python
@classmethod
def remove_message(cls, chat_code: str, message_id: str) -> bool:
    """
    Remove a specific message from cache (for soft deletes).

    This removes the message from:
    1. Main messages cache (chat:{code}:messages)
    2. Pinned messages cache (chat:{code}:pinned) - if pinned
    3. Reactions cache (chat:{code}:reactions:{message_id})
    """
```

**Layer 1: Message Hash + Timeline**
```
Key: room:{room_id}:msg_data  → HDEL (remove from hash)
Key: room:{room_id}:timeline  → ZREM (remove from sorted set)
Why: Prevents deleted message from appearing in message list
```

**Layer 2: All Filter Indexes**
```
Keys: room:{room_id}:idx:*  → ZREM from all matching indexes (via SCAN)
Why: Prevents deleted message from appearing in Focus or Gift views
```

**Layer 3: Pinned Messages Cache**
```
Key: room:{room_id}:pinned:{message_id}  → DEL
Key: room:{room_id}:pinned_order          → ZREM
Why: Deleted pinned messages should not remain in sticky UI
```

**Layer 4: Reactions Cache**
```
Key: room:{room_id}:reactions:{message_id}  → DEL
Why: Reactions for deleted messages are no longer relevant
```

### Real-Time WebSocket Updates

**Backend Broadcast (`views.py:1606-1612`):**
```python
# Broadcast deletion event via WebSocket
channel_layer = get_channel_layer()
room_group_name = f'chat_{code}'
async_to_sync(channel_layer.group_send)(
    room_group_name,
    {
        'type': 'message_deleted',
        'message_id': str(message_id)
    }
)
```

**Frontend Handler (`useChatWebSocket.ts`):**
```typescript
// Handle message deletion events
if (data.type === 'message_deleted') {
  console.log('[WebSocket] Message deleted event received:', data.message_id);
  if (onMessageDeleted) {
    onMessageDeleted(data.message_id);  // Remove from local state
  }
  return;
}
```

**UI Update (`page.tsx`):**
```typescript
const handleMessageDeleted = useCallback((messageId: string) => {
  // Remove message from local state
  setMessages(prev => prev.filter(msg => msg.id !== messageId));

  // Remove reactions for this message
  setMessageReactions(prev => {
    const updated = { ...prev };
    delete updated[messageId];
    return updated;
  });
}, []);
```

### Authorization & Security

**Only chat hosts can delete messages:**
- Session token validation enforced via `ChatSessionValidator`
- Host status verified: `request.user == chat_room.host`
- Cross-chat protection: Session token must match chat code
- Authenticated users only (Django REST Framework authentication)

**See:** `views.py:MessageDeleteView` for full implementation

### Soft Delete Pattern

**Database Behavior:**
- `is_deleted` flag set to `True` (message preserved for audit trails)
- All message data preserved (content, username, timestamp, etc.)
- Message count unchanged (soft delete doesn't remove records)
- Idempotent: Deleting already-deleted message returns success

**Query Filtering:**
- Message list views filter `is_deleted=False` by default
- Deleted messages excluded from API responses
- PostgreSQL retains full history for compliance/recovery

### Error Handling & Graceful Degradation

**Redis Failure During Deletion:**
- Database deletion succeeds even if Redis cache removal fails
- PostgreSQL is source of truth - cache failures are non-fatal
- Deleted messages won't reappear from PostgreSQL queries (filtered by `is_deleted`)
- Cache will self-heal on next rebuild (expired cache → PostgreSQL backfill → cache excludes deleted messages)

**Edge Cases:**
- **Message not in cache:** `remove_message()` returns `False` but deletion succeeds
- **Message already deleted:** Returns `{success: true, already_deleted: true}`
- **Non-existent message:** Returns 404 Not Found
- **Wrong chat code:** Returns 404 Not Found (message not found in specified chat)
- **Inactive chat:** Returns 404 Not Found (chat not accessible)

### Implementation Files

**Backend:**
- `backend/chats/utils/performance/cache.py` - `MessageCache.remove_message()` (hash + timeline + all indexes + pinned + reactions)
- `backend/chats/views.py` - `MessageDeleteView` (API endpoint)
- `backend/chats/consumers.py` - WebSocket `message_deleted` handler

**Frontend:**
- `frontend/src/lib/api.ts` - `deleteMessage()` API method
- `frontend/src/hooks/useChatWebSocket.ts` - WebSocket event handler
- `frontend/src/app/chat/[username]/[code]/page.tsx` - `handleMessageDeleted()` state update
- `frontend/src/components/MessageActionsModal.tsx` - Delete UI with confirmation

### Testing

**Test Coverage:** 22 tests in `chats/tests_message_deletion.py`

**Test Classes:**
1. `MessageDeletionAuthorizationTests` (7 tests) - Host-only access, session validation
2. `MessageSoftDeletionTests` (6 tests) - `is_deleted` flag, data preservation
3. `MessageCacheInvalidationTests` (4 tests) - Multi-layer cache cleanup
4. `MessageDeletionWebSocketTests` (2 tests) - Real-time broadcasting
5. `MessageDeletionEdgeCasesTests` (5 tests) - Error handling, edge cases

**Key Tests:**
- `test_cache_invalidation_removes_message_from_messages_cache`
- `test_cache_invalidation_removes_message_from_pinned_cache`
- `test_cache_invalidation_removes_reactions_cache`
- `test_deletion_succeeds_even_if_cache_removal_fails`

**Run Tests:**
```bash
./venv/bin/python manage.py test chats.tests_message_deletion
```

**See:** [docs/TESTING.md](./TESTING.md) - Section 7 for detailed test documentation

---

## Performance Characteristics

### Message Caching

**Expected Latencies:**
- **Message Send:** ~25ms (5ms Redis + 20ms PostgreSQL)
- **Load Recent (Redis hit):** ~5ms (pure cache)
- **Load Recent (Partial cache hit - 30 cache + 20 DB):** ~17ms (~50% faster than full DB)
- **Load Recent (PostgreSQL fallback):** ~34ms (full DB query)
- **WebSocket Broadcast:** <2ms (reads from Redis)
- **Scroll Pagination (Redis):** <2ms
- **Scroll Pagination (PostgreSQL):** <100ms

**Cache Hit Rates:**
- **Active Chats:** ~95-99% (most loads from Redis)
- **Partial Cache Hits:** ~5-15% (cache has fewer messages than requested)
- **Inactive Chats:** ~0-50% (depends on message age)

**Partial Cache Hit Performance:**
- **Scenario:** Cache has 30 messages, user requests 50
- **Hybrid Query Time:** 16.77ms (30 from cache + 20 from DB)
- **Speedup vs Full DB:** 50.4% faster
- **Why It Matters:** Prevents incomplete responses while maintaining performance benefits

### Reaction Caching

**Before Caching:**
- 50 messages: ~500ms (51 queries)
- 100 messages: ~1000ms (101 queries)
- Scalability: ~100 concurrent users max

**After Caching:**
- 50 messages: ~12ms (1 message query + 1 pipelined reaction query)
- 100 messages: ~20ms (2 message queries + 1 pipelined reaction query)
- Scalability: 10,000+ concurrent users

**Improvement:** 40x faster, 100x more scalable

---

## Configuration

### Runtime Configuration (Constance)

**RECOMMENDED:** Use Constance dynamic settings to enable/disable caching without redeployment.

Access via Django admin: `/admin/constance/config/`

```python
# Message History Limits
MESSAGE_HISTORY_MAX_DAYS = 7           # Days of history users can scroll back
MESSAGE_HISTORY_MAX_COUNT = 500        # Max total messages loaded (initial + pagination)
MESSAGE_LIST_DEFAULT_LIMIT = 50        # Default page size for message list (can be overridden with ?limit=)

# Redis Message Cache (enable when scaling past 1000+ chats)
REDIS_CACHE_ENABLED = False            # Enable Redis caching (read + write). 5-10x faster page loads.
REDIS_CACHE_MAX_COUNT = 500            # Max messages cached per chat (recommended: 100-200)
REDIS_CACHE_TTL_HOURS = 24             # Hours before cached messages expire (auto-cleanup)
```

**Limit Enforcement (Security Feature):**

The `limit` query parameter in message list requests is now **enforced** to prevent abuse:

- **Default:** `MESSAGE_LIST_DEFAULT_LIMIT` (50 messages)
- **User override:** Users can pass `?limit=100` to request more messages
- **Security cap:** System caps requests at `MESSAGE_HISTORY_MAX_COUNT` (500 messages max)
- **Example:** If user requests `?limit=99999`, system automatically caps to 500

This prevents:
- Database overload from massive queries
- Memory issues from serializing huge result sets
- Data scraping of entire chat histories
- Bypassing intended history limits

**Implementation:** `views.py:278-284` (MessageListView.get)

**How It Works:**
- **`REDIS_CACHE_ENABLED=True`:** Writes new messages to Redis AND reads from Redis first
- **`REDIS_CACHE_ENABLED=False`:** PostgreSQL only (no Redis reads or writes)
- **Cache Miss:** Automatic fallback to PostgreSQL (no errors)
- **Reactions:** Always cached (separate from message cache control)

**When to Enable:**
- **Small Scale (< 1000 chats):** Keep `REDIS_CACHE_ENABLED=False` (PostgreSQL is fast enough)
- **Medium Scale (1000-5000 chats):** Enable `REDIS_CACHE_ENABLED=True` for 5-10x faster page loads
- **Large Scale (5000+ chats):** Keep both enabled (required for scaling)

**Performance Impact:**
- PostgreSQL: ~10-15ms per message query
- Redis: ~1-3ms per message query
- Improvement: 5-10x faster initial page loads

### Static Configuration (settings.py)

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

# Message Cache Settings (fallback defaults if Constance not available)
MESSAGE_CACHE_MAX_COUNT = 500  # Max messages per chat in Redis (use Constance to change)
MESSAGE_CACHE_TTL_HOURS = 24   # Auto-expire after 24 hours (use Constance to change)

# Reaction Cache Settings
REACTION_CACHE_TTL_HOURS = 24  # Match message cache TTL
```

**Note:** `MESSAGE_CACHE_MAX_COUNT` and `MESSAGE_CACHE_TTL_HOURS` are now configurable via Constance (see Runtime Configuration above). The values in `settings.py` are only used as fallback defaults if Constance is unavailable.

---

## Monitoring & Debugging

### Cache Health Metrics

**Message Cache:**
- Track `source` field in API responses (`redis` vs `postgresql`)
- Monitor cache hit rate (% of loads from Redis)
- Alert if hit rate drops below 90% for active chats

**Reaction Cache:**
- Track reaction cache hit rate (% of reactions loaded from Redis vs PostgreSQL)
- Monitor reaction load time (should be <20ms for 50 messages)
- Alert if load time exceeds 100ms consistently

### Debug Tools

**Redis CLI Commands:**

```bash
# Inspect message hash (all message data)
redis-cli -p 6381 HLEN room:{room_id}:msg_data

# Inspect timeline (message count)
redis-cli -p 6381 ZCARD room:{room_id}:timeline

# Inspect filter indexes
redis-cli -p 6381 ZCARD room:{room_id}:idx:host
redis-cli -p 6381 ZCARD room:{room_id}:idx:focus:alice
redis-cli -p 6381 ZCARD room:{room_id}:idx:gifts
redis-cli -p 6381 ZCARD room:{room_id}:idx:gifts:alice

# Inspect reactions for a message
redis-cli -p 6381 HGETALL room:{room_id}:reactions:{message_id}

# Check cache TTL
redis-cli -p 6381 TTL room:{room_id}:timeline

# List all keys for a room
redis-cli -p 6381 KEYS "room:{room_id}:*"
```

**Python Management Commands:**

```bash
# Inspect Redis cache (see docs/MANAGEMENT_COMMANDS.md for full usage)
./venv/bin/python manage.py inspect_redis --chat jane/tech-talk-tuesday
./venv/bin/python manage.py inspect_redis --chat jane/tech-talk-tuesday --show-messages
./venv/bin/python manage.py inspect_redis --stats
```

**MessageCache API:**

```python
from chats.utils.performance.cache import MessageCache

# Clear all caches for a room
MessageCache.clear_room_cache(room_id)

# Clear specific message reactions
MessageCache.set_message_reactions(room_id, message_id, [])
```

---

## Edge Cases & Error Handling

**Redis Failure:**
- Write errors: Log but don't crash (PostgreSQL has the data)
- Read errors: Automatic fallback to PostgreSQL
- No impact on data integrity

**Cache Inconsistency:**
- Redis cleared: PostgreSQL backfills on next read
- Reaction edited: Update both stores (dual-write)
- WebSocket broadcast failed: Next page load corrects state

**Race Conditions:**
- Multiple users react simultaneously: PostgreSQL unique constraints prevent duplicates
- Cache updated out of order: Last write wins (eventual consistency acceptable)
- Use microsecond timestamps for message ordering

---

## Related Documentation

- **Testing:** [docs/TESTING.md](./TESTING.md) - Redis cache test suite (49 cache tests + 8 partial hit tests)
- **Architecture:** [docs/ARCHITECTURE.md](./ARCHITECTURE.md) - Overall system design, gift system, filter architecture
- **Management Commands:** [docs/MANAGEMENT_COMMANDS.md](./MANAGEMENT_COMMANDS.md) - `inspect_redis` cache debugging tool
- **Monitoring:** [docs/MONITORING.md](./MONITORING.md) - Adaptive sampling and real-time dashboard

---

**Last Updated:** 2026-03-04
- Rewrote Redis data structures section for hash + index architecture (replaces sorted-set-with-JSON-values)
- Added Filter Index Architecture section (focus, gifts, fan-out routing)
- Updated all key patterns from `chat:{code}:*` → `room:{room_id}:*`
- Updated all file paths from `redis_cache.py` → `utils/performance/cache.py`
- Documented `gift_recipient` denormalized field and per-user gift indexes
- Removed stale "frontend reactions not implemented" section (reactions are fully implemented)
- Updated message deletion to document filter index cleanup (Layer 2)
- Added frontend room navigation architecture note (unified `currentRoom` state)
