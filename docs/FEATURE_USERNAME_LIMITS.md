# Username Reservation with Configurable TTL

**Feature:** Custom Username Reservation with Race Condition Prevention
**Status:** ✅ Completed
**Last Updated:** 2025-10-14

---

## Overview

This document describes the username reservation system that prevents race conditions during registration and chat join flows. When users validate custom usernames, the system temporarily reserves them in Redis to prevent concurrent users from claiming the same username.

---

## Dual TTL Strategy

The system uses two different Time-To-Live (TTL) settings for username reservations:

### 1. Generated Usernames (Longer TTL)

**Use Case:** Random usernames generated via the "dice roll" button
**TTL:** 60 minutes (default) - Configurable via `USERNAME_RESERVATION_TTL_MINUTES`
**Rationale:** Users may need time for email verification, form completion, etc.

**Constance Setting:**
```python
'USERNAME_RESERVATION_TTL_MINUTES': (
    60,
    'How long generated usernames are reserved in Redis (minutes). Gives users time to complete registration/join chat. Used for both anonymous and registered user flows.',
    int
)
```

### 2. Custom Usernames (Shorter TTL)

**Use Case:** User-entered custom usernames validated in real-time
**TTL:** 10 minutes (default) - Configurable via `USERNAME_VALIDATION_TTL_MINUTES`
**Rationale:** User is actively filling out the form, shorter reservation is sufficient

**Constance Setting:**
```python
'USERNAME_VALIDATION_TTL_MINUTES': (
    10,
    'How long custom usernames are reserved after real-time validation (minutes). Prevents race conditions during form submission where two users try to register the same username.',
    int
)
```

---

## Implementation Details

### Files Modified

**Configuration:**
- `/backend/chatpop/settings.py:276-286` - Added two Constance TTL settings

**Username Generation:**
- `/backend/chats/utils/username/generator.py:50` - Updated to use Constance `USERNAME_RESERVATION_TTL_MINUTES` instead of hardcoded 3600 seconds

**Registration Validation:**
- `/backend/accounts/views.py:12-15` - Added imports for validators, generator, cache, and config
- `/backend/accounts/views.py:126-153` - Updated `CheckUsernameView` to:
  - Use `is_username_globally_available()` for comprehensive checking
  - Reserve available usernames in Redis with `USERNAME_VALIDATION_TTL_MINUTES` TTL
  - Prevent race conditions during registration

**Chat Join Validation:**
- `/backend/chats/views.py:966-982` - Updated `UsernameValidationView` to:
  - Reserve available usernames in Redis with `USERNAME_VALIDATION_TTL_MINUTES` TTL
  - Prevent race conditions during chat join

**Tests:**
- `/backend/chats/tests/tests_username_generation.py:515-828` - Added 13 new tests:
  - 6 tests for CheckUsernameView Redis reservation behavior
  - 7 tests for UsernameValidationView Redis reservation behavior

---

## API Endpoints

### 1. Registration Username Check

**Endpoint:** `GET /api/auth/check-username/?username={username}`

**Behavior:**
1. Validates username format and profanity
2. Checks global availability (User.reserved_username + ChatParticipation.username + Redis reservations)
3. If available, reserves username in Redis for 10 minutes (configurable)
4. Returns availability status

**Response:**
```json
{
  "available": true,
  "message": "Username is available"
}
```

**Race Condition Prevention:**
- User A checks "CoolUser" → Available, reserved in Redis
- User B checks "CoolUser" 1 second later → Unavailable (reserved by User A)
- User A has 10 minutes to complete registration before reservation expires

### 2. Chat Join Username Validation

**Endpoint:** `POST /api/chats/{code}/validate-username/`

**Request Body:**
```json
{
  "username": "CoolUser"
}
```

**Behavior:**
1. Validates username format and profanity
2. Checks if reserved by another user
3. Checks if used in this chat
4. If available, reserves username in Redis for 10 minutes (configurable)
5. Returns detailed availability information

**Response:**
```json
{
  "available": true,
  "username": "CoolUser",
  "in_use_in_chat": false,
  "reserved_by_other": false,
  "has_reserved_badge": false,
  "message": "Username validated successfully"
}
```

---

## Redis Key Patterns

**Username Reservations:**
```
username:reserved:{username_lower}  # TTL: 10 min or 60 min
```

**Generated Username Tracking:**
```
username:generation_attempts:{fingerprint}    # TTL: 60 min
username:generated_for_fingerprint:{fingerprint}  # TTL: 60 min
```

