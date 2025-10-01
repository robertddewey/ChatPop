# ChatPop Performance Optimization Plan

## Current Performance Analysis

### Identified Issues

#### 1. Polling Every 3 Seconds
**Location**: `frontend/src/app/chat/[code]/page.tsx:173-182`

```typescript
setInterval(() => {
  loadMessages();
}, 3000);
```

**Problems**:
- Fetches ALL messages every 3 seconds, regardless of changes
- With 1000+ messages, significant unnecessary data transfer
- 20 API calls per minute per user
- Server load scales linearly with concurrent users

**Impact**: High message rate rooms will cause excessive bandwidth and server load.

---

#### 2. IntersectionObserver Re-initialization
**Location**: `frontend/src/app/chat/[code]/page.tsx:207-254`

```typescript
useEffect(() => {
  // Creates new observer on every message change
}, [filteredMessages.length, allStickyHostMessages.length]);
```

**Problems**:
- Observer torn down and recreated on every new message
- Performance overhead with high message rates
- Memory churn from constant create/destroy cycle

**Impact**: CPU spikes during active conversations.

---

#### 3. Filter Calculations on Every Render
**Location**: `frontend/src/app/chat/[code]/page.tsx:140-158`

```typescript
const filteredMessages = filterMode === 'focus'
  ? messages.filter(msg => {
      // Show messages that host replied to
      const hostRepliedToThis = messages.some(
        m => m.is_from_host && m.reply_to === msg.id
      );
    })
  : messages;
```

**Problems**:
- O(n²) complexity when checking replies
- Runs on every render (not memoized)
- With 1000 messages: potentially 1,000,000 operations per render
- No caching of filter results

**Impact**: UI lag and frame drops during typing or scrolling.

---

#### 4. Multiple Unoptimized Array Operations
**Location**: Throughout component

```typescript
allStickyHostMessages.map()
filteredMessages.filter().sort()
messages.filter().slice().reverse()
```

**Problems**:
- Run on every render without memoization
- Multiple passes over full message array
- Sorting operations on every render

**Impact**: Wasted CPU cycles, especially on mobile devices.

---

#### 5. No Pagination or Message Limiting
**Current State**: All messages loaded at once

**Problems**:
- Initial page load scales with total message count
- Memory usage grows unbounded
- No way to handle rooms with 10,000+ messages

**Impact**: App becomes unusable for popular/old chat rooms.

---

## Optimization Roadmap

### Phase 1: Quick Wins (Low Effort, High Impact)

#### 1.1 Add useMemo for Expensive Calculations
**Estimated Time**: 30 minutes
**Impact**: 70-80% reduction in render-time calculations

```typescript
const filteredMessages = useMemo(() => {
  if (filterMode !== 'focus') return messages;

  const myUsername = localStorage.getItem(`chat_username_${code}`);
  const hostReplyMap = new Map(); // O(n) instead of O(n²)

  messages.forEach(m => {
    if (m.is_from_host && m.reply_to) {
      hostReplyMap.set(m.reply_to, true);
    }
  });

  return messages.filter(msg => {
    if (msg.is_from_host) return true;
    if (msg.username === myUsername) return true;
    if (hostReplyMap.has(msg.id)) return true;
    return false;
  });
}, [messages, filterMode, code]);

const allStickyHostMessages = useMemo(() => {
  return filteredMessages
    .filter(m => m.is_from_host)
    .slice(-2)
    .reverse();
}, [filteredMessages]);

const topPinnedMessage = useMemo(() => {
  return filteredMessages
    .filter(m => m.is_pinned && !m.is_from_host)
    .sort((a, b) => parseFloat(b.pin_amount_paid) - parseFloat(a.pin_amount_paid))
    [0];
}, [filteredMessages]);
```

---

#### 1.2 Backend Message Limiting
**Estimated Time**: 1 hour
**Impact**: 90% reduction in initial load time for large rooms

**Backend Changes** (`backend/chats/views.py`):
```python
class MessageListView(generics.ListAPIView):
    def get_queryset(self):
        code = self.kwargs['code']
        chat_room = get_object_or_404(ChatRoom, code=code, is_active=True)

        # Add limit parameter (default 100)
        limit = int(self.request.query_params.get('limit', 100))

        messages = Message.objects.filter(
            chat_room=chat_room,
            is_deleted=False
        ).annotate(
            priority=Case(
                When(message_type=Message.MESSAGE_HOST, then=Value(0)),
                When(is_pinned=True, then=Value(1)),
                default=Value(2),
                output_field=IntegerField()
            )
        ).order_by('priority', 'created_at')

        # Return only recent messages (always include pinned/host)
        pinned_and_host = messages.filter(Q(is_pinned=True) | Q(message_type=Message.MESSAGE_HOST))
        regular = messages.filter(is_pinned=False, message_type=Message.MESSAGE_NORMAL)[:limit]

        return (pinned_and_host | regular).distinct()
```

