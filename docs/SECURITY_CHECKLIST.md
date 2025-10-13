# Security Checklist - User Blocking Feature

This document tracks known vulnerabilities, security tests, and ongoing security work for the ChatPop user blocking feature.

## Running Security Tests

### Quick Test Commands

```bash
cd /Users/robertdewey/GitProjects/ChatPop/backend

# Run basic functional tests (6 tests)
python3 test_user_blocking.py

# Run adversarial security tests (11 tests)
python3 test_user_blocking_adversarial.py

# Run all Django unit tests
./venv/bin/python manage.py test

# Run specific test suite
./venv/bin/python manage.py test chats.tests.tests_security
```

### Test Suites

| Test File | Purpose | Test Count | Last Run | Status |
|-----------|---------|------------|----------|--------|
| `test_user_blocking.py` | Basic functionality | 6 tests | 2025-01-12 | 5/6 passing |
| `test_user_blocking_adversarial.py` | Security vulnerabilities | 11 tests | 2025-01-12 | 6/11 passing |

---

## Known Vulnerabilities (As of 2025-01-12)

### 🔴 CRITICAL - Unicode Homoglyph Attack

**Status:** VULNERABLE
**Test:** `test_user_blocking_adversarial.py::test_unicode_homoglyph_bypass()`

**Description:**
An attacker can bypass blocking by using visually identical Unicode characters from different scripts (e.g., Cyrillic 'і' instead of Latin 'i').

**Attack Vector:**
```python
# User blocks "Victim"
# Attacker uses "Vіctim" (with Cyrillic і)
# System treats these as different usernames
```

**Impact:**
- Blocking is completely bypassed
- Harasser can continue messaging with nearly identical username
- User has no way to detect the difference visually

**Fix Required:**
- Implement Unicode normalization (NFKC) in validation layer
- Apply normalization before storage AND comparison
- Consider restricting to ASCII-only usernames

**Files to Modify:**
- `chats/models.py` - UserBlock model validation
- `chats/user_block_views.py` - Input normalization
- `chats/consumers.py` - WebSocket filtering normalization
- `chats/utils/validators.py` - Create username normalization utility

---

### 🔴 HIGH - Whitespace Manipulation

**Status:** VULNERABLE
**Test:** `test_user_blocking_adversarial.py::test_whitespace_manipulation()`

**Description:**
System accepts usernames with leading/trailing whitespace, creating duplicate blocks for the same logical user.

**Attack Vector:**
```python
# These create 6 separate blocks:
"User2"
" User2"   # Leading space
"User2 "   # Trailing space
"User2\t"  # Tab character
"User2\n"  # Newline
```

**Impact:**
- Database pollution with duplicate records
- Inconsistent filtering behavior
- User confusion about who is blocked
- Potential DoS via creating thousands of whitespace variations

**Fix Required:**
- Add `.strip()` to ALL username inputs before validation
- Apply consistently across all layers (API, WebSocket, cache)
- Consider database migration to clean existing data

**Files to Modify:**
- `chats/user_block_views.py` - Lines 21, 67 (strip username input)
- `chats/consumers.py` - Normalize before filtering
- `chats/utils/performance/cache.py` - Normalize cache keys

---

### 🔴 HIGH - Race Condition on Block Creation

**Status:** VULNERABLE
**Test:** `test_user_blocking_adversarial.py::test_race_condition()`

**Description:**
Concurrent block operations create duplicate UserBlock records in the database.

**Attack Vector:**
```python
# 10 concurrent requests to block same user
# Result: 5 duplicate records created
# get_or_create() is not atomic under high concurrency
```

**Impact:**
- Database integrity violations
- Inconsistent state between PostgreSQL and Redis
- Potential crashes when querying duplicate blocks
- User sees multiple entries for same blocked user

**Fix Required:**
- Add database-level unique constraint: `unique_together = ['blocker', 'blocked_username']`
- Use `select_for_update()` with transaction isolation
- Handle `IntegrityError` gracefully in views

**Files to Modify:**
- `chats/models.py` - Add unique constraint to UserBlock model
- `chats/migrations/` - Create migration for constraint
- `chats/user_block_views.py` - Wrap in transaction, handle IntegrityError

**Code Example:**
```python
class UserBlock(models.Model):
    blocker = models.ForeignKey(User, on_delete=models.CASCADE)
    blocked_username = models.CharField(max_length=150)

    class Meta:
        unique_together = ['blocker', 'blocked_username']
        indexes = [
            models.Index(fields=['blocker', 'blocked_username']),
        ]
```

---

### 🟡 MEDIUM - Rate Limiting / DoS

**Status:** VULNERABLE
**Test:** `test_user_blocking_adversarial.py::test_rate_limiting_dos()`

**Description:**
No rate limiting on block/unblock endpoints allows unlimited operations.

**Attack Vector:**
```python
# Achieved 27.4 operations/second with no throttling
# Can spam thousands of requests to:
# - Overload PostgreSQL
# - Flood Redis cache
# - Spam WebSocket broadcasts
```

**Impact:**
- Service degradation for all users
- Database overload
- Redis memory exhaustion
- WebSocket connection saturation

**Fix Required:**
- Install `django-ratelimit` package
- Apply rate limiting decorators to block/unblock views
- Set reasonable limits (e.g., 10 blocks per minute per user)

**Files to Modify:**
- `requirements.txt` - Add django-ratelimit
- `chats/user_block_views.py` - Add @ratelimit decorators
- `chatpop/settings.py` - Configure rate limit backend

**Code Example:**
```python
from django_ratelimit.decorators import ratelimit

class UserBlockView(APIView):
    @ratelimit(key='user', rate='10/m', method='POST')
    def post(self, request):
        # ... existing code
```

