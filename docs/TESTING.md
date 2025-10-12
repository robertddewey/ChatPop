# Testing Documentation

**Total Test Count:** 139 tests across 7 test suites

This document provides comprehensive documentation of all backend tests, including what each test does and why it's important.

---

## Test Suites Overview

| Test Suite | File | Test Count | Purpose |
|------------|------|------------|---------|
| Security Tests | `chats/tests_security.py` | 26 tests | JWT authentication, username reservations, attack prevention |
| Username Validation | `chats/tests_validators.py` | 10 tests | Username format and character validation |
| Profanity Filtering | `chats/tests_profanity.py` | 26 tests | Profanity detection across all username entry points |
| Rate Limiting | `chats/tests_rate_limits.py` | 12 tests | Username generation rate limiting |
| Dual Sessions | `chats/tests_dual_sessions.py` | 16 tests | Anonymous/logged-in user coexistence |
| Redis Caching | `chats/tests_redis_cache.py` | 49 tests | Message caching, performance benchmarks |

---

## 1. Security Tests (`chats/tests_security.py`)

**File Location:** `backend/chats/tests_security.py`
**Test Count:** 26 tests
**Test Classes:** `ChatSessionSecurityTests` (17 tests), `UsernameReservationSecurityTests` (9 tests)

### 1.1 JWT Session Security Tests (17 tests)

These tests verify the JWT-based session authentication system used for securing chat messages and API endpoints.

#### `test_message_send_requires_session_token`
**What it tests:** Sending messages without a session token is blocked
**How it works:** Attempts to POST to `/api/chats/{code}/messages/send/` without `session_token` field
**Expected result:** 403 Forbidden with error message containing "session token"
**Why it matters:** Prevents anonymous message posting; ensures all users go through join flow to get a valid session token

#### `test_message_send_with_invalid_token`
**What it tests:** Invalid JWT tokens are rejected
**How it works:** Sends message with `session_token: 'invalid.jwt.token'`
**Expected result:** 403 Forbidden
**Why it matters:** Prevents attackers from forging tokens with random strings

#### `test_message_send_with_expired_token`
**What it tests:** Expired tokens are rejected
**How it works:** Creates JWT with `exp` field set to 1 hour in the past, attempts to send message
**Expected result:** 403 Forbidden with error containing "expired"
**Why it matters:** Ensures sessions don't last forever; users must rejoin after 24 hours

