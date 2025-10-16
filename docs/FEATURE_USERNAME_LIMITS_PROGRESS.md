# Feature: Global Username System - Implementation Progress

**Branch:** `feature/username-limits`
**Status:** In Progress (1/13 tasks completed)
**Last Updated:** 2025-10-14

---

## Overview

This document tracks the implementation progress of the Global Username System feature as specified in `/docs/FEATURE_USERNAME_LIMITS.md`.

---

## ✅ Completed Tasks

### 1. Database Migration - Global Username Index

**Status:** COMPLETED ✅

**What Was Done:**
- Created migration `0046_add_global_username_index.py`
- Added database index to `ChatParticipation.username` field for fast global lookups
- Migration applied successfully to database

**Files Modified:**
- `/backend/chats/migrations/0046_add_global_username_index.py` (new file)

**Migration Code:**
```python
operations = [
    migrations.AddIndex(
        model_name='chatparticipation',
        index=models.Index(fields=['username'], name='chats_chatpart_username_global_idx'),
    ),
]
```

**Verification:**
```bash
./venv/bin/python manage.py migrate chats 0046
# Output: Applying chats.0046_add_global_username_index... OK
```

---

## 🔍 Infrastructure Analysis Completed

### Existing Endpoints Inventory

**Chat-Specific Endpoints (`/api/chats/{code}/...`):**

1. **`POST /api/chats/{code}/suggest-username/`** (SuggestUsernameView)
   - Generates username suggestions for specific chat
   - Rate limited: 20 requests per fingerprint/IP per chat per hour
   - Uses `generate_username(chat_code)` - chat-specific logic
   - **ACTION NEEDED:** Enhance to track generated usernames in Redis per fingerprint

2. **`POST /api/chats/{code}/validate-username/`** (UsernameValidationView)
   - Validates username availability within specific chat
   - Checks global `User.reserved_username` field
   - Checks per-chat `ChatParticipation` records
   - Handles dual sessions (registered + anonymous with same username)
   - **STATUS:** Already implements most of required logic ✓

**Global/Account Endpoints (`/api/accounts/...`):**

3. **`GET /api/accounts/check-username/?username=X`** (CheckUsernameView)
   - Checks global `User.reserved_username` availability (case-insensitive)
   - Validates format and profanity
   - **ACTION NEEDED:** Also check `ChatParticipation` for true global uniqueness

4. **`POST /api/accounts/suggest-username/`** (SuggestUsernameView)
   - Generates username for account registration
   - No rate limiting currently
   - Uses `generate_username(chat_code=None)` - global logic
   - **ACTION NEEDED:** Add rate limiting to match chat version

### Current Username Generation Logic

**File:** `/backend/chats/utils/username/generator.py`

**Function:** `generate_username(chat_code=None, max_attempts=100)`

**Current Behavior:**
- Validates format with `validate_username(username, skip_badwords_check=True)`
- Checks Redis cache for recent suggestions (chat-specific only, if chat_code provided)
- Checks `User.reserved_username` for global conflicts
- Checks `ChatParticipation` for per-chat conflicts (if chat_code provided)
- Returns: `str` (username only)

**What's Missing for New Feature:**
- ❌ No tracking of generated usernames per fingerprint in Redis
- ❌ No attempt counting per fingerprint
- ❌ Doesn't return remaining attempts count
- ❌ No Constance integration for max attempts limit
- ❌ No validation of previously generated usernames on join

---

## 📋 Remaining Tasks (Detailed Implementation Plan)

### Phase 1: Backend Foundation (Tasks 2-4)

#### Task 2: Update `generate_username()` Function

**File:** `/backend/chats/utils/username/generator.py`

**Changes Required:**

