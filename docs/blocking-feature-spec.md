# User Blocking Feature Specification

## Overview

User blocking allows chat hosts to prevent specific users from accessing their chat rooms. Blocks are enforced across multiple identifiers (username, fingerprint, user account, and future email/phone fields) to prevent circumvention.

---

## Core Blocking Concept

**Block Target:** A `ChatParticipation` record (a specific user in a specific chat)

**Block Scope:** The block applies to:
1. **Username** (case-insensitive) - blocks "robert", "Robert", "ROBERT" in that chat
2. **Fingerprint** - blocks the device/browser
3. **User Account** (if logged in) - blocks all participations by that user in the chat
4. **Future:** Email/mobile number fields on ChatParticipation

---

## Database Schema

### ChatBlock Model

```python
class ChatBlock(models.Model):
    """
    Represents a block applied to a user in a specific chat room.
    Multiple blocks can exist for the same user (one per identifier).
    """
    chat_room = ForeignKey(ChatRoom, on_delete=CASCADE)
    blocked_by = ForeignKey(ChatParticipation, on_delete=CASCADE)  # Who created the block (usually host)

    # What's being blocked (at least one must be set)
    blocked_username = CharField(max_length=15, null=True, blank=True)  # Case-insensitive
    blocked_fingerprint = CharField(max_length=255, null=True, blank=True)
    blocked_user = ForeignKey(User, null=True, blank=True, on_delete=CASCADE)  # Registered account
    blocked_email = EmailField(null=True, blank=True)  # Future
    blocked_phone = CharField(max_length=20, null=True, blank=True)  # Future

    # Metadata
    blocked_at = DateTimeField(auto_now_add=True)
    reason = TextField(blank=True)  # Optional note for host
    expires_at = DateTimeField(null=True, blank=True)  # Optional: for timed blocks

    class Meta:
        indexes = [
            Index(fields=['chat_room', 'blocked_username']),
            Index(fields=['chat_room', 'blocked_fingerprint']),
            Index(fields=['chat_room', 'blocked_user']),
        ]
        # Prevent duplicate blocks
        constraints = [
            UniqueConstraint(
                fields=['chat_room', 'blocked_username'],
                name='unique_chat_username_block',
                condition=Q(blocked_username__isnull=False)
            ),
            UniqueConstraint(
                fields=['chat_room', 'blocked_fingerprint'],
                name='unique_chat_fingerprint_block',
                condition=Q(blocked_fingerprint__isnull=False)
            ),
            UniqueConstraint(
                fields=['chat_room', 'blocked_user'],
                name='unique_chat_user_block',
                condition=Q(blocked_user__isnull=False)
            ),
        ]
```

### Future ChatParticipation Fields

```python
class ChatParticipation(models.Model):
    # Existing fields...
    user = ForeignKey(User, null=True, blank=True)
    fingerprint = CharField(max_length=255, null=True, blank=True)
    username = CharField(max_length=15)

    # New fields for host-required contact info
    contact_email = EmailField(null=True, blank=True)  # Host can require email
    contact_phone = CharField(max_length=20, null=True, blank=True)  # Host can require phone
```

### Future ChatRoom Settings

```python
class ChatRoom(models.Model):
    # Existing fields...

    # Contact requirements
    require_email = BooleanField(default=False)  # Host requires email to join
    require_phone = BooleanField(default=False)  # Host requires phone to join
```

---

## Block Creation Logic

### Function: `block_participation()`

```python
def block_participation(chat_room, participation, blocked_by):
    """
    Block a user across all their identifiers.
    Creates multiple ChatBlock records to cover username, fingerprint, and user account.

    Args:
        chat_room: ChatRoom instance
        participation: ChatParticipation to block
        blocked_by: ChatParticipation of blocker (usually host)

    Returns:
        List of created ChatBlock instances
    """
    blocks_created = []

    # Block username (case-insensitive)
    if participation.username:
        block, created = ChatBlock.objects.get_or_create(
            chat_room=chat_room,
            blocked_username=participation.username.lower(),
            defaults={
                'blocked_by': blocked_by,
            }
        )
        if created:
            blocks_created.append(block)

    # Block fingerprint (anonymous users)
    if participation.fingerprint:
        block, created = ChatBlock.objects.get_or_create(
            chat_room=chat_room,
            blocked_fingerprint=participation.fingerprint,
            defaults={
                'blocked_by': blocked_by,
            }
        )
        if created:
            blocks_created.append(block)

    # Block user account (logged-in users)
    if participation.user:
        block, created = ChatBlock.objects.get_or_create(
            chat_room=chat_room,
            blocked_user=participation.user,
            defaults={
                'blocked_by': blocked_by,
            }
        )
        if created:
            blocks_created.append(block)

    # Future: Block email/phone if those fields exist
    if hasattr(participation, 'contact_email') and participation.contact_email:
        block, created = ChatBlock.objects.get_or_create(
            chat_room=chat_room,
            blocked_email=participation.contact_email.lower(),
            defaults={
                'blocked_by': blocked_by,
            }
        )
        if created:
            blocks_created.append(block)

            # Also block all other participations with this email
            other_participations = ChatParticipation.objects.filter(
                chat_room=chat_room,
                contact_email__iexact=participation.contact_email
            ).exclude(id=participation.id)

            for other_part in other_participations:
                block_participation(chat_room, other_part, blocked_by)

    if hasattr(participation, 'contact_phone') and participation.contact_phone:
        block, created = ChatBlock.objects.get_or_create(
            chat_room=chat_room,
            blocked_phone=participation.contact_phone,
            defaults={
                'blocked_by': blocked_by,
            }
        )
        if created:
            blocks_created.append(block)

            # Also block all other participations with this phone
            other_participations = ChatParticipation.objects.filter(
                chat_room=chat_room,
                contact_phone=participation.contact_phone
            ).exclude(id=participation.id)

            for other_part in other_participations:
                block_participation(chat_room, other_part, blocked_by)

    return blocks_created
```