---

### 🟡 LOW - Empty Username Validation

**Status:** VULNERABLE
**Test:** `test_user_blocking_adversarial.py::test_empty_username_validation()`

**Description:**
System accepts whitespace-only strings as valid usernames to block.

**Attack Vector:**
```python
# Block username: " " (single space)
# System accepts it after stripping becomes ""
```

**Impact:**
- User blocks "nothing" and gets confused
- Database pollution with meaningless records
- Edge case that breaks UI assumptions

**Fix Required:**
- After stripping, validate username is not empty
- Reject whitespace-only usernames with clear error message

**Files to Modify:**
- `chats/user_block_views.py` - Add validation after strip

**Code Example:**
```python
blocked_username = request.data.get('username', '').strip()

if not blocked_username:
    raise ValidationError({"username": ["Username cannot be empty"]})
```

---

## ✅ Secure Areas (Verified)

These attack vectors have been tested and confirmed secure:

### SQL Injection
- **Test:** `test_user_blocking_adversarial.py::test_sql_injection()`
- **Status:** SECURE
- **Why:** Django ORM properly parameterizes all queries

### Token Manipulation
- **Test:** `test_user_blocking_adversarial.py::test_token_manipulation()`
- **Status:** SECURE
- **Why:** DRF Token authentication validates tokens against database

### Cross-User Data Leakage
- **Test:** `test_user_blocking_adversarial.py::test_cross_user_data_leakage()`
- **Status:** SECURE
- **Why:** Queries filtered by `request.user`

### Authorization Bypass
- **Test:** `test_user_blocking_adversarial.py::test_authorization_bypass()`
- **Status:** SECURE
- **Why:** Permission checks enforce user can only modify their own blocks

### Username Enumeration
- **Test:** `test_user_blocking_adversarial.py::test_username_enumeration()`
- **Status:** SECURE
- **Why:** System allows blocking non-existent users (no 404 for missing usernames)

### Case Sensitivity
- **Test:** `test_user_blocking_adversarial.py::test_case_sensitivity_bypass()`
- **Status:** SECURE (requires manual WebSocket verification)
- **Why:** Database comparison uses case-insensitive matching

---

## Remediation Priority

**Priority Order:**
1. 🔴 **Unicode Homoglyph Attack** - Complete bypass of blocking
2. 🔴 **Race Condition** - Data integrity issue
3. 🔴 **Whitespace Manipulation** - Database pollution + bypass potential
4. 🟡 **Rate Limiting** - DoS prevention
5. 🟡 **Empty Username Validation** - Edge case handling

**Estimated Effort:**
- Unicode normalization: 2-3 hours (research + implementation + testing)
- Race condition fix: 1 hour (migration + error handling)
- Whitespace normalization: 30 minutes (add .strip() everywhere)
- Rate limiting: 1 hour (install + configure + test)
- Empty validation: 15 minutes (one-line fix)

**Total:** ~5-6 hours to fix all vulnerabilities

---

## Testing Workflow

### Before Pushing Code

```bash
# 1. Run adversarial tests to check for regressions
python3 test_user_blocking_adversarial.py

# 2. Run basic functionality tests
python3 test_user_blocking.py

# 3. Run Django unit tests
./venv/bin/python manage.py test chats

# 4. Manual testing
# - Test blocking in browser
# - Verify WebSocket filtering works
# - Check Redis cache consistency
```

### After Fixing a Vulnerability

```bash
# 1. Run the specific test that was failing
python3 test_user_blocking_adversarial.py

# 2. Look for the test that was marked VULNERABLE
# Expected: Test should now show ✅ SECURE

# 3. Update this document:
# - Move vulnerability from "Known Vulnerabilities" to "Fixed Vulnerabilities"
# - Add date fixed and PR/commit reference

# 4. Run full test suite to ensure no regressions
./venv/bin/python manage.py test
```

---

## Fixed Vulnerabilities

### 🟢 AttributeError - request.user.username (Fixed 2025-01-12)

**Description:** Views tried to access `request.user.username` which doesn't exist on User model.

**Fix:** Changed to `request.user.reserved_username`

**Files Modified:**
- `chats/user_block_views.py` - Line 27

**Commit:** TBD

---

## Future Security Considerations

### Not Yet Tested

- **CSRF Protection:** Verify CSRF tokens required for all state-changing operations
- **XSS in Usernames:** Test if malicious JavaScript in usernames gets escaped
- **Clickjacking:** Ensure X-Frame-Options header is set
- **Mass Assignment:** Verify users can't set arbitrary fields via API
- **Time-based Attacks:** Check if block/unblock timing leaks information
- **WebSocket Authentication:** Verify WebSocket connections properly authenticated
- **Redis Cache Poisoning:** Test if attacker can corrupt cache with malformed data

### Potential Future Attacks

- **Block List Size Limit:** What happens if user blocks 100,000 usernames?
- **Unicode Width Attacks:** Can attacker use zero-width characters?
- **Regex DoS:** If we add pattern-based blocking, watch for ReDoS
- **Memory Exhaustion:** Large block lists held in WebSocket memory

---

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Unicode Security Guide](https://unicode.org/reports/tr39/)
- [Django Security Best Practices](https://docs.djangoproject.com/en/stable/topics/security/)
- [DRF Security](https://www.django-rest-framework.org/topics/security/)

---

## Document Version History

| Date | Author | Changes |
|------|--------|---------|
| 2025-01-12 | Claude | Initial document created with 5 known vulnerabilities |

---

**Last Updated:** 2025-01-12
**Next Review:** After vulnerability fixes are implemented