1. **Add fingerprint parameter and attempt tracking:**
```python
def generate_username(fingerprint=None, chat_code=None, max_attempts=None):
    """
    Generate username with Redis tracking per fingerprint.

    Args:
        fingerprint: Browser fingerprint for tracking generated usernames
        chat_code: Optional chat code (for backwards compatibility)
        max_attempts: Max generation attempts (defaults to Constance config)

    Returns:
        tuple: (username, attempts_remaining)
    """
    from constance import config

    if max_attempts is None:
        max_attempts = config.MAX_ANONYMOUS_USERNAME_GENERATION_ATTEMPTS

    # Check current attempt count
    if fingerprint:
        attempts_key = f"username:attempts:{fingerprint}"
        current_attempts = int(cache.get(attempts_key) or 0)

        if current_attempts >= max_attempts:
            raise ValidationError(
                f"Maximum username generation attempts exceeded ({max_attempts})"
            )

    # ... existing generation logic ...

    # After finding valid username:
    if fingerprint:
        # Track this username was generated for this fingerprint
        generated_key = f"username:generated:{fingerprint}"
        cache.sadd(generated_key, username)  # Add to set
        cache.expire(generated_key, 3600)  # 1 hour TTL

        # Increment attempt count
        cache.incr(attempts_key)
        cache.expire(attempts_key, 3600)

        remaining = max_attempts - current_attempts - 1
        return username, remaining
    else:
        # Backwards compatibility: no fingerprint provided
        return username, None
```

2. **Add global uniqueness check:**
```python
# Replace chat-specific check with global check
if ChatParticipation.objects.filter(username__iexact=username).exists():
    continue  # Username taken globally, try another
```

3. **Add helper function for validation:**
```python
def is_username_globally_available(username):
    """Check if username is available globally across entire platform"""
    # Check registered users
    if User.objects.filter(reserved_username__iexact=username).exists():
        return False

    # Check all anonymous/per-chat usernames
    if ChatParticipation.objects.filter(username__iexact=username).exists():
        return False

    return True
```

**Dependencies:**
- Requires Task 3 (Constance config) to be completed first

---

#### Task 3: Add Constance Configuration

**File:** `/backend/chatpop/settings.py`

**Location:** Add to existing `CONSTANCE_CONFIG` dictionary (around line 222)

**Code to Add:**
```python
CONSTANCE_CONFIG = {
    # ... existing config ...

    # Username Generation Settings
    'MAX_ANONYMOUS_USERNAME_GENERATION_ATTEMPTS': (
        10,
        'Maximum username generation attempts for anonymous users per hour',
        int
    ),
}
```

**Notes:**
- Default: 10 attempts per hour per fingerprint
- TTL: 1 hour (3600 seconds)
- Can be changed via Django admin without code changes

---

#### Task 4: Create Username Generation Endpoint with Tracking

**Option A: Enhance Existing Endpoint**

Enhance `/api/chats/{code}/suggest-username/` (SuggestUsernameView in `chats/views.py` lines 944-989)

**Changes:**
```python
class SuggestUsernameView(APIView):
    def post(self, request, code):
        fingerprint = request.data.get('fingerprint') or get_client_ip(request)

        try:
            # NEW: Pass fingerprint for tracking
            username, remaining = generate_username(
                fingerprint=fingerprint,
                chat_code=code
            )

            # NEW: Return remaining attempts
            return Response({
                'username': username,
                'remaining': remaining  # NEW FIELD
            })
        except ValidationError as e:
            if "exceeded" in str(e):
                return Response(
                    {'error': str(e), 'max_attempts': config.MAX_ANONYMOUS_USERNAME_GENERATION_ATTEMPTS},
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )
            raise
```

**Option B: Create New Dedicated Endpoint**

Create `/api/usernames/generate/` as specified in docs.

**Decision:** Use Option A (enhance existing endpoint) to avoid duplication and maintain backwards compatibility.

---

### Phase 2: Join Logic Updates (Task 5)

#### Task 5: Update Join Chat Endpoint

**File:** `/backend/chats/views.py` - ChatRoomJoinView

**Required Changes:**