---

## Block Enforcement

### 1. Chat Join Prevention (`views.py` - `JoinChatView`)

```python
def check_if_blocked(chat_room, username, fingerprint, user, email=None, phone=None):
    """
    Check if user is blocked from this chat.

    Returns:
        (is_blocked: bool, error_message: str|None)
    """
    blocks = ChatBlock.objects.filter(chat_room=chat_room)

    # Check for expired blocks
    now = timezone.now()
    blocks = blocks.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))

    # Check username (case-insensitive)
    if username and blocks.filter(blocked_username__iexact=username).exists():
        return True, "You have been blocked from this chat."

    # Check fingerprint
    if fingerprint and blocks.filter(blocked_fingerprint=fingerprint).exists():
        return True, "You have been blocked from this chat."

    # Check user account
    if user and blocks.filter(blocked_user=user).exists():
        return True, "You have been blocked from this chat."

    # Check email (future)
    if email and blocks.filter(blocked_email__iexact=email).exists():
        return True, "You have been blocked from this chat."

    # Check phone (future)
    if phone and blocks.filter(blocked_phone=phone).exists():
        return True, "You have been blocked from this chat."

    return False, None
```

**Integration in JoinChatView:**

```python
class JoinChatView(APIView):
    def post(self, request, code):
        # ... existing code ...

        # Check if user is blocked
        is_blocked, error_msg = check_if_blocked(
            chat_room=chat_room,
            username=username,
            fingerprint=fingerprint,
            user=request.user if request.user.is_authenticated else None,
            email=request.data.get('contact_email'),  # Future
            phone=request.data.get('contact_phone'),  # Future
        )

        if is_blocked:
            return Response({'error': error_msg}, status=status.HTTP_403_FORBIDDEN)

        # ... continue with join logic ...
```

### 2. Message Send Prevention (WebSocket)

```python
# In ChatConsumer.receive()
async def receive(self, text_data):
    # ... parse message ...

    # Check if user is blocked before accepting message
    is_blocked = await database_sync_to_async(self.check_blocked)()

    if is_blocked:
        await self.send(json.dumps({
            'error': 'You have been blocked from this chat.'
        }))
        await self.close()
        return

    # ... process message ...

@database_sync_to_async
def check_blocked(self):
    """Check if current user is blocked."""
    is_blocked, _ = check_if_blocked(
        chat_room=self.participation.chat_room,
        username=self.participation.username,
        fingerprint=self.participation.fingerprint,
        user=self.participation.user,
    )
    return is_blocked
```

### 3. Real-Time Eviction

When a block is created, immediately disconnect blocked users:

```python
# After creating blocks in block_participation()
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

channel_layer = get_channel_layer()

# Send "user_blocked" event to chat group
async_to_sync(channel_layer.group_send)(
    f"chat_{chat_room.code}",
    {
        'type': 'user_blocked',
        'blocked_username': participation.username,
        'blocked_fingerprint': participation.fingerprint,
        'blocked_user_id': participation.user_id if participation.user else None,
    }
)
```

**Handle in ChatConsumer:**

```python
async def user_blocked(self, event):
    """Handle user_blocked event - disconnect if this user is blocked."""
    # Check if this consumer's user matches the blocked identifiers
    is_me_blocked = (
        (event.get('blocked_username') and
         self.participation.username.lower() == event['blocked_username'].lower()) or
        (event.get('blocked_fingerprint') and
         self.participation.fingerprint == event['blocked_fingerprint']) or
        (event.get('blocked_user_id') and
         self.participation.user_id == event['blocked_user_id'])
    )

    if is_me_blocked:
        await self.send(json.dumps({
            'type': 'blocked',
            'message': 'You have been removed from this chat.'
        }))
        await self.close()
```

---

## API Endpoints

### Block User

**POST `/api/chats/{code}/block/`**

