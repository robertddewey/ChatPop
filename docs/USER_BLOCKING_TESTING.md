# User Blocking - Frontend Testing Guide

This document explains how to test the user blocking feature in the browser and verify it works at scale.

## Current Implementation Status

**Backend:** ✅ Complete (with known security vulnerabilities documented in SECURITY_CHECKLIST.md)
- API endpoints: `/api/chats/user-blocks/block/`, `/api/chats/user-blocks/unblock/`, `/api/chats/user-blocks/`
- PostgreSQL persistence
- Redis caching
- WebSocket message filtering

**Frontend:** ⚠️ API integration only (no UI yet)
- API functions exist in `frontend/src/lib/api.ts`
- No UI components to trigger block/unblock
- No blocked users management interface

---

## What's Missing for Frontend Testing

### 1. Block/Unblock UI Components

**Location needed:** `frontend/src/components/MessageActionsModal.tsx`

The existing long-press action modal needs a "Block User" option:

```typescript
// Inside MessageActionsModal.tsx

const handleBlockUser = async () => {
  try {
    await messageApi.blockUserSiteWide(message.username);
    toast.success(`Blocked ${message.username}`);
    setIsOpen(false);
  } catch (error) {
    toast.error('Failed to block user');
  }
};

// Add to action buttons:
<button
  onClick={handleBlockUser}
  className={actionButtonClass}
>
  <UserX className="w-5 h-5" />
  <span>Block User</span>
</button>
```

**Requirements:**
- Only show for registered users (check if `localStorage.getItem('auth_token')` exists)
- Don't show "Block User" option on your own messages
- Add confirmation dialog for block action
- Show toast notification on success/failure

### 2. Blocked Users Management UI

**Location needed:** New component `frontend/src/components/BlockedUsersModal.tsx`

A modal/sheet to view and manage blocked users:

```typescript
// Features needed:
- List all blocked users (call messageApi.getBlockedUsers())
- Show username and date blocked
- Unblock button for each user
- Empty state: "You haven't blocked anyone yet"
- Search/filter if list is long
```

**Access point:** Add button in chat settings or user profile

### 3. Real-time Block Updates

**Location needed:** `frontend/src/app/chat/[code]/page.tsx`

WebSocket listener for block_update events:

```typescript
// In WebSocket message handler
if (data.type === 'block_update') {
  if (data.action === 'add') {
    // User blocked someone - hide their messages in real-time
    setBlockedUsernames(prev => [...prev, data.blocked_username]);
  } else if (data.action === 'remove') {
    // User unblocked someone - show their messages again
    setBlockedUsernames(prev => prev.filter(u => u !== data.blocked_username));
  }
}

// Filter messages display
const visibleMessages = messages.filter(msg =>
  !blockedUsernames.includes(msg.username)
);
```

### 4. Client-side Message Filtering

**Location needed:** `frontend/src/app/chat/[code]/page.tsx`

Load blocked usernames on page load and filter messages:

```typescript
// On component mount
useEffect(() => {
  const loadBlockedUsers = async () => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      const result = await messageApi.getBlockedUsers();
      setBlockedUsernames(result.blocked_users.map(u => u.username));
    }
  };
  loadBlockedUsers();
}, []);

// Filter messages before rendering
const visibleMessages = messages.filter(msg =>
  !blockedUsernames.includes(msg.username)
);
```

---

## Manual Testing Procedure (Once UI is Built)

### Test 1: Basic Block Functionality

**Setup:**
1. Register two users: `Alice` and `Bob`
2. Create a public chat
3. Both users join the chat

**Test Steps:**
1. **Bob sends messages:** "Hello" → "How are you?" → "Testing"
2. **Alice sees all 3 messages:** ✅
3. **Alice long-presses Bob's message** → "Block User" → Confirm
4. **Verify API call:** Network tab shows POST to `/api/chats/user-blocks/block/` with status 201
5. **Alice's view updates:** All Bob's messages disappear immediately
6. **Bob sends new message:** "Can you see this?"
7. **Alice doesn't see it:** ✅ Real-time filtering working
8. **Bob's view unchanged:** He still sees all messages (blocking is one-way)

**Expected Results:**
- ✅ Alice doesn't see any messages from Bob (past or new)
- ✅ Bob has no idea he's been blocked (sees all messages normally)
- ✅ Other users in chat see all messages (blocking is per-user)

### Test 2: Unblock Functionality

**Test Steps:**
1. **Alice opens blocked users list**
2. **Sees Bob in the list** with block timestamp
3. **Clicks "Unblock" next to Bob's name**
4. **Verify API call:** Network tab shows POST to `/api/chats/user-blocks/unblock/` with status 200
5. **Bob's messages reappear** in Alice's chat immediately
6. **Bob sends new message:** "Hello again"
7. **Alice sees it:** ✅

**Expected Results:**
- ✅ All of Bob's messages become visible again
- ✅ Real-time updates work (WebSocket block_update with action: 'remove')

### Test 3: Multi-Device Sync

**Setup:**
1. Alice logged in on two devices (two browser tabs/windows)
2. Both tabs in same chat with Bob