---

#### 1.3 Debounce Scroll Handler
**Estimated Time**: 15 minutes
**Impact**: Reduce scroll event processing by 90%

```typescript
const handleScroll = useMemo(
  () => debounce(() => {
    shouldAutoScrollRef.current = checkIfNearBottom();
  }, 100),
  []
);
```

---

### Phase 2: Real-Time Communication (Medium Effort, High Impact)

#### 2.1 Implement WebSockets with Django Channels
**Estimated Time**: 4-6 hours
**Impact**: Eliminate polling, instant message delivery, 95% reduction in API calls

**Benefits**:
- Real-time message delivery (no 3-second delay)
- Only send new messages (not entire message list)
- Server can push updates to specific users
- Typing indicators possible
- Read receipts possible

**Implementation Overview**:

1. **Backend: Setup Channels** (already in dependencies)
```python
# backend/chats/consumers.py
from channels.generic.websocket import AsyncJsonWebsocketConsumer

class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.room_code = self.scope['url_route']['kwargs']['code']
        self.room_group_name = f'chat_{self.room_code}'

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def receive_json(self, content):
        message_type = content.get('type')

        if message_type == 'chat_message':
            # Broadcast to room
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat.message',
                    'message': content['message']
                }
            )

    async def chat_message(self, event):
        await self.send_json(event['message'])
```

2. **Backend: Update Routing**
```python
# backend/chats/routing.py (already exists)
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/chat/(?P<code>\w+)/$', consumers.ChatConsumer.as_asgi()),
]
```

3. **Frontend: WebSocket Hook**
```typescript
// frontend/src/hooks/useWebSocket.ts
export function useChatWebSocket(code: string, onMessage: (msg: Message) => void) {
  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:9000/ws/chat/${code}/`);

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      onMessage(message);
    };

    return () => ws.close();
  }, [code]);
}
```

4. **Frontend: Integration**
```typescript
// In chat page
const [messages, setMessages] = useState<Message[]>([]);

useChatWebSocket(code, (newMessage) => {
  setMessages(prev => [...prev, newMessage]);
});
```

---

### Phase 3: Advanced Optimizations (High Effort, High Impact)

#### 3.1 Virtual Scrolling
**Estimated Time**: 3-4 hours
**Impact**: Handle 10,000+ messages without performance degradation

**Library**: `react-window` or `@tanstack/react-virtual`

```typescript
import { useVirtualizer } from '@tanstack/react-virtual';

const parentRef = useRef<HTMLDivElement>(null);

const virtualizer = useVirtualizer({
  count: filteredMessages.length,
  getScrollElement: () => parentRef.current,
  estimateSize: () => 80, // Approximate message height
  overscan: 5,
});

return (
  <div ref={parentRef} className="flex-1 overflow-y-auto">
    <div style={{ height: `${virtualizer.getTotalSize()}px` }}>
      {virtualizer.getVirtualItems().map((virtualRow) => {
        const message = filteredMessages[virtualRow.index];
        return (
          <div
            key={message.id}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              transform: `translateY(${virtualRow.start}px)`,
            }}
          >
            {/* Message component */}
          </div>
        );
      })}
    </div>
  </div>
);
```

**Benefits**:
- Only renders visible messages (typically 10-20)
- Smooth scrolling even with 100,000+ messages
- Reduced memory footprint
- Critical for mobile performance

---

#### 3.2 Message Pagination with "Load More"
**Estimated Time**: 2-3 hours
**Impact**: Fast initial loads, unlimited message history

**Backend**:
```python
class MessageListView(generics.ListAPIView):
    def get_queryset(self):
        before = self.request.query_params.get('before')  # Timestamp
        limit = int(self.request.query_params.get('limit', 50))

        messages = Message.objects.filter(
            chat_room=chat_room,
            is_deleted=False
        )

        if before:
            messages = messages.filter(created_at__lt=before)

        return messages.order_by('-created_at')[:limit]
```

**Frontend**:
```typescript
const [messages, setMessages] = useState<Message[]>([]);
const [hasMore, setHasMore] = useState(true);