Request:
```json
{
  "participation_id": "550e8400-e29b-41d4-a716-446655440000",
  "reason": "Spam messages"  // Optional
}
```

Response (201):
```json
{
  "success": true,
  "blocks_created": 3,  // username, fingerprint, user account
  "message": "User @username has been blocked"
}
```

Response (403):
```json
{
  "error": "Only the chat host can block users"
}
```

### Unblock User

**DELETE `/api/chats/{code}/block/{participation_id}/`**

Response (200):
```json
{
  "success": true,
  "blocks_removed": 3,
  "message": "User @username has been unblocked"
}
```

### List Blocked Users

**GET `/api/chats/{code}/blocked/`**

Response (200):
```json
{
  "blocked_users": [
    {
      "participation_id": "550e8400-e29b-41d4-a716-446655440000",
      "username": "spammer123",
      "blocked_at": "2025-10-09T12:34:56Z",
      "reason": "Spam messages",
      "blocked_identifiers": ["username", "fingerprint", "user_account"]
    }
  ]
}
```

---

## Frontend UI/UX

### 1. Block Button Location

Add "Block User" option to message action modal (long-press menu):

```typescript
// MessageActionsModal.tsx
{isHost && (
  <button
    onClick={() => handleBlockUser(message.user_id)}
    className="flex items-center space-x-3 w-full px-4 py-3 hover:bg-red-50"
  >
    <Ban className="w-5 h-5 text-red-600" />
    <span className="text-red-600 font-medium">Block User</span>
  </button>
)}
```

### 2. Block Confirmation Modal

```typescript
interface BlockConfirmModalProps {
  username: string;
  onConfirm: () => void;
  onCancel: () => void;
}

function BlockConfirmModal({ username, onConfirm, onCancel }: BlockConfirmModalProps) {
  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-sm mx-4">
        <h3 className="text-lg font-bold mb-2">Block @{username}?</h3>
        <p className="text-gray-600 mb-4">
          This user will be immediately removed from the chat and won't be able to rejoin.
          This action blocks their username, device, and account.
        </p>
        <div className="flex space-x-3">
          <button onClick={onCancel} className="flex-1 px-4 py-2 bg-gray-200 rounded-lg">
            Cancel
          </button>
          <button onClick={onConfirm} className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg">
            Block User
          </button>
        </div>
      </div>
    </div>
  );
}
```

### 3. Blocked Users Management (Settings Sheet)

Add a "Blocked Users" tab to ChatSettingsSheet:

```typescript
// ChatSettingsSheet.tsx
<TabsContent value="blocked">
  <div className="space-y-4">
    <h3 className="font-semibold text-lg">Blocked Users</h3>
    {blockedUsers.length === 0 ? (
      <p className="text-gray-500">No blocked users</p>
    ) : (
      <div className="space-y-2">
        {blockedUsers.map(blocked => (
          <div key={blocked.participation_id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
            <div>
              <p className="font-medium">@{blocked.username}</p>
              <p className="text-sm text-gray-500">
                Blocked {new Date(blocked.blocked_at).toLocaleDateString()}
              </p>
              {blocked.reason && (
                <p className="text-sm text-gray-600 italic mt-1">{blocked.reason}</p>
              )}
            </div>
            <button
              onClick={() => handleUnblock(blocked.participation_id)}
              className="px-3 py-1 bg-blue-600 text-white text-sm rounded-lg"
            >
              Unblock
            </button>
          </div>
        ))}
      </div>
    )}
  </div>
</TabsContent>
```

### 4. Visual Feedback

**Block Success Toast:**
```typescript
toast.success(`@${username} has been blocked and removed from the chat`);
```

**User Eviction (Frontend):**
```typescript
// When WebSocket receives "blocked" message
socket.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'blocked') {
    toast.error(data.message);
    // Redirect to home page after 2 seconds
    setTimeout(() => {
      router.push('/');
    }, 2000);
  }
};
```

---

## Exhaustive Implementation Checklist

### Phase 1: Database & Models (Backend)

#### 1.1 ChatBlock Model
- [ ] Create `ChatBlock` model in `backend/chats/models.py`
  - [ ] Add `chat_room` ForeignKey to ChatRoom
  - [ ] Add `blocked_by` ForeignKey to ChatParticipation
  - [ ] Add `blocked_username` CharField (max_length=15, null=True, blank=True)
  - [ ] Add `blocked_fingerprint` CharField (max_length=255, null=True, blank=True)
  - [ ] Add `blocked_user` ForeignKey to User (null=True, blank=True)
  - [ ] Add `blocked_email` EmailField (null=True, blank=True)
  - [ ] Add `blocked_phone` CharField (max_length=20, null=True, blank=True)
  - [ ] Add `blocked_at` DateTimeField (auto_now_add=True)
  - [ ] Add `reason` TextField (blank=True)
  - [ ] Add `expires_at` DateTimeField (null=True, blank=True)
  - [ ] Add `__str__` method for admin display