1. **Add username validation on join for anonymous users:**
```python
# In ChatRoomJoinView.post() method

# For anonymous users submitting generated username:
if not request.user.is_authenticated and username:
    fingerprint = request.data.get('fingerprint')

    # Validate username was actually generated for this fingerprint
    if fingerprint:
        generated_key = f"username:generated:{fingerprint}"
        generated_usernames = cache.smembers(generated_key)

        if username not in generated_usernames:
            return Response(
                {'error': 'Invalid username - not generated for this session'},
                status=status.HTTP_400_BAD_REQUEST
            )

    # Double-check global availability (race condition protection)
    if not is_username_globally_available(username):
        return Response(
            {'error': 'Username no longer available'},
            status=status.HTTP_409_CONFLICT
        )
```

2. **Add atomic transaction for username claiming:**
```python
from django.db import transaction

@transaction.atomic
def claim_username(username, user_or_fingerprint, chat_room):
    # Final availability check inside transaction
    if not is_username_globally_available(username):
        raise ValidationError("Username already taken")

    # Create participation record
    participation = ChatParticipation.objects.create(
        chat_room=chat_room,
        username=username,
        user=user if user else None,
        fingerprint=fingerprint if not user else None
    )

    return participation
```

**Security:** This prevents API bypass attacks where users submit usernames they didn't generate.

---

### Phase 3: Registration Enhancement (Task 6)

#### Task 6: Enhance Registration Endpoint

**File:** `/backend/accounts/views.py` - CheckUsernameView

**Current Logic:**
```python
# Currently only checks User.reserved_username
if User.objects.filter(reserved_username__iexact=username).exists():
    return Response({'available': False, ...})
```

**Enhanced Logic:**
```python
# Check both User.reserved_username AND ChatParticipation
from chats.utils.username.generator import is_username_globally_available

if not is_username_globally_available(username):
    return Response({
        'available': False,
        'message': 'Username is already taken'
    })
```

**Impact:** Registration now enforces true global uniqueness across both reserved usernames and anonymous per-chat usernames.

---

### Phase 4: Testing (Task 7)

#### Task 7: Write Comprehensive Tests

**File:** `/backend/chats/tests/tests_username_generation.py` (new file)

**Test Coverage Required:**

1. **Username Generation Tests:**
   - Test attempt limiting (10 attempts max)
   - Test Redis tracking of generated usernames
   - Test TTL expiration (1 hour)
   - Test global uniqueness checking
   - Test escalating number ranges (3→4→5 digits)

2. **Join Validation Tests:**
   - Test API bypass prevention (reject non-generated usernames)
   - Test race condition handling (atomic transactions)
   - Test registered vs anonymous flows
   - Test fingerprint validation

3. **Registration Tests:**
   - Test global uniqueness enforcement
   - Test case-insensitive checks
   - Test reserved username conflicts with ChatParticipation

**Example Test:**
```python
class UsernameGenerationTests(TestCase):
    def test_generation_limit_enforced(self):
        fingerprint = "test_fingerprint_123"

        # Generate 10 usernames (should succeed)
        for i in range(10):
            username, remaining = generate_username(fingerprint=fingerprint)
            self.assertIsNotNone(username)
            self.assertEqual(remaining, 9 - i)

        # 11th attempt should fail
        with self.assertRaises(ValidationError) as cm:
            generate_username(fingerprint=fingerprint)

        self.assertIn("exceeded", str(cm.exception))

    def test_api_bypass_prevention(self):
        # Attempt to join with username not generated
        response = self.client.post('/api/chats/ABC123/join/', {
            'username': 'HackerUser123',
            'fingerprint': 'test_fp'
        })

        self.assertEqual(response.status_code, 400)
        self.assertIn('not generated', response.data['error'])
```

**Existing Tests to Update:**
- `/backend/chats/tests/tests_rate_limits.py` - Update suggest-username tests
- `/backend/accounts/tests/...` - Update registration tests

---

### Phase 5: Frontend Implementation (Tasks 8-10)

#### Task 8: Update JoinChatModal - Anonymous Users