**Chat-Specific Suggestions:**
```
chat:{chat_code}:recent_suggestions  # TTL: 30 minutes
```

---

## Test Coverage

**Test File:** `/backend/chats/tests/tests_username_generation.py`

**New Test Classes:**

### CheckUsernameRedisReservationTestCase (6 tests)
- `test_available_username_reserved_in_redis` - Verifies Redis reservation on successful validation
- `test_unavailable_username_not_reserved` - Confirms taken usernames aren't reserved
- `test_invalid_username_not_reserved` - Invalid usernames shouldn't be reserved
- `test_race_condition_prevention` - Second user sees first user's reservation
- `test_constance_ttl_setting_used` - Verifies Constance integration
- `test_case_insensitive_reservation` - Case-insensitive reservation behavior

### UsernameValidationRedisReservationTestCase (7 tests)
- `test_available_username_reserved_in_redis` - Verifies Redis reservation on successful validation
- `test_unavailable_username_not_reserved` - Confirms taken usernames aren't reserved
- `test_invalid_username_not_reserved` - Invalid usernames shouldn't be reserved
- `test_race_condition_prevention` - Second user sees first user's reservation
- `test_constance_ttl_setting_used` - Verifies Constance integration
- `test_case_insensitive_reservation` - Case-insensitive reservation behavior
- `test_reserved_username_detected` - Checks User.reserved_username detection

**Running Tests:**
```bash
cd backend
./venv/bin/python manage.py test chats.tests.tests_username_generation -v 2
```

**Test Results:**
```
Ran 37 tests in 2.398s

OK
```

---

## Configuration

**Location:** Django Admin → Constance → Config (`/admin/constance/config/`)

**Adjustable Settings:**
- `USERNAME_RESERVATION_TTL_MINUTES` (int) - TTL for generated usernames (default: 60 minutes)
- `USERNAME_VALIDATION_TTL_MINUTES` (int) - TTL for custom usernames (default: 10 minutes)

**Recommendations:**
- **Development:** Keep defaults (60 minutes, 10 minutes)
- **Production:** Adjust based on user behavior analysis
  - If users take longer to complete registration → Increase `USERNAME_VALIDATION_TTL_MINUTES`
  - If rapid username turnover is needed → Decrease `USERNAME_RESERVATION_TTL_MINUTES`

---

## Security Considerations

1. **Case-Insensitive Reservations:**
   - All Redis keys use `username.lower()` to prevent case-based bypasses
   - "CoolUser", "cooluser", "COOLUSER" all map to same reservation

2. **Atomic Operations:**
   - Redis SET operations are atomic, preventing simultaneous reservations
   - First successful SET wins, subsequent attempts see existing reservation

3. **Automatic Expiration:**
   - Redis TTL ensures abandoned reservations don't permanently lock usernames
   - No manual cleanup required

4. **Global Uniqueness:**
   - `is_username_globally_available()` checks all three sources:
     - `User.reserved_username` (registered users)
     - `ChatParticipation.username` (active chat participants)
     - Redis temporary reservations

---

## Monitoring

**Redis Key Inspection:**
```bash
# Check if username is reserved
redis-cli GET "username:reserved:cooluser"

# Check reservation TTL
redis-cli TTL "username:reserved:cooluser"

# List all reserved usernames (use with caution in production)
redis-cli KEYS "username:reserved:*"
```

**Expected Values:**
- Successful reservation: `"true"` (stored as string)
- TTL: 600 seconds (10 min) or 3600 seconds (60 min)
- Expired reservation: `nil`

---

## Future Enhancements

1. **Analytics Dashboard:**
   - Track reservation expiration rates
   - Monitor race condition prevention effectiveness
   - Identify popular username patterns

2. **Dynamic TTL Adjustment:**
   - Adjust TTL based on system load
   - Shorter TTL during high traffic
   - Longer TTL during low traffic

3. **Reservation Notifications:**
   - Notify users when their reservation is about to expire
   - Allow manual reservation extension

---

## Related Documentation

- [ARCHITECTURE.md](./ARCHITECTURE.md) - Global Username System architecture
- [TESTING.md](./TESTING.md) - Complete test suite documentation
- [FEATURE_USERNAME_LIMITS_PROGRESS.md](./FEATURE_USERNAME_LIMITS_PROGRESS.md) - Implementation progress tracking