#### 1.2 Model Meta & Constraints
- [ ] Add Meta class to ChatBlock
  - [ ] Add index on `(chat_room, blocked_username)`
  - [ ] Add index on `(chat_room, blocked_fingerprint)`
  - [ ] Add index on `(chat_room, blocked_user)`
  - [ ] Add UniqueConstraint for username blocks
  - [ ] Add UniqueConstraint for fingerprint blocks
  - [ ] Add UniqueConstraint for user account blocks
  - [ ] Add database table name if needed

#### 1.3 Database Migration
- [ ] Run `python manage.py makemigrations`
- [ ] Review generated migration file
- [ ] Run `python manage.py migrate`
- [ ] Verify migration in PostgreSQL
  - [ ] Check table `chats_chatblock` exists
  - [ ] Check all columns are created
  - [ ] Check indexes are created
  - [ ] Check unique constraints are created

#### 1.4 Admin Interface
- [ ] Register ChatBlock in `backend/chats/admin.py`
  - [ ] Add list_display fields
  - [ ] Add list_filter for chat_room, blocked_at
  - [ ] Add search_fields for username, fingerprint
  - [ ] Add readonly_fields for blocked_at
  - [ ] Add fieldsets for organization

---

### Phase 2: Core Blocking Logic (Backend)

#### 2.1 Helper Functions in `backend/chats/utils.py` (or new file)
- [ ] Create `block_participation()` function
  - [ ] Accept parameters: chat_room, participation, blocked_by
  - [ ] Block username (lowercase, use get_or_create)
  - [ ] Block fingerprint (use get_or_create)
  - [ ] Block user account (use get_or_create)
  - [ ] Block email if exists (use get_or_create)
  - [ ] Block phone if exists (use get_or_create)
  - [ ] Return list of created ChatBlock instances
  - [ ] Add error handling for database errors

- [ ] Create `check_if_blocked()` function
  - [ ] Accept parameters: chat_room, username, fingerprint, user, email, phone
  - [ ] Query ChatBlock.objects.filter(chat_room=chat_room)
  - [ ] Filter out expired blocks (check expires_at)
  - [ ] Check username match (case-insensitive)
  - [ ] Check fingerprint match
  - [ ] Check user account match
  - [ ] Check email match (case-insensitive)
  - [ ] Check phone match
  - [ ] Return (is_blocked: bool, error_message: str|None)

- [ ] Create `unblock_participation()` function
  - [ ] Accept parameters: chat_room, participation
  - [ ] Delete all ChatBlock records for this participation
  - [ ] Return count of deleted blocks

- [ ] Create `get_blocked_users()` function
  - [ ] Accept parameter: chat_room
  - [ ] Query all active blocks for chat_room
  - [ ] Group by participation_id
  - [ ] Return list of blocked user summaries

#### 2.2 Prevent Self-Block
- [ ] Add validation in `block_participation()`
  - [ ] Check if blocked_by.user == participation.user
  - [ ] Check if blocked_by.fingerprint == participation.fingerprint
  - [ ] Raise ValidationError if self-block attempt
  - [ ] Return error message to API

---

### Phase 3: API Endpoints (Backend)

#### 3.1 Block User Endpoint
- [ ] Create `BlockUserView` in `backend/chats/views.py`
  - [ ] POST `/api/chats/{code}/block/`
  - [ ] Require authentication or session token
  - [ ] Validate requester is chat host
  - [ ] Get ChatRoom by code
  - [ ] Get ChatParticipation to block by participation_id
  - [ ] Get blocker's ChatParticipation
  - [ ] Call `block_participation()`
  - [ ] Return success response with blocks_created count
  - [ ] Handle errors (not host, participation not found, etc.)

- [ ] Add URL pattern to `backend/chats/urls.py`
  - [ ] Add path for block endpoint

#### 3.2 Unblock User Endpoint
- [ ] Create `UnblockUserView` in `backend/chats/views.py`
  - [ ] DELETE `/api/chats/{code}/block/{participation_id}/`
  - [ ] Require authentication or session token
  - [ ] Validate requester is chat host
  - [ ] Get ChatRoom by code
  - [ ] Get ChatParticipation to unblock by participation_id
  - [ ] Call `unblock_participation()`
  - [ ] Return success response with blocks_removed count
  - [ ] Handle errors (not host, participation not found, etc.)

- [ ] Add URL pattern to `backend/chats/urls.py`
  - [ ] Add path for unblock endpoint

#### 3.3 List Blocked Users Endpoint
- [ ] Create `BlockedUsersListView` in `backend/chats/views.py`
  - [ ] GET `/api/chats/{code}/blocked/`
  - [ ] Require authentication or session token
  - [ ] Validate requester is chat host
  - [ ] Get ChatRoom by code
  - [ ] Call `get_blocked_users()`
  - [ ] Serialize blocked user data
  - [ ] Return JSON response
  - [ ] Handle errors (not host, etc.)