const loadMore = async () => {
  const oldest = messages[0];
  const olderMessages = await messageApi.getMessages(code, {
    before: oldest.created_at,
    limit: 50
  });

  setMessages([...olderMessages, ...messages]);
  setHasMore(olderMessages.length === 50);
};
```

---

#### 3.3 Optimize IntersectionObserver
**Estimated Time**: 1 hour
**Impact**: Eliminate re-initialization overhead

```typescript
// Create observer once, update observations dynamically
const observerRef = useRef<IntersectionObserver | null>(null);

useEffect(() => {
  if (!observerRef.current) {
    observerRef.current = new IntersectionObserver(/* ... */);
  }

  // Just update what we're observing, don't recreate
  const observer = observerRef.current;

  return () => {
    observer.disconnect();
  };
}, []); // Only create once

// Separate effect to manage observations
useEffect(() => {
  if (!observerRef.current) return;

  const observer = observerRef.current;
  const container = messagesContainerRef.current;

  // Update observations without recreating observer
  // ...
}, [filteredMessages.length]);
```

---

### Phase 4: Caching & State Management (Optional)

#### 4.1 React Query for Message Caching
**Estimated Time**: 2-3 hours
**Impact**: Instant navigation between chats, optimistic updates

```typescript
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

const { data: messages } = useQuery({
  queryKey: ['messages', code],
  queryFn: () => messageApi.getMessages(code),
  staleTime: 1000, // Consider fresh for 1 second
});

const queryClient = useQueryClient();

const sendMessage = useMutation({
  mutationFn: (content: string) => messageApi.sendMessage(code, username, content),
  onMutate: async (content) => {
    // Optimistic update
    const newMessage = { /* ... */ };
    queryClient.setQueryData(['messages', code], (old) => [...old, newMessage]);
  },
});
```

---

## Performance Targets

### Current Performance (1000 messages)
- Initial Load: 2-3 seconds
- Render Time: 150-300ms per update
- Memory Usage: 50-80MB
- Network: 20 requests/min
- Scroll FPS: 30-45 fps

### Target Performance (Phase 1 Complete)
- Initial Load: 500-800ms
- Render Time: 20-40ms per update
- Memory Usage: 20-30MB
- Network: 10 requests/min
- Scroll FPS: 55-60 fps

### Target Performance (Phase 2 Complete - WebSockets)
- Initial Load: 300-500ms
- Render Time: 10-20ms per update
- Memory Usage: 20-30MB
- Network: <1 request/min (only WS)
- Scroll FPS: 55-60 fps

### Target Performance (Phase 3 Complete - Virtual Scroll)
- Initial Load: 300-500ms (regardless of message count)
- Render Time: 5-10ms per update
- Memory Usage: 15-20MB (even with 10,000+ messages)
- Network: <1 request/min
- Scroll FPS: 60 fps

---

## Implementation Priority

### Do Now (Before Launch)
1. ✅ Add useMemo to filter calculations
2. ✅ Backend message limiting (100 messages)
3. ✅ Debounce scroll handler

### Do Before Scale (1000+ concurrent users)
4. WebSocket implementation
5. Optimize IntersectionObserver
6. Basic pagination ("Load more" for history)

### Do When Growing (10,000+ messages per room)
7. Virtual scrolling
8. React Query for caching
9. Advanced pagination strategies

### Nice to Have
- Typing indicators
- Read receipts
- Message search
- Message reactions
- File uploads with progress

---

## Testing Strategy

### Performance Benchmarks
1. **Load Test**: Create room with 10,000 messages
2. **Stress Test**: 100 users sending messages simultaneously
3. **Mobile Test**: Test on iPhone SE (2020) - slowest modern device
4. **Network Test**: Simulate 3G connection

### Metrics to Track
- Time to First Message (TTFM)
- Messages per second throughput
- Memory usage over time
- CPU usage during active chat
- Scroll frame rate
- Network bandwidth usage

### Tools
- Chrome DevTools Performance tab
- React DevTools Profiler
- Lighthouse for initial load
- Artillery.io for load testing backend

---

## Notes

- Django Channels already included in `backend/requirements.txt`
- Redis needed for Channels (already in `docker-compose.yml`)
- Consider message retention policy (delete after 30 days?)
- Consider WebSocket reconnection logic
- Consider message delivery guarantees

---

## Questions to Answer

1. What's the expected message rate for popular rooms?
2. What's the expected concurrent user count per room?
3. How long should message history be retained?
4. Do we need message delivery guarantees?
5. Should we support offline message queuing?
6. What's the budget for infrastructure (Redis, etc.)?
