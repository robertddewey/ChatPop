# Emoji Reactions Feature - Implementation Guide

## ✅ Completed Implementation

### Backend (100% Complete)

#### 1. Database Schema
**File:** `backend/chats/models.py:343-398`

```python
class MessageReaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='reactions')
    emoji = models.CharField(max_length=10)
    user = models.ForeignKey(User, null=True, blank=True, related_name='message_reactions')
    fingerprint = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    username = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
```

**Features:**
- One reaction per user per message (unique constraints)
- Support for both logged-in and anonymous users
- Indexed for performance

**Migration:** `backend/chats/migrations/0043_add_message_reactions.py`

#### 2. API Endpoints
**Files:** `backend/chats/views.py:776-885`, `backend/chats/urls.py:26-27`

**Endpoints:**
- `POST /api/chats/{code}/messages/{message_id}/react/`
  - Toggle reaction (add/remove/update)
  - Requires: `emoji`, `session_token`, `username`, `fingerprint`
  - Returns: `{action: 'added'|'removed'|'updated', emoji, reaction}`

- `GET /api/chats/{code}/messages/{message_id}/reactions/`
  - Get all reactions for a message
  - Returns: `{reactions: [...], summary: [...], total_count: N}`
  - Summary includes top 3 emojis with counts

**Allowed Emojis:** 👍 ❤️ 😂 😮 😢 😡

#### 3. WebSocket Real-time Broadcast
**Files:** `backend/chats/consumers.py:109-111`, `backend/chats/views.py:850-866`

**WebSocket Event Format:**
```javascript
{
  type: 'reaction',
  action: 'added' | 'removed' | 'updated',
  message_id: '...',
  emoji: '👍',
  username: 'alice',
  reaction: { /* full reaction object */ }
}
```

### Frontend (90% Complete)

#### 1. TypeScript Types
**File:** `frontend/src/lib/api.ts:141-178`

```typescript
export interface MessageReaction {
  id: string;
  message: string;
  emoji: string;
  user: User | null;
  fingerprint: string | null;
  username: string;
  created_at: string;
}

export interface ReactionSummary {
  emoji: string;
  count: number;
  users: string[];
}

export interface Message {
  // ... existing fields ...
  reactions?: ReactionSummary[]; // Top 3 reactions for display
}
```

#### 2. API Client Functions
**File:** `frontend/src/lib/api.ts:398-424`

```typescript
messageApi.toggleReaction(code, messageId, emoji, username, fingerprint)
messageApi.getReactions(code, messageId)
```

#### 3. ReactionBar Component
**File:** `frontend/src/components/ReactionBar.tsx`

**Usage:**
```tsx
<ReactionBar
  reactions={message.reactions}
  onReactionClick={(emoji) => handleReactionToggle(message.id, emoji)}
  themeIsDarkMode={isDark}
/>
```

**Features:**
- Shows top 3 reactions
- Click to toggle reaction (Slack/Discord style)
- Theme-aware styling (dark/light)

#### 4. Emoji Picker in MessageActionsModal
**File:** `frontend/src/components/MessageActionsModal.tsx:53-54, 299-323`

**Features:**
- 6 emoji buttons displayed above action menu
- Horizontal layout with circular buttons
- Closes modal after selection
- Callback: `onReact(messageId, emoji)`

---

## 📋 Remaining Integration Steps

### Step 1: Add State Management to Chat Page

**File:** `frontend/src/app/chat/[code]/page.tsx`

Add state to track reactions per message:

```typescript
// Add near other state declarations
const [messageReactions, setMessageReactions] = useState<Record<string, ReactionSummary[]>>({});
```

### Step 2: Create Reaction Toggle Handler

Add this function in the chat page component:

```typescript
const handleReactionToggle = async (messageId: string, emoji: string) => {
  try {
    const result = await messageApi.toggleReaction(
      params.code,
      messageId,
      emoji,
      username,
      fingerprint
    );

    // Optimistically update local state
    if (result.action === 'removed') {
      // Remove reaction from local state
      setMessageReactions(prev => {
        const updated = { ...prev };
        const reactions = updated[messageId] || [];
        updated[messageId] = reactions.filter(r => r.emoji !== emoji);
        return updated;
      });
    } else {
      // Add/update reaction in local state
      // This will be refreshed by WebSocket broadcast
    }
  } catch (error) {
    console.error('Failed to toggle reaction:', error);
  }
};
```

### Step 3: Handle WebSocket Reaction Events

Add to the existing WebSocket message handler:

```typescript
// In the WebSocket onmessage handler
const data = JSON.parse(event.data);

if (data.type === 'reaction') {
  // Update reactions for the specific message
  const { message_id, action, emoji } = data;

  // Fetch fresh reaction summary for this message
  const { summary } = await messageApi.getReactions(params.code, message_id);

  setMessageReactions(prev => ({
    ...prev,
    [message_id]: summary
  }));
}
```

### Step 4: Add ReactionBar to Message Rendering

In the message rendering section, add the ReactionBar component:

```tsx
import ReactionBar from '@/components/ReactionBar';

// In the message map/render function
{messages.map((message) => (
  <div key={message.id}>
    {/* Existing message content */}
    <MessageActionsModal
      message={message}
      currentUsername={username}
      isHost={isHost}
      themeIsDarkMode={currentDesign.is_dark_mode}
      onReply={handleReply}
      onReact={handleReactionToggle}  // Add this prop
      // ... other props
    >
      {/* Message bubble */}
    </MessageActionsModal>

    {/* Add ReactionBar below message */}
    <ReactionBar
      reactions={messageReactions[message.id] || message.reactions || []}
      onReactionClick={(emoji) => handleReactionToggle(message.id, emoji)}
      themeIsDarkMode={currentDesign.is_dark_mode}
    />
  </div>
))}
```

### Step 5: Load Initial Reactions (Optional)

If you want to load reactions when fetching messages:

```typescript
// After loading messages
const loadReactionsForMessages = async (messages: Message[]) => {
  const reactionsMap: Record<string, ReactionSummary[]> = {};

  // You can either:
  // A) Include reactions in message serializer (backend change needed)
  // B) Fetch reactions for each message (not recommended for many messages)
  // C) Wait for user interaction (current approach)

  setMessageReactions(reactionsMap);
};
```

---

## 🧪 Testing Checklist

### Backend Tests
- [ ] Test reaction creation with logged-in user
- [ ] Test reaction creation with anonymous user
- [ ] Test one reaction per user constraint
- [ ] Test reaction toggle (add → remove → add)
- [ ] Test WebSocket broadcast to all connected users
- [ ] Test allowed emoji validation
- [ ] Test session token validation

### Frontend Tests
- [ ] Emoji picker displays correctly in modal
- [ ] Clicking emoji calls API and closes modal
- [ ] ReactionBar displays top 3 reactions
- [ ] Clicking reaction in ReactionBar toggles it
- [ ] Real-time updates work across multiple users
- [ ] Works in both light and dark themes
- [ ] Works on mobile and desktop
- [ ] Works for both logged-in and anonymous users

### Cross-Theme Testing
Test on all themes:
- [ ] Purple Dream (light)
- [ ] Ocean Blue (light)
- [ ] Dark Mode (dark)
- [ ] Any custom themes

---

## 🎨 Styling Customization

### ReactionBar Styling
Located in `frontend/src/components/ReactionBar.tsx:20-25`

Current colors:
- **Dark theme:** `bg-zinc-800/50 border-zinc-700 text-zinc-300`
- **Light theme:** `bg-gray-100/80 border-gray-300 text-gray-700`

### Emoji Picker Styling
Located in `frontend/src/components/MessageActionsModal.tsx:314-316`

Current colors:
- **Dark theme:** `bg-zinc-800 hover:bg-zinc-700`
- **Light theme:** `bg-gray-100 hover:bg-gray-200`

---

## 📝 Database Migration

**IMPORTANT:** Before testing, you must run the migration:

```bash
cd backend
./venv/bin/python manage.py migrate chats
```

This creates the `chats_messagereaction` table.

---

## 🚀 Quick Start Testing

1. **Start Backend:**
   ```bash
   cd backend
   ALLOWED_HOSTS=localhost,127.0.0.1,10.0.0.135 \
   CORS_ALLOWED_ORIGINS="http://localhost:4000,https://localhost:4000" \
   ./venv/bin/daphne -e ssl:9000:privateKey=../certs/localhost+3-key.pem:certKey=../certs/localhost+3.pem -b 0.0.0.0 chatpop.asgi:application
   ```

2. **Start Frontend:**
   ```bash
   cd frontend
   npm run dev:https
   ```

3. **Open Chat:**
   - Navigate to `https://localhost:4000/chat/{code}`
   - Long-press a message
   - Click an emoji
   - Check database: `SELECT * FROM chats_messagereaction;`

---

## 🔧 Troubleshooting

### Reactions not saving
- Check migration ran successfully
- Check session token is being sent
- Check browser console for API errors

### WebSocket not broadcasting
- Verify WebSocket connection is established
- Check Redis is running (reactions use WebSocket channels)
- Check browser console for WebSocket errors

### Reactions not displaying
- Verify message state includes reactions
- Check ReactionBar is imported correctly
- Check theme styling is applied

---

## 📚 Related Files

**Backend:**
- Models: `backend/chats/models.py:343-398`
- Views: `backend/chats/views.py:776-885`
- URLs: `backend/chats/urls.py:26-27`
- Serializers: `backend/chats/serializers.py:271-288`
- Consumer: `backend/chats/consumers.py:109-111`
- Migration: `backend/chats/migrations/0043_add_message_reactions.py`

**Frontend:**
- API Types: `frontend/src/lib/api.ts:141-178, 398-424`
- ReactionBar: `frontend/src/components/ReactionBar.tsx`
- Emoji Picker: `frontend/src/components/MessageActionsModal.tsx:53-54, 299-323`
- Chat Page: `frontend/src/app/chat/[code]/page.tsx` (integration pending)

---

## ✅ Feature Complete Checklist

- [x] Backend database schema
- [x] Backend API endpoints
- [x] Backend WebSocket broadcasting
- [x] Frontend TypeScript types
- [x] Frontend API client
- [x] ReactionBar component
- [x] Emoji picker UI
- [ ] Chat page integration
- [ ] WebSocket listener
- [ ] State management
- [ ] Cross-theme testing
- [ ] Unit tests

**Status:** 85% Complete - Ready for integration!