- [ ] Add URL pattern to `backend/chats/urls.py`
  - [ ] Add path for blocked users list endpoint

#### 3.4 Serializers
- [ ] Create `ChatBlockSerializer` in `backend/chats/serializers.py`
  - [ ] Add fields for all ChatBlock attributes
  - [ ] Add SerializerMethodField for blocked_identifiers list
  - [ ] Add SerializerMethodField for username display

---

### Phase 4: Block Enforcement (Backend)

#### 4.1 Chat Join Prevention
- [ ] Modify `JoinChatView` in `backend/chats/views.py`
  - [ ] After validating chat exists and before creating participation
  - [ ] Extract username, fingerprint, user from request
  - [ ] Extract email, phone if provided (future)
  - [ ] Call `check_if_blocked()`
  - [ ] If blocked, return 403 Forbidden with error message
  - [ ] If not blocked, continue with join logic

#### 4.2 Message Send Prevention (WebSocket)
- [ ] Modify `ChatConsumer` in `backend/chats/consumers.py`
  - [ ] Add `check_blocked()` method (database_sync_to_async)
  - [ ] In `receive()`, check if user is blocked before processing message
  - [ ] If blocked, send error message to client
  - [ ] If blocked, close WebSocket connection
  - [ ] If not blocked, continue with message processing

---

### Phase 5: Real-Time Eviction (Backend)

#### 5.1 WebSocket Event Emission
- [ ] Modify `block_participation()` function
  - [ ] After creating blocks, emit `user_blocked` event
  - [ ] Use `channel_layer.group_send()`
  - [ ] Send to chat group: `f"chat_{chat_room.code}"`
  - [ ] Include blocked_username, blocked_fingerprint, blocked_user_id in event

#### 5.2 WebSocket Event Handler
- [ ] Add `user_blocked()` method to `ChatConsumer`
  - [ ] Receive event with blocked identifiers
  - [ ] Check if this consumer's user matches blocked identifiers
  - [ ] If match, send 'blocked' message to client
  - [ ] If match, close WebSocket connection
  - [ ] If no match, do nothing

---

### Phase 6: Frontend API Client (TypeScript)

#### 6.1 API Functions in `frontend/src/lib/api.ts`
- [ ] Add `blockUser()` function
  - [ ] Accept chatCode, participationId, reason (optional)
  - [ ] Make POST request to `/api/chats/{code}/block/`
  - [ ] Return Promise with success response
  - [ ] Handle errors and throw

- [ ] Add `unblockUser()` function
  - [ ] Accept chatCode, participationId
  - [ ] Make DELETE request to `/api/chats/{code}/block/{participation_id}/`
  - [ ] Return Promise with success response
  - [ ] Handle errors and throw

- [ ] Add `getBlockedUsers()` function
  - [ ] Accept chatCode
  - [ ] Make GET request to `/api/chats/{code}/blocked/`
  - [ ] Return Promise with blocked users list
  - [ ] Handle errors and throw

#### 6.2 TypeScript Types
- [ ] Add `BlockedUser` interface
  - [ ] participation_id: string
  - [ ] username: string
  - [ ] blocked_at: string
  - [ ] reason?: string
  - [ ] blocked_identifiers: string[]

- [ ] Add `BlockUserRequest` interface
  - [ ] participation_id: string
  - [ ] reason?: string

---

### Phase 7: Frontend UI Components

#### 7.1 Block Confirmation Modal
- [ ] Create `BlockConfirmModal.tsx` component
  - [ ] Accept props: isOpen, username, onConfirm, onCancel
  - [ ] Render modal with warning message
  - [ ] Show username being blocked
  - [ ] Show explanation of what will be blocked
  - [ ] Add Cancel button
  - [ ] Add Block User button (red/danger style)
  - [ ] Add optional reason input field
  - [ ] Handle modal close on backdrop click
  - [ ] Add proper z-index for overlay

#### 7.2 Message Actions Modal Updates
- [ ] Modify `MessageActionsModal.tsx`
  - [ ] Add `isHost` prop or check if current user is host
  - [ ] Add "Block User" button (only show if isHost)
  - [ ] Use Ban icon from lucide-react
  - [ ] Style button with red color
  - [ ] On click, open BlockConfirmModal
  - [ ] Pass message.user_id to block function

#### 7.3 Blocked Users List in Settings
- [ ] Modify `ChatSettingsSheet.tsx`
  - [ ] Add new tab: "Blocked Users"
  - [ ] Add TabsTrigger for "Blocked Users" (only show if isHost)
  - [ ] Add TabsContent for "Blocked Users"
  - [ ] Fetch blocked users list on tab open
  - [ ] Display loading state while fetching
  - [ ] Display empty state if no blocked users
  - [ ] Map over blocked users and render cards
  - [ ] Show username, blocked_at, reason, blocked_identifiers
  - [ ] Add Unblock button for each user
  - [ ] Handle unblock click with confirmation