**Test Steps:**
1. **Tab 1: Alice blocks Bob**
2. **Tab 2: Bob's messages disappear immediately** (WebSocket sync)
3. **Bob sends new message**
4. **Neither tab shows the message:** ✅
5. **Tab 2: Alice unblocks Bob**
6. **Tab 1: Bob's messages reappear immediately**

**Expected Results:**
- ✅ Block/unblock syncs across all of user's active sessions
- ✅ WebSocket group_send to `user_{user_id}_notifications` works

### Test 4: Cross-Chat Blocking (Site-Wide)

**Setup:**
1. Alice and Bob in Chat A
2. Alice blocks Bob in Chat A

**Test Steps:**
1. **Create Chat B** (different chat room)
2. **Alice and Bob both join Chat B**
3. **Bob sends message in Chat B**
4. **Alice doesn't see it:** ✅ Block is site-wide

**Expected Results:**
- ✅ Blocking works across all chat rooms
- ✅ Alice doesn't see Bob's messages anywhere on the site

### Test 5: Anonymous User Restriction

**Test Steps:**
1. **Alice NOT logged in** (no auth token)
2. **Alice joins chat as anonymous user**
3. **Long-press message** → "Block User" option not shown
4. **Try direct API call** via browser console:
   ```javascript
   fetch('https://localhost:9000/api/chats/user-blocks/block/', {
     method: 'POST',
     headers: { 'Content-Type': 'application/json' },
     body: JSON.stringify({ username: 'Bob' })
   })
   ```
5. **Response: 401 Unauthorized** ✅

**Expected Results:**
- ✅ Anonymous users cannot access blocking feature
- ✅ UI doesn't show block options for anonymous users

---

## Scale Testing (Load Testing)

### Test 6: Large Block List Performance

**Objective:** Verify blocking still works with 1,000+ blocked users

**Setup Script:** `backend/test_large_blocklist.py`

```python
#!/usr/bin/env python3
"""Test blocking performance with large block list"""
import requests
import time

API_BASE = 'https://localhost:9000'

def test_large_blocklist():
    # Register user
    token = register_user()

    print("Creating 1000 blocks...")
    start = time.time()

    for i in range(1000):
        block_user(token, f"User{i}")
        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/1000 blocks created")

    elapsed = time.time() - start
    print(f"✓ Created 1000 blocks in {elapsed:.2f}s")

    # Test retrieval
    print("\nFetching block list...")
    start = time.time()
    response = requests.get(
        f"{API_BASE}/api/chats/user-blocks/",
        headers={"Authorization": f"Token {token}"},
        verify=False
    )
    elapsed = time.time() - start

    print(f"✓ Retrieved {response.json()['count']} blocks in {elapsed:.2f}s")

    if elapsed > 1.0:
        print("⚠️  WARNING: Retrieval taking >1s, consider pagination")

if __name__ == "__main__":
    test_large_blocklist()
```

**Expected Results:**
- ✅ 1000 blocks created without errors
- ✅ Block list retrieval takes <1 second
- ✅ WebSocket connection doesn't timeout loading blocks
- ⚠️ If >1s, add pagination to API

**Performance Benchmarks:**
- Block creation: <50ms per operation
- Block list retrieval: <500ms for 1000 users
- WebSocket filtering: O(1) lookup via Python sets

### Test 7: Concurrent Block Operations

**Objective:** Verify race condition fix (when implemented)

**Setup:** `backend/test_concurrent_blocks.py`

```python
#!/usr/bin/env python3
"""Test concurrent blocking operations"""
import concurrent.futures
import requests

def block_same_user_concurrently(token, username):
    """10 threads try to block same user simultaneously"""
    def block():
        return requests.post(
            'https://localhost:9000/api/chats/user-blocks/block/',
            json={'username': username},
            headers={'Authorization': f'Token {token}'},
            verify=False
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(block) for _ in range(10)]
        results = [f.result() for f in futures]

    # Check database for duplicates
    response = requests.get(
        'https://localhost:9000/api/chats/user-blocks/',
        headers={'Authorization': f'Token {token}'},
        verify=False
    )

    count = response.json()['count']
    if count > 1:
        print(f"❌ RACE CONDITION: {count} duplicate blocks created")
        return False
    else:
        print(f"✅ Race condition prevented: Only 1 block created")
        return True
```

**Expected Results (after fix):**
- ✅ Only 1 UserBlock record created despite 10 concurrent requests
- ✅ No `IntegrityError` crashes
- ✅ All API responses return success (idempotent)

### Test 8: WebSocket Message Throughput

**Objective:** Verify blocking doesn't slow down message delivery

**Setup:** Simulate high-traffic chat with blocked users

```python
# Send 100 messages/second from 10 users
# Alice has blocked 5 of those users
# Measure: Message delivery latency to Alice
```

**Expected Results:**
- ✅ <100ms latency for message delivery
- ✅ No memory leaks in WebSocket consumer
- ✅ Filtering happens before send (not after)