#### `test_cannot_use_token_for_different_chat`
**What it tests:** Tokens are chat-specific (can't use token from Chat A in Chat B)
**How it works:** Creates two chat rooms, gets token for Chat A, tries to use it in Chat B
**Expected result:** 403 Forbidden with error "not valid for this chat"
**Why it matters:** Prevents cross-chat attacks where attacker joins Chat A and tries to spam Chat B

#### `test_cannot_use_token_for_different_username`
**What it tests:** Tokens are username-specific
**How it works:** Gets token for username "testuser", tries to send message as "different_user" with same token
**Expected result:** 403 Forbidden with error "username mismatch"
**Why it matters:** Prevents impersonation attacks within the same chat

#### `test_cannot_forge_token_with_wrong_secret`
**What it tests:** Tokens signed with wrong secret key are rejected
**How it works:** Creates JWT payload and signs with `'wrong_secret'` instead of Django `SECRET_KEY`
**Expected result:** 403 Forbidden
**Why it matters:** Core JWT security - only tokens signed with Django's secret are valid

#### `test_cannot_modify_token_payload`
**What it tests:** Modified token payloads are rejected
**How it works:** Decodes valid token, changes username to "hacker", re-encodes with attacker's secret
**Expected result:** 403 Forbidden
**Why it matters:** Prevents attackers from tampering with token contents

#### `test_join_endpoint_issues_valid_token`
**What it tests:** Join endpoint properly issues session tokens
**How it works:** POSTs to `/api/chats/{code}/join/` with username, checks response contains `session_token`
**Expected result:** 200 OK, token can be decoded and contains correct chat_code and username
**Why it matters:** Verifies the token issuance flow works correctly

#### `test_valid_token_allows_message_send`
**What it tests:** Valid tokens allow message sending
**How it works:** Uses token from setUp (valid for current chat/username), sends message
**Expected result:** 201 Created, message appears in database
**Why it matters:** Ensures legitimate users can send messages (positive test case)

#### `test_replay_attack_prevention`
**What it tests:** Token reusability within lifetime (by design)
**How it works:** Sends two different messages with same token
**Expected result:** Both succeed (201 Created)
**Why it matters:** Documents that tokens are reusable until expiry (not single-use). Comment notes this is by design.

#### `test_sql_injection_in_username`
**What it tests:** SQL injection attempts are blocked by validation
**How it works:** Tries to join with username `"'; DROP TABLE chats_message; --"`
**Expected result:** 400 Bad Request (validation error), chat room still exists
**Why it matters:** Defense against SQL injection attacks

#### `test_xss_in_username`
**What it tests:** XSS attempts are blocked by validation
**How it works:** Tries to join with username `"<script>alert('XSS')</script>"`
**Expected result:** 400 Bad Request (validation error)
**Why it matters:** Defense against cross-site scripting attacks

#### `test_token_without_expiration`
**What it tests:** Tokens must have expiration claim
**How it works:** Creates JWT without `exp` field, tries to use it
**Expected result:** 403 Forbidden
**Why it matters:** Ensures all tokens have finite lifetime

#### `test_rate_limiting_not_bypassed_by_multiple_tokens`
**What it tests:** Multiple valid tokens work independently
**How it works:** Creates 5 tokens for different usernames, sends message with each
**Expected result:** All 5 succeed
**Why it matters:** Verifies that having multiple tokens doesn't bypass any rate limits (future-proofing)

#### `test_empty_or_null_token`
**What it tests:** Empty or null tokens are rejected
**How it works:** Tests three cases: `session_token: ''`, `session_token: None`, missing field entirely
**Expected result:** All three return 403 Forbidden
**Why it matters:** Edge case handling for token validation

#### `test_token_with_future_iat`
**What it tests:** Tokens with future issued-at time are rejected
**How it works:** Creates JWT with `iat` (issued-at) 1 hour in the future
**Expected result:** 403 Forbidden
**Why it matters:** Prevents clock-skew attacks where attacker creates tokens with future timestamps

#### `test_private_chat_access_code_protection`
**What it tests:** Private chats require correct access code to get session token
**How it works:** Creates private chat, tries to join without code, with wrong code, then with correct code
**Expected result:** First two fail (403), third succeeds (200) with session_token
**Why it matters:** Core private chat security feature

### 1.2 Username Reservation Security Tests (9 tests)

These tests verify the username reservation system and fingerprinting mechanism for anonymous users.

#### `test_two_anonymous_users_same_username_blocked`
**What it tests:** Two anonymous users can't use the same username in a chat
**How it works:** User with fingerprint1 joins as "Charlie", user with fingerprint2 tries to join as "Charlie"
**Expected result:** First succeeds, second fails (400 Bad Request)
**Why it matters:** Prevents username confusion in anonymous chats

#### `test_anonymous_and_registered_user_coexist_with_same_name`
**What it tests:** Anonymous user and logged-in user with same username can coexist
**How it works:** Anonymous joins as "Bobby", logged-in user (reserved_username="Bobby") also joins as "Bobby"
**Expected result:** Both succeed, create separate participations
**Verification:** Sends messages from both, checks `username_is_reserved` flag (false for anonymous, true for logged-in)
**Why it matters:** Core dual sessions feature - allows smooth upgrade path from anonymous to registered

#### `test_registered_user_blocked_from_using_others_reserved_username`
**What it tests:** Logged-in user A can't join using user B's reserved_username
**How it works:** user1 tries to join with user2's reserved_username "Bobby"
**Expected result:** 400 Bad Request with error containing "reserved"
**Why it matters:** Prevents username theft among registered users

#### `test_anonymous_user_username_persistence_via_fingerprint`
**What it tests:** Anonymous users are locked to their username via fingerprint
**How it works:** User with fingerprint1 joins as "Charlie", tries to rejoin with different username but same fingerprint
**Expected result:** Second attempt fails (400 Bad Request) with error "already joined"
**Why it matters:** Prevents anonymous users from changing usernames mid-chat (would cause confusion)

#### `test_registered_user_username_persistence`
**What it tests:** Registered users are locked to their chosen username in a chat
**How it works:** user1 joins as "SuperAlice", tries to rejoin as "Alice" (their reserved_username), then as "MegaAlice"
**Expected result:** All rejoin attempts fail with "already joined" error
**Why it matters:** Consistent identity - once you join with a username, you can't change it in that chat

#### `test_reserved_username_case_insensitive_uniqueness`
**What it tests:** Reserved usernames are unique case-insensitively but case is preserved
**How it works:** User1 has reserved_username='Alice', tries to register 'alice' and 'ALICE'
**Expected result:** Both registrations fail with "already reserved" error, original 'Alice' case preserved
**Why it matters:** Prevents username squatting with case variations

#### `test_chat_username_case_insensitive_uniqueness`
**What it tests:** Chat usernames are unique case-insensitively but case is preserved
**How it works:** User joins as "Charlie", others try to join as "charlie" and "CHARLIE"
**Expected result:** Only first succeeds, others fail with "already in use", original case 'Charlie' preserved
**Why it matters:** Prevents username confusion while respecting user's choice of capitalization

#### `test_reserved_username_case_preservation_in_messages`
**What it tests:** Reserved username case is preserved when displayed in messages
**How it works:** User with reserved_username='Alice' joins and sends message, checks message response
**Expected result:** Message contains `user.reserved_username` with value 'Alice' (capital A preserved)
**Why it matters:** Ensures username display consistency

#### `test_anonymous_username_case_preservation_in_messages`
**What it tests:** Anonymous username case is preserved in messages
**How it works:** Anonymous user joins as "DaVinci" (mixed case), sends message, checks participation record
**Expected result:** ChatParticipation.username = 'DaVinci' (exact case preserved)
**Why it matters:** Respects user's capitalization choice for anonymous usernames

---

## 2. Username Validation Tests (`chats/tests_validators.py`)

**File Location:** `backend/chats/tests_validators.py`
**Test Count:** 10 tests
**Test Class:** `UsernameValidatorTestCase`

These tests verify the `validate_username()` function from `chats/validators.py`, which is used for both reserved usernames (registration) and chat usernames (anonymous users).

#### `test_valid_usernames`
**What it tests:** Valid usernames pass validation
**How it works:** Tests 13 valid username patterns:
- Different cases: 'alice', 'Alice', 'ALICE'
- Alphanumeric: 'alice123', 'alice_123'
- Underscores: 'user_name', '_user_', 'test_user_1'
- Numeric only: '12345'
- Edge lengths: 'abcde' (5 chars minimum), 'abcdefghijklmno' (15 chars maximum)
**Expected result:** All return the username unchanged
**Why it matters:** Documents valid username format for users and developers

#### `test_minimum_length_validation`
**What it tests:** Usernames shorter than 5 characters are rejected
**How it works:** Tests empty string, 1-4 character usernames
**Expected result:** ValidationError with message "at least 5 characters" or "cannot be empty"
**Why it matters:** Prevents very short usernames that are hard to distinguish

#### `test_maximum_length_validation`
**What it tests:** Usernames longer than 15 characters are rejected
**How it works:** Tests 16-character username, 20-character username, very long username
**Expected result:** ValidationError with message "at most 15 characters"
**Why it matters:** Keeps usernames readable in chat UI

#### `test_invalid_characters`
**What it tests:** Usernames with invalid characters are rejected
**How it works:** Tests 30+ special characters and combinations:
- Space, hyphen, period, @, !, #, $, %, &, *, +, =, /, \, |
- Brackets, braces, parentheses, angle brackets
- Comma, semicolon, colon, quotes, backtick, tilde, question mark
- Newline, tab
**Expected result:** All fail with "letters, numbers, and underscores" error
**Why it matters:** Prevents injection attacks and display issues

#### `test_whitespace_handling`
**What it tests:** Leading/trailing whitespace is stripped before validation
**How it works:** Tests `'  valid_user  '` (spaces around valid username)
**Expected result:** Returns `'valid_user'` (spaces removed)
**Also tests:** Space in middle (`'user name'`) should fail
**Why it matters:** Forgiving UX for accidental spaces, while preventing spaces mid-username

#### `test_empty_and_none_values`
**What it tests:** Empty strings, None, and whitespace-only strings are rejected
**How it works:** Tests `''`, `None`, `'   '` (whitespace only)
**Expected result:** All fail with "cannot be empty" or "at least 5 characters"
**Why it matters:** Edge case handling

#### `test_case_preservation`
**What it tests:** Original case is preserved
**How it works:** Validates `'AlIcE_123'` (mixed case)
**Expected result:** Returns `'AlIcE_123'` unchanged
**Why it matters:** Respects user's capitalization choice

#### `test_unicode_rejection`
**What it tests:** Unicode/emoji characters are rejected
**How it works:** Tests 6 unicode patterns:
- Emoji: 'alice😀'
- Accented Latin: 'josé_name', 'müller_abc'
- Cyrillic: 'алиса_name'
- Chinese: '用户用户用户用'
- Japanese: 'ユーザーユーザー'
**Expected result:** All fail with "letters, numbers, and underscores" or length error
**Why it matters:** ASCII-only requirement prevents encoding issues

#### `test_underscore_positions`
**What it tests:** Underscores can appear anywhere in username
**How it works:** Tests underscores at start, end, both, middle, consecutive
**Expected result:** All valid ('_alice', 'alice_', '_alice_', 'alice_bob_c', '___alice___')
**Why it matters:** Documents that underscores have no position restrictions

#### `test_numeric_only_usernames`
**What it tests:** Purely numeric usernames are allowed
**How it works:** Tests '12345', '999999999999999' (15 digits)
**Expected result:** Both valid
**Why it matters:** No requirement for alphabetic characters

---

## 3. Profanity Filtering Tests (`chats/tests_profanity.py`)

**File Location:** `backend/chats/tests_profanity.py`
**Test Count:** 26 tests
**Test Classes:** 5 classes covering profanity detection across all username entry points

### 3.1 Profanity Checker Module Tests (5 tests)

**Test Class:** `UsernameProfanityCheckTests`

#### `test_clean_usernames_allowed`
**What it tests:** Clean usernames pass profanity check
**How it works:** Tests 5 clean usernames: "Alice_Smith", "Bob12345", "Charlie99", "DavidJones", "Emma_Watson"
**Expected result:** All return `ValidationResult(allowed=True, reason=None)`
**Why it matters:** Positive test case for profanity checker

#### `test_obvious_profanity_blocked`
**What it tests:** Obvious profanity is detected and blocked
**How it works:** Tests 3 profane usernames (contains common swear words)
**Expected result:** All return `ValidationResult(allowed=False, reason="...")` with explanation
**Why it matters:** Core profanity detection functionality

#### `test_leet_speak_variants_blocked`
**What it tests:** Leet speak variants of profanity are detected
**How it works:** Tests obfuscation patterns: case variation, separators, extra separators
**Expected result:** All blocked
**Why it matters:** Prevents bypassing profanity filter with "clever" spelling

#### `test_legitimate_words_with_banned_substrings_allowed`
**What it tests:** Legitimate words containing banned substrings are allowed
**How it works:** Tests "password123" (contains 'ass'), "assistant99", "compass_user", "titan_gamer" (contains 'tit')
**Expected result:** All allowed
**Why it matters:** Reduces false positives from substring matching

#### `test_check_result_structure`
**What it tests:** ValidationResult has correct structure
**How it works:** Tests clean and blocked usernames, verifies structure
**Expected result:** Allowed has `(allowed=True, reason=None)`, blocked has `(allowed=False, reason=<string>)`
**Why it matters:** API contract verification

### 3.2 Validator Integration Tests (4 tests)

**Test Class:** `ValidatorProfanityIntegrationTests`

#### `test_clean_username_passes_validation`
**What it tests:** Clean usernames pass `validate_username()` with profanity check enabled
**How it works:** Calls `validate_username(username, skip_badwords_check=False)` with clean usernames
**Expected result:** Returns username unchanged
**Why it matters:** Integration between validator and profanity checker

#### `test_profane_username_fails_validation`
**What it tests:** Profane usernames fail `validate_username()` with profanity check
**How it works:** Calls validator with profane usernames, profanity check enabled
**Expected result:** ValidationError with "not allowed"
**Why it matters:** Profanity filter is enforced in validation layer

#### `test_skip_badwords_check_bypasses_profanity_filter`
**What it tests:** `skip_badwords_check=True` bypasses profanity filtering
**How it works:** Calls validator with profane username BUT `skip_badwords_check=True`
**Expected result:** Should NOT fail on profanity (only format validation applies)
**Why it matters:** Allows system-generated usernames to skip profanity check

#### `test_legitimate_words_pass_validation`
**What it tests:** Legitimate words with substrings pass validation
**How it works:** Tests "password123", "assistant99", "compass_user" through full validator
**Expected result:** All pass
**Why it matters:** End-to-end verification of false positive handling

### 3.3 Chat Join API Tests (4 tests)

**Test Class:** `ChatJoinProfanityTests`

#### `test_join_with_clean_username`
**What it tests:** Joining chat with clean username succeeds
**How it works:** POST to `/api/chats/{code}/join/` with clean username
**Expected result:** 200 OK
**Why it matters:** Positive test for join flow

#### `test_join_with_profane_username_rejected`
**What it tests:** Joining with profane username is rejected
**How it works:** POST to join endpoint with profane username
**Expected result:** 400 Bad Request with 'username' in error response
**Why it matters:** Profanity filter enforced at chat entry point

#### `test_join_with_leet_speak_profanity_rejected`
**What it tests:** Leet speak profanity rejected at join
**How it works:** POST with 'f_u_c_k_99' (obfuscated profanity)
**Expected result:** 400 Bad Request
**Why it matters:** Can't bypass filter with separators

#### `test_join_with_legitimate_word_containing_substring`
**What it tests:** Legitimate words allowed at join
**How it works:** POST with "password123"
**Expected result:** 200 OK
**Why it matters:** False positive handling at join endpoint

### 3.4 Check Username Endpoint Tests (4 tests)

**Test Class:** `CheckUsernameProfanityTests`

Tests real-time username validation during registration modal (GET `/api/auth/check-username/?username=X`).

#### `test_check_clean_username`
**What it tests:** Clean username check returns available
**How it works:** GET with `?username=GoodUser123`
**Expected result:** 200 OK, JSON: `{available: true, message: "Username is available"}`
**Why it matters:** Real-time feedback during registration

#### `test_check_profane_username_rejected`
**What it tests:** Profane username check returns error
**How it works:** GET with profane username
**Expected result:** 400 Bad Request, JSON: `{available: false, message: "... not allowed..."}`
**Why it matters:** Prevents profane reserved usernames

#### `test_check_leet_speak_profanity_rejected`
**What it tests:** Leet speak rejected during check
**How it works:** GET with obfuscated profanity
**Expected result:** 400 Bad Request
**Why it matters:** Can't bypass during registration

#### `test_check_legitimate_word_with_substring`
**What it tests:** Legitimate words pass check
**How it works:** GET with "password123"
**Expected result:** 200 OK, available
**Why it matters:** False positive handling during registration

### 3.5 Username Validation Endpoint Tests (4 tests)

**Test Class:** `UsernameValidationProfanityTests`

Tests real-time validation in Join ChatPop modal (POST `/api/chats/{code}/validate-username/`).

#### `test_validate_clean_username`
**What it tests:** Clean username validation succeeds
**How it works:** POST with clean username + fingerprint
**Expected result:** 200 OK, `{available: true}`
**Why it matters:** Real-time feedback before joining chat

#### `test_validate_profane_username_rejected`
**What it tests:** Profane username validation fails
**How it works:** POST with profane username
**Expected result:** 400 Bad Request, `{available: false, error: "..."}`
**Why it matters:** Prevents profane chat usernames before join

#### `test_validate_leet_speak_profanity_rejected`
**What it tests:** Leet speak rejected during validation
**How it works:** POST with obfuscated profanity
**Expected result:** 400 Bad Request
**Why it matters:** Can't bypass in Join modal

#### `test_validate_legitimate_word_with_substring`
**What it tests:** Legitimate words pass validation
**How it works:** POST with "password123"
**Expected result:** 200 OK, available
**Why it matters:** False positive handling in Join modal

### 3.6 User Registration Tests (3 tests)

**Test Class:** `UserRegistrationProfanityTests`

#### `test_register_with_clean_reserved_username`
**What it tests:** Registration with clean reserved_username succeeds
**How it works:** POST to `/api/auth/register/` with clean reserved_username
**Expected result:** 201 Created
**Why it matters:** Positive test for registration flow

#### `test_register_with_profane_reserved_username_rejected`
**What it tests:** Profane reserved_username rejected during registration
**How it works:** POST with profane reserved_username
**Expected result:** 400 Bad Request with error in `reserved_username` field
**Why it matters:** Prevents profane account-level usernames

#### `test_register_without_reserved_username`
**What it tests:** Registration works without reserved_username (optional field)
**How it works:** POST with only email + password
**Expected result:** 201 Created
**Why it matters:** reserved_username is optional

### 3.7 Suggested Username Tests (2 tests)

**Test Class:** `SuggestUsernameProfanityTests`

#### `test_suggested_usernames_are_clean`
**What it tests:** Auto-generated usernames never contain profanity
**How it works:** Calls `/api/chats/{code}/suggest-username/` 10 times, runs each result through `is_username_allowed()`
**Expected result:** All 10 suggestions pass profanity check
**Why it matters:** System never suggests inappropriate usernames

#### `test_suggested_username_endpoint_success`
**What it tests:** Suggest endpoint returns valid username
**How it works:** POST to suggest-username endpoint
**Expected result:** 200 OK, response contains `{username: "..."}` (non-empty string)
**Why it matters:** Endpoint works correctly

---

## 4. Rate Limiting Tests (`chats/tests_rate_limits.py`)

**File Location:** `backend/chats/tests_rate_limits.py`
**Test Count:** 12 tests
**Test Class:** `UsernameGenerationRateLimitTests`

These tests verify rate limiting for the username suggestion endpoint (`/api/chats/{code}/suggest-username/`).

**Rate Limit:** 20 suggestions per hour per fingerprint per chat

#### `test_username_suggestion_allows_up_to_20_requests`
**What it tests:** Up to 20 requests are allowed within rate limit
**How it works:** Makes 20 POST requests with same fingerprint, checks `remaining` field in response
**Expected result:** All 20 return 200 OK, `remaining` counts down from 19 to 0
**Why it matters:** Verifies limit enforcement and counter accuracy

#### `test_username_suggestion_blocks_21st_request`
**What it tests:** 21st request is rate limited
**How it works:** Makes 20 successful requests, then attempts 21st
**Expected result:** 21st returns 429 Too Many Requests, `{error: "limit reached", remaining: 0}`
**Why it matters:** Hard limit enforcement

#### `test_rate_limit_is_per_fingerprint`
**What it tests:** Rate limits are isolated per fingerprint
**How it works:** Uses up 20 requests for fingerprint1, tries fingerprint1 again (blocked), tries fingerprint2 (succeeds)
**Expected result:** fingerprint1 gets 429, fingerprint2 gets 200
**Why it matters:** Different users have separate limits

#### `test_rate_limit_is_per_chat`
**What it tests:** Rate limits are isolated per chat room
**How it works:** Uses up 20 requests in chat1, tries chat1 again (blocked), tries chat2 with same fingerprint (succeeds)
**Expected result:** chat1 gets 429, chat2 gets 200
**Why it matters:** User can get suggestions in multiple chats

#### `test_rate_limit_fallback_to_ip_when_no_fingerprint`
**What it tests:** IP-based rate limiting when fingerprint is missing
**How it works:** Makes 20 requests without fingerprint field (uses IP), 21st is blocked
**Expected result:** 20 succeed, 21st gets 429
**Why it matters:** Fallback mechanism for clients that don't send fingerprint

#### `test_rate_limit_counter_increments_correctly`
**What it tests:** Remaining counter decrements correctly
**How it works:** Makes requests and checks `remaining` field: 1st request = 19 remaining, 5th = 15 remaining, 20th = 0 remaining
**Expected result:** Counter matches expected values
**Why it matters:** Accurate feedback to frontend

#### `test_rate_limit_error_message_format`
**What it tests:** Rate limit error has correct structure
**How it works:** Exhausts limit, checks error response structure
**Expected result:** `{error: <string>, remaining: <int>}`, error mentions "20" and "hour"
**Why it matters:** Clear error messages for users

#### `test_rate_limit_only_increments_on_successful_generation`
**What it tests:** Counter only increments on successful username generation
**How it works:** Makes 5 successful requests, verifies count is exactly 5
**Expected result:** Count matches number of successful responses
**Why it matters:** Errors don't count against limit

#### `test_rate_limit_applies_to_nonexistent_chat`
**What it tests:** Non-existent chat code returns 404, not rate limit error
**How it works:** Requests suggestion for `INVALID_CODE`
**Expected result:** 404 Not Found (not 429)
**Why it matters:** Proper error precedence

#### `test_different_fingerprints_independent_limits`
**What it tests:** Different fingerprints have completely independent limits
**How it works:** Uses 10 from fp1, 5 from fp2, 15 from fp3, checks remaining counts
**Expected result:** fp1=9 remaining, fp2=14 remaining, fp3=4 remaining
**Why it matters:** No cross-contamination between users

#### `test_rate_limit_cache_key_format`
**What it tests:** Correct cache key format is used
**How it works:** Makes request, checks Redis cache key `username_suggest_limit:{chat_code}:{fingerprint}`
**Expected result:** Key exists with value = request count
**Why it matters:** Implementation verification

#### `test_rate_limit_edge_case_exactly_20_requests`
**What it tests:** Exactly 20 requests (boundary condition)
**How it works:** Makes 19 requests, then 20th (should succeed with `remaining: 0`), then 21st (should fail)
**Expected result:** 20th returns 200 + `remaining: 0`, 21st returns 429
**Why it matters:** Off-by-one edge case

---

## 5. Dual Sessions Tests (`chats/tests_dual_sessions.py`)

**File Location:** `backend/chats/tests_dual_sessions.py`
**Test Count:** 16 tests
**Test Classes:** `DualSessionsTests` (6 tests), `ReservedUsernameBadgeTests` (4 tests), `IPRateLimitingTests` (6 tests)

### 5.1 Dual Sessions Architecture Tests (6 tests)

**Test Class:** `DualSessionsTests`

#### `test_anonymous_join_creates_anonymous_participation`
**What it tests:** Anonymous user creates participation with `user=null`, stores fingerprint
**How it works:** POST to join with `username + fingerprint`, no authentication
**Expected result:** ChatParticipation created with `fingerprint="anon-fingerprint-123"`, `user__isnull=True`
**Why it matters:** Core anonymous user flow

#### `test_logged_in_join_creates_user_participation`
**What it tests:** Logged-in user creates participation with `user=<User>`
**How it works:** Authenticate user, POST to join
**Expected result:** ChatParticipation created with `user=<User object>`
**Why it matters:** Core logged-in user flow

#### `test_dual_sessions_allow_same_username`
**What it tests:** Anonymous "robert" and logged-in "Robert" can coexist
**How it works:** Anonymous joins as "robert", logged-in user joins as "Robert" (same username, case-insensitive)
**Expected result:** Both succeed, creates two separate ChatParticipation records
**Why it matters:** Key dual sessions feature - allows upgrade path from anonymous to registered

#### `test_my_participation_prioritizes_logged_in_user`
**What it tests:** MyParticipationView returns logged-in participation when both exist
**How it works:** Creates both anonymous and user participations for same fingerprint, authenticates as user, calls `/my-participation/`
**Expected result:** Returns user participation (username="Robert"), not anonymous (username="robert")
**Why it matters:** Logged-in identity takes precedence

#### `test_my_participation_returns_anonymous_when_not_logged_in`
**What it tests:** MyParticipationView returns anonymous participation when not authenticated
**How it works:** Creates only anonymous participation, calls `/my-participation/` without auth
**Expected result:** Returns anonymous participation
**Why it matters:** Anonymous users can check their participation

#### `test_my_participation_no_fallback_from_logged_in_to_anonymous`
**What it tests:** Logged-in user doesn't see anonymous participation (no fallback)
**How it works:** Creates ONLY anonymous participation, authenticates as different user, calls `/my-participation/`
**Expected result:** `has_joined: false` (doesn't see anonymous participation)
**Why it matters:** Strict separation between logged-in and anonymous identities

### 5.2 Reserved Username Badge Tests (4 tests)

**Test Class:** `ReservedUsernameBadgeTests`

#### `test_username_is_reserved_when_exact_match`
**What it tests:** Badge shown when participation username exactly matches reserved_username
**How it works:** User with `reserved_username="CoolUser"` joins as "CoolUser"
**Expected result:** `username_is_reserved: true` in MyParticipationView response
**Why it matters:** Exact match badge logic

#### `test_username_is_reserved_when_case_insensitive_match`
**What it tests:** Badge shown when case-insensitive match
**How it works:** User with `reserved_username="CoolUser"` joins as "cooluser" (lowercase)
**Expected result:** `username_is_reserved: true`
**Why it matters:** Case-insensitive badge matching

#### `test_username_is_not_reserved_when_different`
**What it tests:** Badge NOT shown when usernames differ
**How it works:** User with `reserved_username="CoolUser"` joins as "DifferentName"
**Expected result:** `username_is_reserved: false`
**Why it matters:** Badge only for matching username

#### `test_username_is_not_reserved_for_anonymous_users`
**What it tests:** Anonymous users never have badge
**How it works:** Creates anonymous participation, checks MyParticipationView
**Expected result:** `username_is_reserved: false`
**Why it matters:** Badge is logged-in-only feature

### 5.3 IP Rate Limiting Tests (6 tests)

**Test Class:** `IPRateLimitingTests`

**Rate Limit:** 3 anonymous usernames per IP per chat

#### `test_anonymous_user_can_join_within_limit`
**What it tests:** Anonymous users can join up to 3 times from same IP
**How it works:** Makes 3 POST requests with different fingerprints, same IP (`REMOTE_ADDR="192.168.1.100"`)
**Expected result:** All 3 succeed, creates 3 ChatParticipation records
**Why it matters:** Allows legitimate multi-device/browser usage

#### `test_anonymous_user_blocked_at_limit`
**What it tests:** 4th join from same IP is blocked
**How it works:** Creates 3 existing participations, tries to join 4th time
**Expected result:** 400 Bad Request with "Maximum anonymous usernames" error
**Why it matters:** Prevents spam from single IP

#### `test_returning_anonymous_user_not_blocked`
**What it tests:** Returning users (existing fingerprint) can rejoin even if IP is at limit
**How it works:** Creates 3 participations, tries to rejoin with fingerprint-1 (existing)
**Expected result:** Succeeds (200 OK)
**Why it matters:** Allows existing users to reconnect

#### `test_different_ip_not_affected_by_limit`
**What it tests:** IP limit is per-IP (different IPs can each have 3 users)
**How it works:** Creates 3 participations from IP1, joins from IP2
**Expected result:** IP2 join succeeds
**Why it matters:** Independent limits per IP

#### `test_logged_in_user_not_affected_by_ip_limit`
**What it tests:** Logged-in users exempt from IP limit
**How it works:** Creates 3 anonymous participations from IP, logs in user, joins from same IP
**Expected result:** Logged-in join succeeds
**Why it matters:** Registered users not penalized by anonymous user spam

#### `test_ip_limit_per_chat`
**What it tests:** IP limit is per-chat (same IP can join 3 times in each chat)
**How it works:** Creates 3 participations in chat1, joins chat2 from same IP
**Expected result:** chat2 join succeeds
**Why it matters:** Independent limits per chat room

---

## 6. Redis Caching Tests (`chats/tests_redis_cache.py`)

**File Location:** `backend/chats/tests_redis_cache.py`
**Test Count:** 49 tests
**Test Classes:** `RedisMessageCacheTests` (22 tests), `RedisPerformanceTests` (7 tests), `RedisReactionCacheTests` (20 tests)

### 6.1 Redis Message Cache Tests (22 tests)

**Test Class:** `RedisMessageCacheTests`

#### `test_add_message_to_redis`
**What it tests:** Messages are added to Redis cache
**How it works:** Creates message in PostgreSQL, calls `MessageCache.add_message()`, fetches from Redis
**Expected result:** Message appears in Redis with correct content and username
**Why it matters:** Core caching functionality

#### `test_username_is_reserved_flag`
**What it tests:** `username_is_reserved` flag correctly computed and cached
**How it works:** Creates message with username matching reserved_username, checks cached flag is true; creates message with different username, checks flag is false
**Expected result:** Cached messages have correct badge flag
**Why it matters:** Badge status must be cached for frontend display

#### `test_username_is_reserved_case_insensitive`
**What it tests:** Badge check is case-insensitive
**How it works:** User with `reserved_username="TestUser"` sends message as "testuser" (lowercase)
**Expected result:** Cached message has `username_is_reserved: true`
**Why it matters:** Case-insensitive badge matching in cache

#### `test_anonymous_user_no_badge`
**What it tests:** Anonymous users never have `username_is_reserved=true`
**How it works:** Creates message with `user=None`
**Expected result:** Cached message has `username_is_reserved: false`, `user_id: null`
**Why it matters:** Badge is logged-in-only feature

#### `test_get_messages_ordering`
**What it tests:** Messages returned in chronological order (oldest first)
**How it works:** Creates 5 messages with small delays, fetches from cache
**Expected result:** Messages ordered 0, 1, 2, 3, 4 (chronological)
**Why it matters:** Chat display requires chronological order

#### `test_get_messages_limit`
**What it tests:** `get_messages()` respects limit parameter
**How it works:** Creates 10 messages, fetches with `limit=3`
**Expected result:** Returns only 3 messages (most recent)
**Why it matters:** Pagination support

#### `test_get_messages_before_timestamp`
**What it tests:** Pagination with `get_messages_before()` works correctly
**How it works:** Creates 5 messages, gets messages before message #2's timestamp
**Expected result:** Returns messages 0 and 1 (chronological order)
**Why it matters:** Scroll-up pagination in chat UI

#### `test_cache_retention_max_count`
**What it tests:** Cache trims to MAX_MESSAGES (500 by default, 10 in test)
**How it works:** Temporarily sets `MAX_MESSAGES=10`, creates 15 messages
**Expected result:** Only last 10 messages remain (5-14)
**Why it matters:** Memory management

#### `test_add_pinned_message`
**What it tests:** Pinned messages added to separate cache
**How it works:** Creates message, sets `is_pinned=True`, adds to pinned cache
**Expected result:** Message appears in `get_pinned_messages()` with pin metadata
**Why it matters:** Pinned message caching

#### `test_pinned_message_auto_expiry`
**What it tests:** Expired pins automatically removed
**How it works:** Creates message with `pinned_until` in the past, adds to cache
**Expected result:** `get_pinned_messages()` returns empty list (auto-removed)
**Why it matters:** Automatic cleanup of expired pins

#### `test_remove_pinned_message`
**What it tests:** Manual pin removal works
**How it works:** Adds pin to cache, calls `remove_pinned_message()`, checks cache
**Expected result:** Pin removed from cache
**Why it matters:** Unpin functionality

#### `test_multiple_pinned_messages_ordering`
**What it tests:** Pinned messages ordered by `pinned_until` timestamp
**How it works:** Creates 3 pins with different expiry times (1h, 2h, 3h)
**Expected result:** Ordered by expiry (earliest first: Pin 0, Pin 1, Pin 2)
**Why it matters:** Pin display order

#### `test_backroom_messages_separate_cache`
**What it tests:** Backroom messages use same cache key (no longer separate)
**How it works:** Creates regular and backroom messages, checks both are cached
**Expected result:** Both messages appear in cache
**Why it matters:** Unified message caching

#### `test_clear_chat_cache`
**What it tests:** Clearing cache removes all messages and pins
**How it works:** Adds messages and pins, calls `clear_chat_cache()`, checks both caches empty
**Expected result:** All caches cleared
**Why it matters:** Manual cache invalidation

#### `test_message_serialization_completeness`
**What it tests:** All message fields properly serialized to Redis
**How it works:** Creates message with ALL optional fields (reply_to, pinned, amount_paid, etc.), checks cached version
**Expected result:** All fields present in cached JSON
**Why it matters:** Complete data preservation in cache

#### `test_redis_failure_graceful_degradation`
**What it tests:** Redis failures don't crash (returns False/empty list)
**How it works:** Calls all cache methods, ensures no exceptions raised
**Expected result:** All methods complete without exceptions
**Why it matters:** Resilience - PostgreSQL is source of truth, Redis failures are non-fatal

### 6.2 Redis Performance Tests (7 tests)

**Test Class:** `RedisPerformanceTests`

These tests benchmark cache performance and print timing results.

#### `test_write_performance_postgresql_only`
**What it tests:** PostgreSQL write speed baseline
**How it works:** Writes 100 messages to PostgreSQL only
**Expected result:** Completes in <10 seconds, prints ms per message
**Why it matters:** Baseline for comparison

#### `test_write_performance_dual_write`
**What it tests:** Dual-write (PostgreSQL + Redis) speed
**How it works:** Writes 100 messages to both stores
**Expected result:** Completes in <10 seconds, prints ms per message
**Why it matters:** Measures overhead of Redis caching

#### `test_read_performance_redis_cache_hit`
**What it tests:** Redis read speed (cache hit)
**How it works:** Populates cache with 50 messages, reads 100 times
**Expected result:** <10ms per read
**Why it matters:** Demonstrates Redis speed advantage

#### `test_read_performance_postgresql_fallback`
**What it tests:** PostgreSQL read speed (cache miss)
**How it works:** Creates 50 messages (NOT cached), reads 100 times from PostgreSQL
**Expected result:** Completes in <10 seconds, slower than Redis
**Why it matters:** Shows cost of cache miss

#### `test_cache_hit_rate_simulation`
**What it tests:** Realistic cache hit rate scenario
**How it works:** Creates 100 cached messages, reads 1000 times
**Expected result:** ~100% hit rate (all reads from cache)
**Why it matters:** Simulates active chat performance

#### `test_pinned_message_performance`
**What it tests:** Pinned message operation speed
**How it works:** Adds 10 pins, reads 100 times
**Expected result:** <10ms per read
**Why it matters:** Pin cache performance

### 6.3 Redis Reaction Cache Tests (20 tests)

**Test Class:** `RedisReactionCacheTests`

#### `test_set_message_reactions`
**What it tests:** Reaction summary caching works
**How it works:** Sets reactions `[{emoji: "👍", count: 5}, {emoji: "❤️", count: 3}, {emoji: "😂", count: 1}]`, fetches from cache
**Expected result:** All 3 reactions cached with correct counts
**Why it matters:** Core reaction caching

#### `test_get_message_reactions_cache_miss`
**What it tests:** Cache miss returns empty list
**How it works:** Fetches reactions for non-cached message
**Expected result:** Returns `[]`
**Why it matters:** Fallback behavior

#### `test_set_empty_reactions_deletes_cache`
**What it tests:** Setting empty reactions removes cache key
**How it works:** Caches reactions, then sets `[]`, checks cache
**Expected result:** Cache key deleted
**Why it matters:** Cleanup when all reactions removed

#### `test_batch_get_reactions`
**What it tests:** Batch fetch multiple message reactions (single Redis round-trip)
**How it works:** Caches reactions for 2 messages, batch fetches both
**Expected result:** Returns dict with both messages' reactions
**Why it matters:** Performance optimization for loading message list

#### `test_batch_get_reactions_with_cache_miss`
**What it tests:** Batch fetch handles missing messages
**How it works:** Caches reactions for message1 only, batch fetches [message1, message2]
**Expected result:** message1 has reactions, message2 has empty list
**Why it matters:** Partial cache hits

#### `test_batch_get_reactions_empty_list`
**What it tests:** Batch fetch with empty input
**How it works:** Calls `batch_get_reactions(chat_code, [])`
**Expected result:** Returns `{}`
**Why it matters:** Edge case handling

#### `test_batch_get_reactions_single_round_trip`
**What it tests:** Batch fetch uses pipelining (single Redis call)
**How it works:** Caches 10 message reactions, batch fetches all 10, measures time
**Expected result:** <50ms for 10 messages
**Why it matters:** Performance verification

#### `test_reaction_cache_ttl`
**What it tests:** Reaction cache has 24-hour TTL
**How it works:** Caches reactions, checks Redis TTL
**Expected result:** TTL between 86000-86500 seconds (~24 hours)
**Why it matters:** Cache expiry policy

#### `test_reaction_cache_update`
**What it tests:** Updating cached reactions works
**How it works:** Caches `[{emoji: "👍", count: 2}]`, updates to `[{emoji: "👍", count: 3}, {emoji: "❤️", count: 1}]`
**Expected result:** Cache reflects updated counts
**Why it matters:** Reaction count updates

#### `test_different_messages_separate_cache`
**What it tests:** Different messages have separate caches
**How it works:** Caches different reactions for message1 and message2
**Expected result:** Each message has its own reactions
**Why it matters:** Cache isolation

#### `test_reaction_cache_redis_failure_graceful`
**What it tests:** Redis failures don't crash
**How it works:** Calls all reaction cache methods
**Expected result:** No exceptions raised
**Why it matters:** Graceful degradation

---

## Running Tests

### Run All Tests
```bash
cd backend
./venv/bin/python manage.py test
```

### Run Specific Test Suite
```bash
# Security tests (26 tests)
./venv/bin/python manage.py test chats.tests_security

# Username validation tests (10 tests)
./venv/bin/python manage.py test chats.tests_validators

# Profanity filter tests (26 tests)
./venv/bin/python manage.py test chats.tests_profanity

# Rate limit tests (12 tests)
./venv/bin/python manage.py test chats.tests_rate_limits

# Dual sessions tests (16 tests)
./venv/bin/python manage.py test chats.tests_dual_sessions

# Redis cache tests (49 tests)
./venv/bin/python manage.py test chats.tests_redis_cache
```

### Run Specific Test Class
```bash
./venv/bin/python manage.py test chats.tests_security.ChatSessionSecurityTests
```

### Run with Verbose Output
```bash
./venv/bin/python manage.py test -v 2
```

---

## Test Coverage Summary

| Feature Area | Tests | Coverage Level |
|--------------|-------|----------------|
| JWT Authentication | 17 | Comprehensive - all attack vectors covered |
| Username Reservations | 9 | Comprehensive - all edge cases covered |
| Username Validation | 10 | Comprehensive - all valid/invalid patterns |
| Profanity Filtering | 26 | Comprehensive - all entry points + bypass attempts |
| Rate Limiting | 12 | Comprehensive - limits, isolation, edge cases |
| Dual Sessions | 16 | Comprehensive - anonymous/logged-in coexistence |
| Redis Caching | 49 | Comprehensive - correctness + performance benchmarks |

**Overall Coverage:** 139 tests covering security, validation, caching, and performance