#### 7.4 Block/Unblock Logic in Page Component
- [ ] Modify `frontend/src/app/chat/[code]/page.tsx`
  - [ ] Add state for blockConfirmModal visibility
  - [ ] Add state for selected user to block
  - [ ] Add state for blocked users list
  - [ ] Add `handleBlockUser()` function
    - [ ] Show confirmation modal
  - [ ] Add `handleConfirmBlock()` function
    - [ ] Call blockUser API
    - [ ] Show success toast
    - [ ] Close modal
    - [ ] Update blocked users list
  - [ ] Add `handleUnblock()` function
    - [ ] Call unblockUser API
    - [ ] Show success toast
    - [ ] Update blocked users list
  - [ ] Add `fetchBlockedUsers()` function
    - [ ] Call getBlockedUsers API
    - [ ] Update state

---

### Phase 8: WebSocket Eviction Handling (Frontend)

#### 8.1 WebSocket Message Handling
- [ ] Modify `useChatWebSocket.ts` hook
  - [ ] In onmessage handler, check for `type: 'blocked'`
  - [ ] If blocked message received, show error toast
  - [ ] If blocked message received, disconnect WebSocket
  - [ ] If blocked message received, redirect to home page after 2s

#### 8.2 User Feedback
- [ ] Add toast notification for blocked users
  - [ ] Show "You have been removed from this chat"
  - [ ] Use error toast style
  - [ ] Auto-dismiss after 2 seconds
  - [ ] Redirect to home page after toast dismisses

---

### Phase 9: Testing (Backend)

#### 9.1 Unit Tests for Block Logic
- [ ] Create `backend/chats/tests_blocking.py`
- [ ] Test `block_participation()` function
  - [ ] Test creates username block
  - [ ] Test creates fingerprint block
  - [ ] Test creates user account block
  - [ ] Test returns list of created blocks
  - [ ] Test handles duplicate blocks (get_or_create)
  - [ ] Test prevents self-block

- [ ] Test `check_if_blocked()` function
  - [ ] Test detects username block (case-insensitive)
  - [ ] Test detects fingerprint block
  - [ ] Test detects user account block
  - [ ] Test returns False when not blocked
  - [ ] Test respects expires_at field
  - [ ] Test expired blocks are ignored

- [ ] Test `unblock_participation()` function
  - [ ] Test deletes all blocks for participation
  - [ ] Test returns correct count
  - [ ] Test handles participation with no blocks

#### 9.2 API Endpoint Tests
- [ ] Test BlockUserView
  - [ ] Test host can block user
  - [ ] Test non-host cannot block user
  - [ ] Test requires authentication
  - [ ] Test returns 403 for non-host
  - [ ] Test returns 201 on success
  - [ ] Test creates multiple ChatBlock records

- [ ] Test UnblockUserView
  - [ ] Test host can unblock user
  - [ ] Test non-host cannot unblock user
  - [ ] Test requires authentication
  - [ ] Test returns 200 on success
  - [ ] Test deletes ChatBlock records

- [ ] Test BlockedUsersListView
  - [ ] Test host can list blocked users
  - [ ] Test non-host cannot list blocked users
  - [ ] Test returns correct blocked users
  - [ ] Test returns empty list when none blocked

#### 9.3 Integration Tests
- [ ] Test Chat Join Prevention
  - [ ] Test blocked username cannot join
  - [ ] Test blocked fingerprint cannot join
  - [ ] Test blocked user account cannot join
  - [ ] Test returns 403 Forbidden
  - [ ] Test non-blocked user can join

- [ ] Test WebSocket Message Prevention
  - [ ] Test blocked user cannot send message
  - [ ] Test WebSocket connection closes
  - [ ] Test error message sent to client

- [ ] Test Real-Time Eviction
  - [ ] Test user_blocked event emitted on block
  - [ ] Test WebSocket disconnects blocked user
  - [ ] Test blocked user receives 'blocked' message

#### 9.4 Edge Case Tests
- [ ] Test user changes username but same fingerprint (still blocked)
- [ ] Test user clears cookies but same username (still blocked)
- [ ] Test user creates new account but same device (still blocked)
- [ ] Test host cannot block themselves
- [ ] Test blocking anonymous user
- [ ] Test blocking logged-in user
- [ ] Test blocking user with both username and account
- [ ] Test duplicate block attempts (idempotent)
- [ ] Test block expiration (timed blocks)

#### 9.5 Test Coverage
- [ ] Run tests: `python manage.py test chats.tests_blocking`
- [ ] Verify all tests pass
- [ ] Check code coverage with pytest-cov
- [ ] Aim for >90% coverage on blocking logic

---

### Phase 10: Testing (Frontend)

#### 10.1 Manual Testing
- [ ] Test block button appears for host
- [ ] Test block button hidden for non-host
- [ ] Test block confirmation modal opens
- [ ] Test block confirmation modal closes on cancel
- [ ] Test block success toast appears
- [ ] Test blocked user removed from chat
- [ ] Test blocked user redirected to home
- [ ] Test unblock button works
- [ ] Test blocked users list displays correctly
- [ ] Test empty state for blocked users list