**How to Monitor:**
```python
# In consumers.py, add timing logs
import time

async def chat_message(self, event):
    start = time.time()

    # Existing filtering logic
    if sender_username in self.blocked_usernames:
        return

    elapsed = (time.time() - start) * 1000
    if elapsed > 10:  # Log if >10ms
        logger.warning(f"Slow message filter: {elapsed:.2f}ms")
```

---

## Scale Considerations

### Database Performance

**Current Implementation:**
```sql
-- Query used by get_blocked_users()
SELECT * FROM chats_userblock
WHERE blocker_id = %s
ORDER BY created_at DESC;
```

**Optimization Needed When:**
- User has >100 blocked users
- List retrieval takes >500ms

**Solution:** Add pagination
```python
# In user_block_views.py
from rest_framework.pagination import PageNumberPagination

class UserBlockListView(APIView):
    pagination_class = PageNumberPagination

    def get(self, request):
        blocks = UserBlock.objects.filter(blocker=request.user).order_by('-created_at')

        # Paginate if needed
        paginator = PageNumberPagination()
        paginator.page_size = 50
        paginated_blocks = paginator.paginate_queryset(blocks, request)

        # ... rest of logic
```

### Redis Memory Usage

**Current Storage:**
```
user_blocks:{user_id} → Set of blocked usernames (strings)
```

**Memory Calculation:**
- Average username: 10 bytes
- 1000 blocked users: ~10KB per user
- 10,000 active users: ~100MB total

**Optimization Needed When:**
- Redis memory usage >1GB
- Block list load time >100ms

**Solution:** Use Redis sorted sets with timestamps for expiration

### WebSocket Memory Usage

**Current Implementation:**
```python
# In consumers.py - each WebSocket connection holds:
self.blocked_usernames = set()  # In-memory set
```

**Memory Calculation:**
- 1000 blocked users per connection: ~10KB
- 1000 concurrent WebSocket connections: ~10MB

**Risk:** Memory leak if sets grow unbounded

**Mitigation:**
```python
async def connect(self):
    # Limit block list size per connection
    blocked_usernames = await self.load_blocked_usernames(self.user_id)
    self.blocked_usernames = set(list(blocked_usernames)[:1000])  # Cap at 1000

    if len(blocked_usernames) > 1000:
        logger.warning(f"User {self.user_id} has {len(blocked_usernames)} blocks (capped at 1000)")
```

---

## Monitoring in Production

### Key Metrics to Track

**API Performance:**
```python
# Add to Django middleware or APM tool
- /api/chats/user-blocks/block/ - avg response time
- /api/chats/user-blocks/unblock/ - avg response time
- /api/chats/user-blocks/ - avg response time
- Rate: blocks created per hour
- Rate: blocks removed per hour
```

**Database Queries:**
```sql
-- Slow query log
-- Alert if any query takes >500ms
SELECT * FROM chats_userblock WHERE blocker_id = ?;
```

**Redis Operations:**
```python
# Monitor Redis command latency
- SADD user_blocks:{id} {username} - avg latency
- SREM user_blocks:{id} {username} - avg latency
- SMEMBERS user_blocks:{id} - avg latency
- SISMEMBER user_blocks:{id} {username} - avg latency
```

**WebSocket Health:**
```python
# Track in consumers.py
- Connections with >100 blocked users
- Message filtering time (should be <1ms)
- Memory usage per connection
```

### Alerts to Configure

**Critical:**
- Block API endpoint returning 500 errors
- Redis connection failures
- Database deadlocks on UserBlock table

**Warning:**
- Block list retrieval >1s
- >10% of block operations failing
- Redis memory usage >80%

---

## Current Test Results Summary

| Test | Status | Notes |
|------|--------|-------|
| Basic functionality | ✅ 5/6 passing | `test_user_blocking.py` |
| Security tests | ⚠️ 6/11 passing | `test_user_blocking_adversarial.py` - vulnerabilities documented |
| Frontend UI | ❌ Not implemented | No UI components exist yet |
| Multi-device sync | ❓ Not tested | WebSocket code exists but untested |
| Large block lists | ❓ Not tested | Need to create load test |
| Concurrent operations | ❌ Race condition exists | Known vulnerability |

---

## Next Steps to Enable Frontend Testing

1. **Add Block UI to MessageActionsModal** (~30 min)
   - Add "Block User" button
   - Add confirmation dialog
   - Call `messageApi.blockUserSiteWide()`

2. **Create BlockedUsersModal component** (~1 hour)
   - List blocked users
   - Unblock functionality
   - Add to settings menu

3. **Implement client-side filtering** (~30 min)
   - Load blocked usernames on mount
   - Filter messages array before render
   - Listen for WebSocket block_update events

4. **Manual testing** (~1 hour)
   - Test block/unblock
   - Test multi-device sync
   - Test cross-chat blocking
   - Test anonymous user restriction

5. **Load testing** (~2 hours)
   - Create large block list test
   - Test concurrent operations
   - Monitor performance

**Total Estimated Time:** ~5-6 hours

Once UI is built, you can run through all manual tests in this document to verify blocking works correctly at the user level.