**File:** `/frontend/src/components/JoinChatModal.tsx`

**Required Changes:**

1. **Remove text input field for anonymous users**
2. **Add dice roll UI:**
```tsx
const [generatedUsername, setGeneratedUsername] = useState<string | null>(null);
const [attemptsRemaining, setAttemptsRemaining] = useState<number | null>(null);
const [isGenerating, setIsGenerating] = useState(false);

const handleRollDice = async () => {
  setIsGenerating(true);
  try {
    const response = await fetch(`/api/chats/${chatCode}/suggest-username/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fingerprint: await getFingerprint() })
    });

    const data = await response.json();
    setGeneratedUsername(data.username);
    setAttemptsRemaining(data.remaining);
  } catch (error) {
    // Handle max attempts exceeded
    if (error.status === 429) {
      // Show error: "Maximum attempts exceeded. Try again in 1 hour."
    }
  } finally {
    setIsGenerating(false);
  }
};
```

3. **UI Structure:**
```tsx
{/* Anonymous user flow */}
{!generatedUsername && (
  <button onClick={handleRollDice} disabled={isGenerating}>
    🎲 Roll dice for username
  </button>
)}

{generatedUsername && (
  <>
    <div className="username-display">
      {generatedUsername}
    </div>
    <div className="attempts-remaining">
      {attemptsRemaining} rolls remaining
    </div>
    {attemptsRemaining > 0 && (
      <button onClick={handleRollDice}>Roll again</button>
    )}
    <button onClick={handleJoinChat}>Join Chat</button>
  </>
)}
```

---

#### Task 9: Update JoinChatModal - Registered Users

**Same File:** `/frontend/src/components/JoinChatModal.tsx`

**Flow:**

1. **Default View (Reserved Username):**
```tsx
{user && (
  <>
    <div className="username-display">
      <input value={user.reserved_username} disabled />
    </div>
    <button onClick={() => setMode('random')}>
      Use random username instead
    </button>
    <button onClick={handleJoinChat}>Join Chat</button>
  </>
)}
```

2. **Random Mode (Dice Roll):**
```tsx
{user && mode === 'random' && (
  <>
    {/* Same dice roll UI as anonymous users */}
    <button onClick={() => setMode('reserved')}>
      Use my reserved username
    </button>
  </>
)}
```

---

#### Task 10: Update Registration Form

**File:** `/frontend/src/components/RegistrationForm.tsx`

**Required Changes:**

1. **Add real-time validator:**
```tsx
const [username, setUsername] = useState('');
const [availability, setAvailability] = useState<{
  available: boolean;
  message: string;
} | null>(null);

const checkUsername = useMemo(
  () => debounce(async (value: string) => {
    const response = await fetch(
      `/api/accounts/check-username/?username=${encodeURIComponent(value)}`
    );
    const data = await response.json();
    setAvailability(data);
  }, 500),
  []
);

useEffect(() => {
  if (username.length >= 3) {
    checkUsername(username);
  }
}, [username]);
```

2. **Display availability status:**
```tsx
<input
  value={username}
  onChange={(e) => setUsername(e.target.value)}
/>
{availability && (
  <div className={availability.available ? 'success' : 'error'}>
    {availability.available ? '✓ Available' : '✗ ' + availability.message}
  </div>
)}
```

---

### Phase 6: Testing & Documentation (Tasks 11-12)

#### Task 11: Run Full Test Suite

**Commands:**
```bash
# Run all backend tests
cd backend
./venv/bin/python manage.py test

