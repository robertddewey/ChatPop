# System Architecture

This document covers advanced architectural patterns and business logic in ChatPop.

---

## Table of Contents

1. [Dual Sessions Architecture](#dual-sessions-architecture)
2. [Username Validation Rules](#username-validation-rules)
3. [IP-Based Rate Limiting](#ip-based-rate-limiting)

---

## Dual Sessions Architecture

### Overview

ChatPop implements a dual sessions architecture that allows users to have separate anonymous and logged-in participations in the same chat. This enables flexible user journeys while preventing abuse through IP-based rate limiting.

**Key Principle:** Logged-in and anonymous users are treated as separate entities, even when using the same device/fingerprint.

### Implementation Details

**1. Anonymous Users** (`views.py:544-565`)
- Identified by browser fingerprint
- Participation has `user=null` and stores `fingerprint`
- Can join any chat without registration
- Username persists across sessions via fingerprint

**2. Logged-In Users** (`views.py:544-565`)
- Identified by authenticated user account
- Participation has `user=<User>` (fingerprint optional)
- Reserved username with verified badge available
- Username persists via user account

**3. Participation Priority** (`views.py:550-565`)
- `MyParticipationView` checks for logged-in participation first
- If authenticated: only check for `user`-based participation
- If anonymous: only check for `fingerprint`-based participation where `user__isnull=True`
- **No fallback** from logged-in to anonymous

**4. Username Coexistence** (`views.py:139-155`)
- Anonymous user "robert" and logged-in user "Robert" can coexist
- Separate participation records in same chat
- Case-insensitive matching within each user type (anonymous vs logged-in)
- Enables upgrade path: join anonymously → register → get verified badge

### Reserved Username Badge

**Badge Logic** (`views.py:570-573`):
```python
username_is_reserved = (participation.username.lower() == participation.user.reserved_username.lower())
```

- Badge shown when participation username matches user's reserved_username (case-insensitive)
- Only applies to logged-in users (anonymous users never have badge)
- Displayed in UI with BadgeCheck icon (frontend)

### User Journey Examples

**Scenario 1: Anonymous → Registered with Same Username**
1. User joins chat anonymously as "robert" (no badge)
2. User registers account with reserved_username="robert"
3. User returns to chat as logged-in user
4. `MyParticipationView` shows no participation (logged-in session doesn't see anonymous)
5. User joins as "Robert" (creates new logged-in participation)
6. Badge displays because "Robert" matches reserved_username (case-insensitive)
7. Both participations coexist: anonymous "robert" and verified "Robert"

**Scenario 2: IP Rate Limiting**
1. Anonymous user from IP 192.168.1.100 joins as "user1"
2. Same IP joins as "user2" (fingerprint2)
3. Same IP joins as "user3" (fingerprint3)
4. Same IP tries to join as "user4" → **BLOCKED** (max 3 reached)
5. Original user (fingerprint1) tries to rejoin → **ALLOWED** (returning user)
6. User logs in and joins → **ALLOWED** (logged-in users exempt)

### Database Schema

**ChatParticipation Model** (`models.py:253-270`):
```python
user = ForeignKey(User, null=True, blank=True)  # Logged-in user
fingerprint = CharField(max_length=255, null=True, blank=True)  # Anonymous identifier
username = CharField(max_length=15)  # Chat username (may differ from reserved_username)
ip_address = GenericIPAddressField(null=True, blank=True)  # For rate limiting
```

**Unique Constraint** (`models.py:289-294`):
- User-based participation: unique per (chat_room, user)
- Anonymous participation: unique per (chat_room, fingerprint) where user is null

### Testing

Comprehensive test suite in `backend/chats/tests_dual_sessions.py` (16 tests):

**Dual Sessions Tests (6 tests):**
- Anonymous and logged-in join create separate participations
- Same username coexistence (case-insensitive)
- Participation priority and no-fallback logic

**Reserved Username Badge Tests (4 tests):**
- Exact and case-insensitive match detection
- Badge not shown for different usernames or anonymous users

**IP Rate Limiting Tests (6 tests):**
- 3-username limit enforcement
- Returning user exemption
- Logged-in user exemption
- Per-IP and per-chat isolation

Run tests:
```bash
./venv/bin/python manage.py test chats.tests_dual_sessions
```

---

## Username Validation Rules

### Overview

**Unified Validation:** The same validation rules apply to both reserved usernames (registration) and chat usernames (anonymous users).

### Rules

- **Minimum Length:** 5 characters (more than 4)
- **Maximum Length:** 15 characters
- **Allowed Characters:** Letters (a-z, A-Z), numbers (0-9), and underscores (_)
- **Disallowed Characters:** Spaces and all special characters except underscore
- **Case Handling:**
  - Case is **preserved** in storage and display (e.g., "Alice" stays "Alice")
  - Uniqueness checks are **case-insensitive** (e.g., cannot have both "Alice" and "alice")

### Implementation Files

- **Backend Validator:** `/backend/chats/validators.py` - Shared validation function used by both registration and chat join serializers
- **Frontend Validator:** `/frontend/src/lib/validation.ts` - Client-side validation matching backend rules
- **Test Suite:** `/backend/chats/tests_validators.py` - 10 test cases covering all validation scenarios
- **Security Tests:** `/backend/chats/tests_security.py` - Includes case preservation tests for both reserved and anonymous usernames

### Usage in Serializers

```python
from chats.validators import validate_username

def validate_reserved_username(self, value):
    """Validate reserved username format and uniqueness"""
    if value:
        value = validate_username(value)  # Format validation
        # Check case-insensitive uniqueness
        if User.objects.filter(reserved_username__iexact=value).exists():
            raise serializers.ValidationError("This username is already reserved")
    return value
```

### Frontend Usage

```typescript
import { validateUsername } from '@/lib/validation';

const validation = validateUsername(username);
if (!validation.isValid) {
  setError(validation.error || 'Invalid username');
  return;
}
```

### Testing

Run validation tests:
```bash
./venv/bin/python manage.py test chats.tests_validators
```

---

## IP-Based Rate Limiting

### Overview

**Purpose:** Prevent abuse by limiting anonymous username creation from a single IP address.

**Implementation** (`views.py:98-125`):

```python
MAX_ANONYMOUS_USERNAMES_PER_IP_PER_CHAT = 3
```

### Rules

1. **Limit Scope:** 3 anonymous usernames per IP per chat
2. **Exemptions:**
   - Returning users (existing fingerprint) can always rejoin
   - Logged-in users not affected by limit
3. **Enforcement:**
   - Check runs before creating new anonymous participation
   - Returns 400 Bad Request with clear error message
4. **IP Storage:**
   - Raw IP addresses stored in `ChatParticipation.ip_address`
   - Updated on every join/rejoin
   - Used for rate limiting queries

### Example Use Cases

- ✅ User joins as "alice" → joins as "bob" → joins as "charlie" (3rd username, allowed)
- ❌ User tries to join as "david" (4th username, blocked)
- ✅ User with fingerprint for "alice" rejoins (returning user, allowed)
- ✅ User logs in and joins as "eve" (logged-in user, not counted)
- ✅ Different IP can create 3 new usernames (per-IP limit)

### Implementation Details

**Query Logic** (`views.py:98-125`):
```python
# Count existing anonymous usernames from this IP in this chat
existing_count = ChatParticipation.objects.filter(
    chat_room=chat_room,
    ip_address=ip_address,
    user__isnull=True  # Only count anonymous users
).values('fingerprint').distinct().count()

if existing_count >= MAX_ANONYMOUS_USERNAMES_PER_IP_PER_CHAT:
    # Check if this is a returning user
    if not ChatParticipation.objects.filter(
        chat_room=chat_room,
        fingerprint=fingerprint,
        user__isnull=True
    ).exists():
        raise ValidationError("Maximum anonymous usernames per IP reached")
```

### Testing

Run IP rate limiting tests:
```bash
./venv/bin/python manage.py test chats.tests_dual_sessions.IPRateLimitingTests
```

---

## Related Documentation

- **Testing:** [docs/TESTING.md](./TESTING.md) - Test suite for dual sessions, validation, and rate limiting
- **Caching:** [docs/CACHING.md](./CACHING.md) - Redis caching architecture
- **Security:** See test documentation for JWT session security details

---

**Last Updated:** 2025-01-10