#### 10.2 E2E Testing (Optional)
- [ ] Write E2E test for blocking flow
  - [ ] Create chat as host
  - [ ] Join chat as second user
  - [ ] Block second user from host account
  - [ ] Verify second user disconnected
  - [ ] Verify second user cannot rejoin
  - [ ] Unblock second user
  - [ ] Verify second user can rejoin

---

### Phase 11: Documentation

#### 11.1 Code Documentation
- [ ] Add docstrings to `block_participation()`
- [ ] Add docstrings to `check_if_blocked()`
- [ ] Add docstrings to `unblock_participation()`
- [ ] Add docstrings to API views
- [ ] Add comments to WebSocket event handlers
- [ ] Add JSDoc comments to frontend functions

#### 11.2 README Updates
- [ ] Update `README.md` with blocking feature
- [ ] Document API endpoints
- [ ] Add example API requests/responses
- [ ] Document WebSocket events
- [ ] Add screenshots of block UI (optional)

#### 11.3 CLAUDE.md Updates
- [ ] Add blocking feature to CLAUDE.md
- [ ] Document ChatBlock model
- [ ] Document block enforcement points
- [ ] Document testing requirements
- [ ] Add to feature list

---

### Phase 12: Performance & Security

#### 12.1 Database Optimization
- [ ] Verify indexes are created
  - [ ] Check `idx_chatblock_username`
  - [ ] Check `idx_chatblock_fingerprint`
  - [ ] Check `idx_chatblock_user`
- [ ] Run EXPLAIN on block check queries
- [ ] Verify query performance <5ms
- [ ] Add database indexes for expires_at if using timed blocks

#### 12.2 Rate Limiting
- [ ] Add rate limiting to block endpoint (10 blocks per hour per host)
- [ ] Add rate limiting to unblock endpoint (10 unblocks per hour per host)
- [ ] Use Django rate limiting decorator or custom middleware

#### 12.3 Security Audit
- [ ] Verify only host can block users
- [ ] Verify host cannot block themselves
- [ ] Verify blocked user email/phone not exposed in API
- [ ] Verify block check is secure (no SQL injection)
- [ ] Verify WebSocket disconnection works
- [ ] Test for CSRF vulnerabilities
- [ ] Test for authorization bypass attempts

---

### Phase 13: Deployment Prep

#### 13.1 Migration Checklist
- [ ] Run migration on staging environment
- [ ] Verify no errors
- [ ] Verify indexes created
- [ ] Verify constraints work
- [ ] Backup database before production migration

#### 13.2 Environment Variables
- [ ] Add any new config to `.env.example`
- [ ] Document environment variables in README
- [ ] Set production environment variables

#### 13.3 Monitoring
- [ ] Add logging for block/unblock actions
- [ ] Add metrics for block events
- [ ] Set up alerts for unusual blocking activity
- [ ] Monitor WebSocket disconnection errors

---

### Phase 14: Future Enhancements (Phase 4)

#### 14.1 Email/Phone Fields
- [ ] Add `contact_email` to ChatParticipation model
- [ ] Add `contact_phone` to ChatParticipation model
- [ ] Add migrations for new fields
- [ ] Update `block_participation()` to block email
- [ ] Update `block_participation()` to block phone
- [ ] Update `check_if_blocked()` to check email
- [ ] Update `check_if_blocked()` to check phone
- [ ] Add cross-participation blocking by email
- [ ] Add cross-participation blocking by phone

#### 14.2 Host Requirements
- [ ] Add `require_email` to ChatRoom model
- [ ] Add `require_phone` to ChatRoom model
- [ ] Add migrations for new fields
- [ ] Update join flow to collect email if required
- [ ] Update join flow to collect phone if required
- [ ] Add email/phone validation
- [ ] Update JoinChatModal to show email/phone inputs

#### 14.3 Timed Blocks
- [ ] Add UI for selecting block duration
  - [ ] Block permanently (default)
  - [ ] Block for 24 hours
  - [ ] Block for 7 days
  - [ ] Block for 30 days
- [ ] Update block API to accept expires_at
- [ ] Add cron job to clean up expired blocks (optional)
- [ ] Show time remaining on blocked users list

#### 14.4 Redis Caching (Performance)
- [ ] Implement `is_blocked_cached()` function
- [ ] Cache blocked usernames in Redis Set
- [ ] Cache blocked fingerprints in Redis Set
- [ ] Cache blocked user IDs in Redis Set
- [ ] Add cache invalidation on block/unblock
- [ ] Monitor cache hit rate
- [ ] Benchmark performance improvement

---

### Phase 15: Final Review & Launch