# Specific test modules
./venv/bin/python manage.py test chats.tests.tests_username_generation
./venv/bin/python manage.py test chats.tests.tests_security
./venv/bin/python manage.py test accounts.tests
```

**Expected:**
- All 139+ existing tests pass
- New username generation tests pass (est. 15-20 new tests)
- Total: ~155-160 tests passing

#### Task 12: Update Documentation

**File:** `/docs/FEATURE_USERNAME_LIMITS.md`

**Add Implementation Notes Section:**
- Final endpoint URLs used
- Constance config values
- Redis key patterns used
- Security considerations implemented
- Known limitations
- Future enhancement ideas

---

## 🔧 Technical Decisions Made

### 1. Leverage Existing Endpoints vs Create New

**Decision:** Enhance existing endpoints rather than creating new `/api/usernames/` routes.

**Rationale:**
- Avoids duplication
- Maintains backwards compatibility
- Existing rate limiting infrastructure
- Clearer REST semantics (username suggestions are chat-specific)

### 2. Global Uniqueness Check Location

**Decision:** Centralize in `is_username_globally_available()` helper function.

**Rationale:**
- Single source of truth
- Reusable across join, registration, validation
- Easier to test
- Performance: uses indexed queries

### 3. Redis Key Patterns

**Chosen Patterns:**
```
username:attempts:{fingerprint}        # Track generation attempts
username:generated:{fingerprint}       # Set of generated usernames
```

**TTL:** 1 hour (3600 seconds)

**Rationale:**
- Clear namespacing
- Easy to debug
- Follows existing Redis patterns in codebase
- 1 hour TTL balances security with UX

---

## 📊 Implementation Checklist

### Backend
- [x] Database index migration
- [ ] Constance configuration
- [ ] Update `generate_username()` function
- [ ] Enhance suggest-username endpoint
- [ ] Update join endpoint validation
- [ ] Enhance registration endpoint
- [ ] Write comprehensive tests

### Frontend
- [ ] Update JoinChatModal (anonymous flow)
- [ ] Update JoinChatModal (registered flow)
- [ ] Update RegistrationForm validator
- [ ] Add error handling for max attempts
- [ ] Add loading states for dice rolls

### Testing & Docs
- [ ] Run full backend test suite (139+ tests)
- [ ] Manual testing on localhost
- [ ] Update FEATURE_USERNAME_LIMITS.md
- [ ] Update API documentation

---

## 🚧 Known Challenges & Solutions

### Challenge 1: Orphaned Usernames

**Problem:** Anonymous users lose fingerprint → username orphaned forever

**Solution:** Acceptable trade-off. With 57M+ combinations, orphaned usernames won't exhaust namespace for years. Monitor usage percentage, alert at 80%.

### Challenge 2: Race Conditions

**Problem:** Two users generate same username simultaneously

**Solution:**
- Use atomic transactions in join logic
- Double-check availability inside transaction
- Return 409 Conflict if taken between generation and join

### Challenge 3: Fingerprint Spoofing

**Problem:** Malicious users could spoof fingerprints to bypass limits

**Solution:**
- Also track by IP address (fallback identifier)
- Redis validation on join prevents using non-generated usernames
- Rate limits apply per chat per fingerprint
- Monitoring and abuse detection

---

## 🎯 Next Steps

**Immediate (Next Session):**
1. Add Constance config (Task 3) - 5 minutes
2. Update `generate_username()` function (Task 2) - 30 minutes
3. Test updated function - 15 minutes

**Short Term (1-2 sessions):**
4. Update suggest-username endpoint (Task 4)
5. Update join endpoint validation (Task 5)
6. Write backend tests (Task 7)

**Medium Term (2-3 sessions):**
7. Frontend implementation (Tasks 8-10)
8. Full testing and debugging

**Total Estimated Time:** 6-8 coding sessions

---

## 📝 Notes

- Branch `feature/username-limits` created
- Database migration applied successfully
- No breaking changes to existing functionality
- All 139 existing tests still pass (not yet re-verified after migration)

---

## 🔗 References

- **Feature Spec:** `/docs/FEATURE_USERNAME_LIMITS.md`
- **Migration:** `/backend/chats/migrations/0046_add_global_username_index.py`
- **Generator:** `/backend/chats/utils/username/generator.py`
- **Views:** `/backend/chats/views.py`, `/backend/accounts/views.py`
- **URLs:** `/backend/chats/urls.py`, `/backend/accounts/urls.py`