- [ ] Code review with team
- [ ] Security review
- [ ] Performance testing
- [ ] Load testing (block checks under high traffic)
- [ ] User acceptance testing
- [ ] Final documentation review
- [ ] Deploy to production
- [ ] Monitor for errors
- [ ] Announce feature to users
- [ ] Gather user feedback
- [ ] Iterate based on feedback

---

## Progress Tracking

**Total Tasks:** 200+
**Completed:** 0
**In Progress:** 0
**Blocked:** 0

**Estimated Time:**
- Phase 1-3 (Database, Logic, API): 8-12 hours
- Phase 4-5 (Enforcement, Eviction): 4-6 hours
- Phase 6-8 (Frontend): 8-12 hours
- Phase 9-10 (Testing): 6-10 hours
- Phase 11-13 (Docs, Security, Deployment): 4-6 hours
- Phase 14 (Future Enhancements): 8-12 hours

**Total Estimated Time:** 38-58 hours

---

## Open Questions

1. **Should blocks be permanent or temporary?**
   - **Decision:** Support both. Add optional `expires_at` field for timed blocks.
   - Host can choose "Block permanently" or "Block for 24 hours / 7 days / 30 days"

2. **Should blocked users know they're blocked?**
   - **Decision:** Generic message "You cannot access this chat" to avoid harassment
   - Don't explicitly say "You have been blocked by the host"

3. **Do we hide their past messages?**
   - **Decision:** Keep past messages visible (for context)
   - Only prevent new messages and chat access
   - Host can separately delete individual messages if needed

4. **Who can block?**
   - **Decision:** Host-only blocking for MVP
   - Personal block lists can be added in Phase 5 if needed

5. **Performance considerations?**
   - Block checks should be fast (<5ms) with proper database indexes
   - Consider caching blocked user list in Redis for high-traffic chats
   - Index on `(chat_room, blocked_username)`, `(chat_room, blocked_fingerprint)`, `(chat_room, blocked_user)`

---

## Testing Considerations

### Unit Tests
- Test `block_participation()` creates correct blocks
- Test `check_if_blocked()` detects blocks correctly
- Test case-insensitive username blocking
- Test cross-participation blocking by email/phone

### Integration Tests
- Test blocked user cannot join chat
- Test blocked user cannot send messages
- Test real-time eviction via WebSocket
- Test unblock restores access
- Test host-only permission enforcement

### Edge Cases
- User changes username but same fingerprint (still blocked)
- User clears cookies but same username (still blocked)
- User creates new account but same device (still blocked)
- Host accidentally blocks themselves (prevent this)
- Multiple hosts blocking same user (deduplicate blocks)

---

## Security Considerations

1. **Authorization:** Only chat host can block users
2. **Self-Block Prevention:** Prevent host from blocking themselves
3. **Rate Limiting:** Limit block/unblock actions to prevent abuse
4. **Audit Trail:** Log all block/unblock actions with timestamps
5. **Privacy:** Don't expose blocked user's email/phone in API responses

---

## Database Indexes

```sql
-- Username blocks (case-insensitive)
CREATE INDEX idx_chatblock_username ON chats_chatblock (chat_room_id, LOWER(blocked_username));

-- Fingerprint blocks
CREATE INDEX idx_chatblock_fingerprint ON chats_chatblock (chat_room_id, blocked_fingerprint);

-- User account blocks
CREATE INDEX idx_chatblock_user ON chats_chatblock (chat_room_id, blocked_user_id);

-- Email blocks (case-insensitive, future)
CREATE INDEX idx_chatblock_email ON chats_chatblock (chat_room_id, LOWER(blocked_email));

-- Phone blocks (future)
CREATE INDEX idx_chatblock_phone ON chats_chatblock (chat_room_id, blocked_phone);

-- Expiration check
CREATE INDEX idx_chatblock_expires ON chats_chatblock (expires_at) WHERE expires_at IS NOT NULL;
```

---

## Performance Optimization

### Caching Strategy (Future)

For high-traffic chats, cache blocked identifiers in Redis:

```python
# Cache key format: chat:{code}:blocked:{type}
# Example: chat:ABC123:blocked:usernames -> Set(['spammer', 'troll123'])

def is_blocked_cached(chat_code, username=None, fingerprint=None, user_id=None):
    """Check if user is blocked using Redis cache."""
    cache_key_prefix = f"chat:{chat_code}:blocked"

    if username:
        blocked_usernames = cache.smembers(f"{cache_key_prefix}:usernames")
        if username.lower() in blocked_usernames:
            return True

    if fingerprint:
        blocked_fingerprints = cache.smembers(f"{cache_key_prefix}:fingerprints")
        if fingerprint in blocked_fingerprints:
            return True

    if user_id:
        blocked_users = cache.smembers(f"{cache_key_prefix}:users")
        if str(user_id) in blocked_users:
            return True

    return False

# Invalidate cache on block/unblock
def invalidate_block_cache(chat_code):
    cache.delete_pattern(f"chat:{chat_code}:blocked:*")
```
