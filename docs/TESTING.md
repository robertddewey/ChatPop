# Testing Documentation

**Total Test Count:** 401 tests across 23 test suites

This document provides comprehensive documentation of all backend tests, including what each test does and why it's important.

---

## Test Suites Overview

| Test Suite | File | Test Count | Purpose |
|------------|------|------------|---------|
| [Security Tests](#1-security-tests-chatsteststs_securitypy) | `chats/tests/tests_security.py` | 26 tests | JWT authentication, username reservations, attack prevention |
| [Username Validation](#2-username-validation-tests-chatsteststs_validatorspy) | `chats/tests/tests_validators.py` | 10 tests | Username format and character validation |
| [Username Generation](#3-username-generation-tests-chatsteststs_username_generationpy) | `chats/tests/tests_username_generation.py` | 48 tests | Global username uniqueness, rate limiting, case preservation, per-chat rotation |
| [Username Flow Integration](#4-username-flow-integration-tests-chatsteststs_username_flow_integrationpy) | `chats/tests/tests_username_flow_integration.py` | 10 tests | End-to-end username suggest→join flow, case preservation, rotation without consecutive duplicates |
| [Username Generation Redis Bug](#5-username-generation-redis-bug-tests-chatsteststest_username_generation_redis_bugpy) | `chats/tests/test_username_generation_redis_bug.py` | 6 tests | Regression tests for Redis SET atomicity fix |
| [Profanity Filtering](#6-profanity-filtering-tests-chatsteststs_profanitypy) | `chats/tests/tests_profanity.py` | 26 tests | Profanity detection across all username entry points |
| [Dual Sessions](#7-dual-sessions-tests-chatsteststs_dual_sessionspy) | `chats/tests/tests_dual_sessions.py` | 16 tests | Anonymous/logged-in user coexistence |
| [Redis Caching](#8-redis-caching-tests-chatsteststs_redis_cachepy) | `chats/tests/tests_redis_cache.py` | 44 tests | Message caching, cache backfill, Constance controls, performance |
| [Partial Cache Hits](#10-partial-cache-hits-tests-chatsteststs_partial_cache_hitspy) | `chats/tests/tests_partial_cache_hits.py` | 8 tests | Handling messages split between Redis and PostgreSQL |
| [Message Deletion](#9-message-deletion-tests-chatsteststs_message_deletionpy) | `chats/tests/tests_message_deletion.py` | 22 tests | Soft delete, cache invalidation, authorization, WebSocket broadcasting |
| [User Blocking](#11-user-blocking-tests-chatsteststs_user_blockingpy) | `chats/tests/tests_user_blocking.py` | 28 tests | User-to-user blocking, Redis cache sync, SQL injection prevention |
| [Chat Ban Enforcement](#12-chat-ban-enforcement-tests-chatsteststs_chat_ban_enforcementpy) | `chats/tests/tests_chat_ban_enforcement.py` | 20 tests | Host-only chat bans, consolidated blocking, WebSocket & HTTP enforcement |
| [Blocking](#13-blocking-tests-chatsteststs_blockingpy) | `chats/tests/tests_blocking.py` | 27 tests | Blocking utility functions, consolidated blocking model |
| [Blocking Redirect](#14-blocking-redirect-tests-chatsteststs_blocking_redirectpy) | `chats/tests/tests_blocking_redirect.py` | 9 tests | Redirect enforcement for blocked users |
| [Voice Messages](#15-voice-messages-tests-chatsteststs_voice_messagespy) | `chats/tests/tests_voice_messages.py` | 19 tests | Voice upload, streaming, authorization, storage |
| [WebSocket Tests](#16-websocket-tests-chatsteststs_websocketpy) | `chats/tests/tests_websocket.py` | 4 tests | WebSocket connection, authentication, message broadcasting |
| [Account Security](#17-account-security-tests-accountstestspy) | `accounts/tests.py` | 17 tests | Registration username security, race condition prevention, API bypass protection |
| [Vision API Tests](#18-vision-api-tests-photo_analysisteststest_vision_apipy) | `photo_analysis/tests/test_vision_api.py` | 11 tests | OpenAI GPT-4o Vision API integration (mocked), JSON parsing, token usage, error handling |
| [Photo Rate Limiting](#19-photo-rate-limiting-tests-photo_analysisteststest_rate_limitingpy) | `photo_analysis/tests/test_rate_limiting.py` | 12 tests | Redis-based upload rate limiting, client identifier extraction, per-hour limits |
| [Photo Deduplication](#20-photo-deduplication-tests-photo_analysisteststest_deduplicationpy) | `photo_analysis/tests/test_deduplication.py` | 5 tests | Dual-hash deduplication (pHash + MD5), cached result return, times-used counter |
| [Image Fingerprinting](#21-image-fingerprinting-tests-photo_analysisteststest_phash_comparisonpy) | `photo_analysis/tests/test_phash_comparison.py` | 8 tests | Perceptual hash similarity detection, Hamming distance calculation |
| [Photo Storage](#22-photo-storage-tests-photo_analysisteststest_storagepy) | `photo_analysis/tests/test_storage.py` | 26 tests | MediaStorage utility, local and S3 storage, file path generation |
| [Image Resizing](#23-image-resizing-tests-photo_analysisteststest_image_resizingpy) | `photo_analysis/tests/test_image_resizing.py` | 16 tests | Automatic image resizing, aspect ratio preservation, token usage optimization |

---

## 1. Security Tests (`chats/tests/tests_security.py`)

**File Location:** `backend/chats/tests/tests_security.py`
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

## 2. Username Validation Tests (`chats/tests/tests_validators.py`)

**File Location:** `backend/chats/tests/tests_validators.py`
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

## 3. Username Generation Tests (`chats/tests/tests_username_generation.py`)

**File Location:** `backend/chats/tests/tests_username_generation.py`
**Test Count:** 48 tests
**Test Classes:** `IsUsernameGloballyAvailableTestCase`, `GenerateUsernameTestCase`, `ChatSuggestUsernameAPITestCase`, `AccountsSuggestUsernameAPITestCase`, `CheckUsernameRedisReservationTestCase`, `UsernameValidationRedisReservationTestCase`

These tests verify the Global Username System including uniqueness checks, username generation with rate limiting, case preservation, unlimited rotation after rate limit, and Redis-based reservation to prevent race conditions.

### 3.1 Global Username Availability Tests (6 tests)

**Test Class:** `IsUsernameGloballyAvailableTestCase`

#### `test_available_username`
**What it tests:** Available usernames return True
**How it works:** Tests three usernames not in database: 'AvailableUser', 'NewUser123', 'UniqueUser'
**Expected result:** All return True
**Why it matters:** Positive test case for availability checker

#### `test_username_taken_by_reserved_user`
**What it tests:** Usernames reserved by registered users are detected
**How it works:** User has `reserved_username="ReservedUser"`, checks exact case and variants ('reserveduser', 'RESERVEDUSER', 'rEsErVeDuSeR')
**Expected result:** All return False (case-insensitive matching)
**Why it matters:** Protects reserved usernames with case-insensitive checking

#### `test_username_taken_by_chat_participant`
**What it tests:** Usernames used in any chat are globally unavailable
**How it works:** ChatParticipation has `username="ChatUser123"`, checks exact case and variants
**Expected result:** All return False (case-insensitive)
**Why it matters:** Global username uniqueness across all chats

#### `test_username_check_with_multiple_participations`
**What it tests:** Username from any chat makes it globally unavailable
**How it works:** Creates two chats, user joins second chat with 'AnotherUser', checks availability
**Expected result:** Returns False (taken in second chat)
**Why it matters:** Enforces global uniqueness across all chat rooms

#### `test_username_check_with_registered_user_participation`
**What it tests:** Both reserved username and chat username are checked
**How it works:** User has `reserved_username="User2Reserved"` and joins chat as 'User2ChatName'
**Expected result:** Both usernames unavailable
**Why it matters:** Dual protection - reserved and active chat usernames both reserved

###  3.2 Username Generation Function Tests (10 tests)

**Test Class:** `GenerateUsernameTestCase`

#### `test_successful_generation`
**What it tests:** Generate username returns valid username with remaining attempts
**How it works:** Calls `generate_username(fingerprint)`, checks format and `remaining` count
**Expected result:** Valid 5-15 char username, `remaining=9` (used 1 of 10)
**Why it matters:** Core generation functionality

#### `test_rate_limit_tracking`
**What it tests:** Rate limit counter decrements correctly over 10 generations
**How it works:** Makes 10 generations, checks `remaining` counts down from 9 to 0, then 11th fails
**Expected result:** First 10 succeed with correct counts, 11th returns `(None, 0)`
**Why it matters:** Enforces 10-per-hour global generation limit

#### `test_rate_limit_per_fingerprint`
**What it tests:** Rate limits are isolated per fingerprint
**How it works:** Exhausts 10 for fingerprint1, tries again (fails), tries fingerprint2 (succeeds)
**Expected result:** fingerprint1 blocked, fingerprint2 works
**Why it matters:** Independent limits prevent one user from blocking others

#### `test_custom_max_attempts_override`
**What it tests:** `max_attempts` parameter overrides Constance default
**How it works:** Calls with `max_attempts=100` (registration flow uses this)
**Expected result:** `remaining=99` (used 1 of 100)
**Why it matters:** Registration gets higher limit than anonymous join

#### `test_generated_usernames_tracking`
**What it tests:** Generated usernames are tracked in Redis with original capitalization
**How it works:** Generates username, checks Redis key `username:generated_for_fingerprint:{fp}`
**Expected result:** Redis set contains username with preserved case (e.g., "HappyTiger42", not "happytiger42")
**Why it matters:** Tracks usernames for API bypass prevention AND preserves capitalization

#### `test_chat_specific_cache`
**What it tests:** Chat-specific recent suggestions cache works
**How it works:** Generates username for specific chat_code, checks Redis `chat:{code}:recent_suggestions`
**Expected result:** Username appears in chat cache (lowercase)
**Why it matters:** Prevents immediate re-suggestion of same username in same chat

#### `test_global_uniqueness_check`
**What it tests:** Generated usernames avoid globally taken usernames
**How it works:** Reserves 'TakenUser1' in database, generates 5 usernames
**Expected result:** None of the 5 match 'TakenUser1'
**Why it matters:** Collision avoidance with existing usernames

#### `test_fallback_to_guest_usernames`
**What it tests:** Guest pattern fallback when generation struggles
**How it works:** Mocks word generation to fail, checks fallback to Guest{random}
**Expected result:** No crash, returns Guest username or fails gracefully
**Why it matters:** Resilience - always has fallback option

#### `test_constance_config_integration`
**What it tests:** Constance `MAX_USERNAME_GENERATION_ATTEMPTS_GLOBAL` setting is used
**How it works:** Sets config to 3, generates 3 usernames, 4th fails
**Expected result:** First 3 succeed, 4th returns `(None, 0)`
**Why it matters:** Runtime-configurable limit via Django admin

#### `test_redis_ttl_expiration`
**What it tests:** Redis tracking keys have 1-hour TTL
**How it works:** Generates username, checks Redis TTL on tracking keys
**Expected result:** Keys have TTL set
**Why it matters:** Automatic cleanup prevents Redis memory growth

### 3.3 Chat Suggest Username API Tests (16 tests)

**Test Class:** `ChatSuggestUsernameAPITestCase`

#### `test_successful_suggestion`
**What it tests:** API returns username with rate limit counters
**How it works:** POST to `/api/chats/{code}/suggest-username/` with fingerprint
**Expected result:** 200 OK, response contains `username`, `remaining` (per-chat), `generation_remaining` (global)
**Why it matters:** API structure verification

#### `test_dual_rate_limits`
**What it tests:** Both chat-specific and global limits are tracked
**How it works:** Makes suggestion, checks both counters
**Expected result:** `remaining=19` (per-chat: 20-1), `generation_remaining=9` (global: 10-1)
**Why it matters:** Dual rate limiting system verification

#### `test_global_generation_limit_hit`
**What it tests:** Rotation behavior when global limit is exceeded
**How it works:** Generates 2 usernames (global limit=2), then makes 10 more requests
**Expected result:** First 2 generate new usernames, next 10 rotate through those 2 usernames (all return 200 OK with `generation_remaining=0`)
**Why it matters:** Unlimited rotation feature - users can cycle through previously generated usernames after hitting global limit

#### `test_username_rotation_after_global_limit`
**What it tests:** Users can infinitely rotate through previously generated usernames
**How it works:** Generates 3 usernames (global limit=3), then makes 20 rotation requests
**Expected result:** All 20 succeed (200 OK), each returns one of the 3 previously generated usernames
**Why it matters:** Core rotation feature - prevents users from being completely blocked

#### `test_per_chat_rate_limit_separate_from_global`
**What it tests:** Per-chat and global limits are independent
**How it works:** Global=10, per-chat=3. Generates 3 in chat1 (hits per-chat limit), tries chat2
**Expected result:** Chat1 hits per-chat limit (`remaining=0`, `generation_remaining=7`), Chat2 succeeds (`remaining=2`, `generation_remaining=6`)
**Why it matters:** Independent limit tracking prevents cross-chat interference

#### `test_case_preservation_in_generation`
**What it tests:** Generated usernames preserve mixed case
**How it works:** Generates username, verifies pattern matches `AdjectiveNoun123` format
**Expected result:** Username has mixed case (e.g., "HappyTiger42"), stored in Redis with original capitalization
**Why it matters:** Respects AdjectiveNoun capitalization pattern

#### `test_case_preservation_in_rotation`
**What it tests:** Rotation returns exact capitalization from generation
**How it works:** Generates 3 usernames with specific capitalization, rotates 10 times
**Expected result:** Each rotation returns exact match (same capitalization) from original list
**Why it matters:** Case consistency across rotation cycles

#### `test_case_insensitive_uniqueness`
**What it tests:** Uniqueness checking is case-insensitive
**How it works:** User1 generates "Username1", reserves it in Redis as lowercase. User2 generates usernames.
**Expected result:** User2 never gets "Username1" (case-insensitive collision detection)
**Why it matters:** Prevents "HappyTiger42" and "happytiger42" coexistence

#### `test_fingerprint_extraction_from_body`
**What it tests:** Fingerprint extracted from request body
**How it works:** POST with `{'fingerprint': 'custom_fingerprint_123'}`
**Expected result:** Redis key uses custom fingerprint
**Why it matters:** Request body parameter handling

#### `test_ip_fallback_when_no_fingerprint`
**What it tests:** IP address fallback when fingerprint missing
**How it works:** POST without fingerprint, sets `REMOTE_ADDR="192.168.1.100"`
**Expected result:** Redis key uses IP address instead
**Why it matters:** Graceful degradation for clients without fingerprinting

#### `test_invalid_chat_code`
**What it tests:** Invalid chat code returns 404
**How it works:** POST to `/api/chats/INVALID/suggest-username/`
**Expected result:** 404 Not Found
**Why it matters:** Proper error handling

### 3.4 Account Suggest Username API Tests (5 tests)

**Test Class:** `AccountsSuggestUsernameAPITestCase`

Tests the `/api/auth/suggest-username/` endpoint used during registration (higher rate limit).

#### `test_registration_higher_limit`
**What it tests:** Registration gets 100 attempts instead of 10
**How it works:** Calls registration suggest endpoint, checks `remaining_attempts=99`
**Expected result:** 99 remaining (used 1 of 100)
**Why it matters:** Registration flow has higher limit than anonymous join

#### `test_successful_registration_suggestion`
**What it tests:** Registration endpoint returns valid username
**How it works:** POST to `/api/auth/suggest-username/`
**Expected result:** 200 OK, username 5-15 chars
**Why it matters:** Core registration suggestion flow

#### `test_ip_fallback_for_registration`
**What it tests:** IP fallback in registration flow
**How it works:** POST without fingerprint, checks Redis key uses IP
**Expected result:** Redis tracking uses IP address
**Why it matters:** Backward compatibility

#### `test_x_forwarded_for_header`
**What it tests:** X-Forwarded-For header used when available (proxy support)
**How it works:** Sets `HTTP_X_FORWARDED_FOR="203.0.113.1, 198.51.100.1"`
**Expected result:** Uses first IP (203.0.113.1)
**Why it matters:** Correct IP extraction behind proxies

#### `test_registration_rate_limit_exhaustion`
**What it tests:** 101st registration suggestion fails
**How it works:** Manually sets Redis counter to 100, attempts generation
**Expected result:** 429 Too Many Requests, `remaining_attempts=0`
**Why it matters:** Even registration has a (high) limit

### 3.5 Check Username Redis Reservation Tests (6 tests)

**Test Class:** `CheckUsernameRedisReservationTestCase`

Tests `/api/auth/check-username/` endpoint (real-time validation during registration).

#### `test_available_username_reserved_in_redis`
**What it tests:** Available usernames are temporarily reserved after check
**How it works:** GET `/api/auth/check-username/?username=ValidUser123`, checks Redis
**Expected result:** Username reserved in Redis with 10-minute TTL
**Why it matters:** Race condition prevention - reserves username during form completion

#### `test_unavailable_username_not_reserved`
**What it tests:** Taken usernames are not reserved
**How it works:** Checks username that already exists in database
**Expected result:** Returns `available: false`, no Redis reservation
**Why it matters:** Don't waste Redis space on unavailable usernames

#### `test_invalid_username_not_reserved`
**What it tests:** Invalid usernames (too short, etc.) not reserved
**How it works:** Checks 3-char username
**Expected result:** 400 Bad Request, no Redis reservation
**Why it matters:** Only valid, available usernames are reserved

#### `test_race_condition_prevention`
**What it tests:** Two users checking same username see it as taken after first check
**How it works:** User1 checks "RaceTest123" (reserved), User2 checks same username
**Expected result:** User1 gets `available: true`, User2 gets `available: false`
**Why it matters:** Critical race condition protection

#### `test_constance_ttl_setting_used`
**What it tests:** Constance `USERNAME_VALIDATION_TTL_MINUTES` setting controls TTL
**How it works:** Sets config to 5 minutes, checks username, verifies reservation exists
**Expected result:** Username reserved with 5-minute TTL
**Why it matters:** Configurable reservation window

#### `test_case_insensitive_reservation`
**What it tests:** Reservation is case-insensitive
**How it works:** Reserves "CaseSensitive", checks "casesensitive" and "CASESENSITIVE"
**Expected result:** All variants show as unavailable
**Why it matters:** Prevents case-variant squatting

### 3.6 Username Validation Redis Reservation Tests (7 tests)

**Test Class:** `UsernameValidationRedisReservationTestCase`

Tests `/api/chats/{code}/validate-username/` endpoint (real-time validation during chat join).

#### `test_available_username_reserved_in_redis`
**What it tests:** Available chat usernames are reserved after validation
**How it works:** POST `/api/chats/{code}/validate-username/` with available username
**Expected result:** Username reserved in Redis with 10-minute TTL
**Why it matters:** Race condition prevention during chat join

#### `test_unavailable_username_not_reserved`
**What it tests:** Taken chat usernames not reserved
**How it works:** Validates username that's already in use in chat
**Expected result:** Returns `available: false`, no reservation
**Why it matters:** Don't waste Redis space

#### `test_invalid_username_not_reserved`
**What it tests:** Invalid usernames (profanity, too short) not reserved
**How it works:** Validates 2-char username
**Expected result:** 400 Bad Request, no reservation
**Why it matters:** Only valid usernames are reserved

#### `test_race_condition_prevention`
**What it tests:** Two users validating same username see conflict
**How it works:** User1 validates "RaceChatTest" (reserved), User2 validates same
**Expected result:** User1 gets `available: true`, User2 gets `available: false`
**Why it matters:** Prevents two users from joining with same username

#### `test_constance_ttl_setting_used`
**What it tests:** TTL setting controls reservation duration
**How it works:** Sets `USERNAME_VALIDATION_TTL_MINUTES=5`, validates username
**Expected result:** 5-minute reservation
**Why it matters:** Configurable via Constance

#### `test_case_insensitive_reservation`
**What it tests:** Chat username reservation is case-insensitive
**How it works:** Validates "MixedCase", checks "mixedcase" and "MIXEDCASE"
**Expected result:** All variants unavailable after first reservation
**Why it matters:** Case-insensitive uniqueness in chats

#### `test_reserved_username_detected`
**What it tests:** User.reserved_username is checked during chat join validation
**How it works:** Validates username that matches host's reserved_username
**Expected result:** Returns `available: false`, `reserved_by_other: true`
**Why it matters:** Respects registered users' reserved usernames

---

## 4. Username Flow Integration Tests (`chats/tests/tests_username_flow_integration.py`)

**File Location:** `backend/chats/tests/tests_username_flow_integration.py`
**Test Count:** 10 tests
**Test Classes:** `UsernameGenerationToJoinFlowTestCase` (3 tests), `UsernameRotationIntegrationTestCase` (4 tests), `UsernameSecurityChecksIntegrationTestCase` (3 tests)

These integration tests verify the full end-to-end username flow from generation through joining a chat, including case preservation, rotation behavior, and security checks. Unlike unit tests that test individual components, these tests exercise the complete user journey.

### 4.1 Generation to Join Flow Tests (3 tests)

**Test Class:** `UsernameGenerationToJoinFlowTestCase`

#### `test_suggest_username_then_join_preserves_case`
**What it tests:** CRITICAL - Full suggest→join flow with case preservation (would have caught the case-sensitivity bug)
**How it works:**
1. POST to `/api/chats/{code}/suggest-username/` to get a username (e.g., "HappyTiger42")
2. Verify username has mixed case (matches `AdjectiveNoun123` pattern)
3. POST to `/api/chats/{code}/join/` with the EXACT suggested username
4. Verify join succeeds and ChatParticipation created with original capitalization
**Expected result:** Join succeeds with 200 OK, username stored as "HappyTiger42" (not "happytiger42")
**Why it matters:** This test catches the bug at `views.py:124` where the security check was doing case-sensitive comparison with case-preserved storage. This is the exact flow users experience.

#### `test_join_rejects_username_not_generated_for_fingerprint`
**What it tests:** Security - prevents using usernames not generated for this fingerprint
**How it works:**
1. Generate username for fingerprint1
2. Try to join with that username using fingerprint2
**Expected result:** Join fails with 400 Bad Request
**Why it matters:** API bypass prevention - ensures users can only use usernames they actually generated

#### `test_case_insensitive_join_attempt_with_different_case`
**What it tests:** Security - prevents bypassing with different case variations
**How it works:**
1. Generate "HappyTiger42" for fingerprint1
2. Try to join as "happytiger42" (all lowercase) with fingerprint1
**Expected result:** Join fails with 400 Bad Request
**Why it matters:** Prevents users from manually crafting lowercase/uppercase variations to bypass the system

### 4.2 Rotation Integration Tests (4 tests)

**Test Class:** `UsernameRotationIntegrationTestCase`

#### `test_rotation_preserves_original_capitalization`
**What it tests:** Rotation returns usernames with EXACT original capitalization
**How it works:**
1. Generate 3 usernames (global limit=3): e.g., "HappyTiger42", "SadPanda99", "ExcitedDog7"
2. Rotate 10 times
**Expected result:** All rotations return exact matches with original capitalization
**Why it matters:** Case consistency throughout rotation cycles

#### `test_rotation_then_join_integration`
**What it tests:** Full flow - generate → rotate → join with rotated username
**How it works:**
1. Generate 3 usernames (hits global limit)
2. Request 10 more usernames (rotation mode)
3. Pick the 5th rotated username
4. Join chat with that username
**Expected result:** Join succeeds, ChatParticipation created with rotated username
**Why it matters:** Ensures rotated usernames work identically to freshly generated ones

#### `test_rotation_no_consecutive_duplicates`
**What it tests:** CRITICAL - Rotation never returns same username consecutively
**How it works:**
1. Generate 3 usernames (global limit=3)
2. Rotate 15 times, tracking sequence
3. Check for consecutive duplicates (e.g., Alice, Alice)
**Expected result:** No two consecutive usernames are identical
**Why it matters:** Addresses user's requirement: "don't return: Alice, Alice, Alice, Bob, Alice, etc". Ensures predictable alphabetical rotation.

#### `test_rotation_after_username_becomes_unavailable`
**What it tests:** Rotation skips usernames that become globally unavailable
**How it works:**
1. Generate 3 usernames: ["Alpha1", "Beta2", "Gamma3"]
2. Another user takes "Beta2" globally
3. Rotate and verify "Beta2" never appears
**Expected result:** Only "Alpha1" and "Gamma3" in rotation
**Why it matters:** Real-time availability checking prevents suggesting taken usernames

### 4.3 Security Checks Integration Tests (3 tests)

**Test Class:** `UsernameSecurityChecksIntegrationTestCase`

#### `test_case_preserved_username_passes_security_check`
**What it tests:** CRITICAL BUG FIX - Case-preserved usernames pass the security check at `views.py:124`
**How it works:**
1. Generate "HappyTiger42"
2. Verify it's stored in Redis as "HappyTiger42" (original case)
3. Join with "HappyTiger42"
**Expected result:** Security check creates lowercase set for comparison, join succeeds
**Why it matters:** This directly tests the bug fix - ensures the security check handles case-insensitive comparison with case-preserved storage

#### `test_cannot_bypass_generation_with_manual_username`
**What it tests:** Anonymous users can't manually craft usernames
**How it works:**
1. Don't generate any usernames
2. Try to join directly with "ManualUsername123"
**Expected result:** Join fails with "Invalid username. Please use the suggest username feature" error
**Why it matters:** Forces anonymous users through the generation/rotation system

#### `test_rejoining_user_bypasses_generation_check`
**What it tests:** Returning users can rejoin without regenerating
**How it works:**
1. User generates username and joins
2. User leaves chat (ChatParticipation deleted)
3. User rejoins with same username
**Expected result:** Join succeeds without needing to regenerate
**Why it matters:** Returning users aren't subject to the security check

### Running These Tests

```bash
# Run all integration tests
./venv/bin/python manage.py test chats.tests.tests_username_flow_integration

# Run specific test class
./venv/bin/python manage.py test chats.tests.tests_username_flow_integration.UsernameRotationIntegrationTestCase

# Run critical test that would have caught the bug
./venv/bin/python manage.py test chats.tests.tests_username_flow_integration.UsernameGenerationToJoinFlowTestCase.test_suggest_username_then_join_preserves_case
```

---

## 5. Username Generation Redis Bug Tests (`chats/tests/test_username_generation_redis_bug.py`)

**File Location:** `backend/chats/tests/test_username_generation_redis_bug.py`
**Test Count:** 6 tests
**Test Class:** `UsernameGenerationRedisBugTest`

### Overview

**CRITICAL BUG EXPOSURE:** This test suite documents a critical bug where generated usernames are NOT being saved to Redis fingerprint-to-username mappings. This breaks username rotation and reuse detection.

**Bug Impact:**
- Users cannot reuse their previously generated usernames
- False "username taken" messages appear
- Username rotation fails completely
- Only affects fingerprint mapping - all other caching (global reservation, chat suggestions, attempt tracking) works correctly

#### `test_generated_username_saved_to_fingerprint_set`
**What it tests:** Generated username should be stored in Redis under `username:generated_for_fingerprint:{fingerprint}` key
**Expected result:** Redis key exists with generated username in SET
**Actual result:** ❌ **FAILS** - key is never written to Redis
**Why it matters:** This is the root cause of username rotation failures

#### `test_multiple_generations_accumulate_in_fingerprint_set`
**What it tests:** Multiple username generations for same fingerprint accumulate in Redis SET
**Expected result:** Redis SET contains all previously generated usernames
**Actual result:** ❌ **FAILS** - no usernames are stored (key never written)
**Why it matters:** Prevents tracking all usernames generated for a single device

#### `test_fingerprint_set_has_correct_ttl`
**What it tests:** Fingerprint SET has proper TTL matching `USERNAME_RESERVATION_TTL_MINUTES` (60 minutes = 3600 seconds)
**Expected result:** Redis key has 3600 second TTL
**Actual result:** ❌ **FAILS** - key doesn't exist, so TTL is irrelevant
**Why it matters:** Without TTL, old username reservations won't expire

#### `test_global_reservation_key_exists`
**What it tests:** Global username reservation works correctly
**Expected result:** `username:reserved:{username}` key exists after generation
**Actual result:** ✅ **PASSES** - global reservation IS working
**Why it matters:** Proves bug is isolated to fingerprint mapping, not global reservation

#### `test_chat_specific_suggestions_exists`
**What it tests:** Chat-specific recent suggestions cache works correctly
**Expected result:** `chat:{chat_code}:recent_suggestions` cache contains generated username
**Actual result:** ✅ **PASSES** - chat suggestions ARE working
**Why it matters:** Shows bug is isolated, not affecting all caching mechanisms

#### `test_generation_attempts_counter_increments`
**What it tests:** Generation attempts counter tracks correctly across multiple generations
**Expected result:** Remaining attempts decrements properly (20, 19, 18...)
**Actual result:** ✅ **PASSES** - attempt tracking works
**Why it matters:** Proves attempt tracking works, bug is specifically in fingerprint mapping

**Running This Suite:**
```bash
./venv/bin/python manage.py test chats.tests.test_username_generation_redis_bug
```

---

## 6. Profanity Filtering Tests (`chats/tests/tests_profanity.py`)

**File Location:** `backend/chats/tests/tests_profanity.py`
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

## 7. Dual Sessions Tests (`chats/tests/tests_dual_sessions.py`)

**File Location:** `backend/chats/tests/tests_dual_sessions.py`
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

## 8. Redis Caching Tests (`chats/tests/tests_redis_cache.py`)

**File Location:** `backend/chats/tests/tests_redis_cache.py`
**Test Count:** 44 tests
**Test Classes:** `RedisMessageCacheTests` (23 tests), `RedisPerformanceTests` (7 tests), `RedisReactionCacheTests` (10 tests), `ConstanceCacheControlTests` (10 tests)

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

### 6.4 Constance Cache Control Tests (10 tests)

**Test Class:** `ConstanceCacheControlTests`

These tests verify the Constance dynamic settings for runtime cache control (`REDIS_CACHE_ENABLED`).

#### `test_redis_cache_write_enabled_true`
**What it tests:** Messages are written to cache when `REDIS_CACHE_WRITE_ENABLED=True`
**How it works:** Enables write setting, creates message, manually calls `MessageCache.add_message()`
**Expected result:** Message appears in Redis cache
**Why it matters:** Verifies cache write control works

#### `test_redis_cache_write_enabled_false`
**What it tests:** Messages are NOT written when `REDIS_CACHE_WRITE_ENABLED=False`
**How it works:** Disables write setting, creates message, conditionally calls add_message
**Expected result:** Message NOT in Redis, but exists in PostgreSQL
**Why it matters:** Allows disabling cache writes to save CPU/memory

#### `test_redis_cache_enabled_true_reads_from_cache`
**What it tests:** `REDIS_CACHE_ENABLED=True` causes MessageListView to read from Redis
**How it works:** Enables cache, creates and caches message, calls API view
**Expected result:** Response has `source: 'redis'`, `cache_enabled: true`
**Why it matters:** Verifies cache read control works

#### `test_redis_cache_enabled_false_reads_from_postgresql`
**What it tests:** `REDIS_CACHE_ENABLED=False` causes reads from PostgreSQL
**How it works:** Disables cache, creates message (not cached), calls API view
**Expected result:** Response has `source: 'postgresql'`, `cache_enabled: false`
**Why it matters:** Allows disabling cache for debugging or small-scale deployments

#### `test_cache_miss_fallback_to_postgresql`
**What it tests:** Cache miss automatically falls back to PostgreSQL
**How it works:** Enables cache, creates message but DON'T cache it, calls API view
**Expected result:** Response has `source: 'postgresql_fallback'`, message loaded from DB
**Why it matters:** Graceful fallback when cache is empty

#### `test_pagination_always_uses_postgresql`
**What it tests:** Pagination requests never use cache (always PostgreSQL)
**How it works:** Enables cache, creates and caches messages, requests with `?before=<timestamp>`
**Expected result:** Response has `source: 'postgresql'` despite cache being enabled
**Why it matters:** Pagination logic bypass is intentional (cache doesn't support before queries)

#### `test_cache_ttl_expiry`
**What it tests:** Messages have 24-hour TTL in Redis
**How it works:** Caches message, checks Redis TTL on key
**Expected result:** TTL between 86000-86500 seconds (~24 hours)
**Why it matters:** Automatic cache expiry prevents stale data

#### `test_cache_hit_performance_vs_postgresql`
**What it tests:** Redis cache is faster than PostgreSQL
**How it works:** Creates 50 messages, reads 100 times from Redis, then 100 times from PostgreSQL, compares timing
**Expected result:** Redis avg time ≤ PostgreSQL avg time (prints speedup factor)
**Why it matters:** Validates performance benefit of caching

#### `test_toggle_cache_settings_runtime`
**What it tests:** Cache settings can be changed dynamically at runtime
**How it works:** Starts with cache disabled, creates message (not cached), enables cache, creates another message (cached), enables read, verifies reads from Redis
**Expected result:** Settings take effect immediately without restart
**Why it matters:** Demonstrates Constance dynamic configuration works correctly

#### `test_cache_backfill_on_miss`
**What it tests:** Cache miss triggers automatic backfill to Redis
**How it works:** Creates 5 messages in PostgreSQL (not cached), makes initial API request, verifies messages are backfilled to cache, makes second request
**Expected result:** First request returns `source: 'postgresql_fallback'` and backfills cache, second request returns `source: 'redis'` (cache hit)
**Why it matters:** Prevents repeated cache misses - first user after cache expiry populates cache for all subsequent users (prevents thundering herd problem)

---

## 9. Message Deletion Tests (`chats/tests/tests_message_deletion.py`)

**File Location:** `backend/chats/tests/tests_message_deletion.py`
**Test Count:** 22 tests
**Test Classes:** `MessageDeletionAuthorizationTests` (7 tests), `MessageSoftDeletionTests` (6 tests), `MessageCacheInvalidationTests` (4 tests), `MessageDeletionWebSocketTests` (2 tests), `MessageDeletionEdgeCasesTests` (5 tests)

### 7.1 Message Deletion Authorization Tests (7 tests)

**Test Class:** `MessageDeletionAuthorizationTests`

These tests verify that only chat hosts can delete messages and that proper session validation is enforced.

#### `test_host_can_delete_message`
**What it tests:** Chat host can delete any message
**How it works:** Host authenticates, posts to `/api/chats/{code}/messages/{message_id}/delete/` with valid session token
**Expected result:** 200 OK, message `is_deleted` flag set to True in database
**Why it matters:** Core deletion functionality for hosts

#### `test_participant_cannot_delete_message`
**What it tests:** Non-host participants cannot delete messages
**How it works:** Participant authenticates, attempts to delete message
**Expected result:** 403 Forbidden, message NOT deleted
**Why it matters:** Prevents abuse - only hosts control message deletion

#### `test_unauthenticated_user_cannot_delete_message`
**What it tests:** Unauthenticated users cannot delete messages
**How it works:** No authentication, fake session token
**Expected result:** 403 Forbidden
**Why it matters:** Basic authentication enforcement

#### `test_missing_session_token_rejected`
**What it tests:** Requests without session token are rejected
**How it works:** Host authenticates but sends request without `session_token` field
**Expected result:** 403 Forbidden with "session token" in error message
**Why it matters:** Session token is required for all authenticated actions

#### `test_invalid_session_token_rejected`
**What it tests:** Invalid/malformed session tokens are rejected
**How it works:** Host sends request with `session_token: 'invalid-token-12345'`
**Expected result:** 403 Forbidden
**Why it matters:** Prevents forged token attacks

#### `test_user_from_different_chat_cannot_delete`
**What it tests:** Session tokens are chat-specific
**How it works:** Host of Chat A tries to delete message from Chat B using their Chat A session token
**Expected result:** 403 Forbidden
**Why it matters:** Prevents cross-chat attacks

#### `test_host_can_delete_others_messages`
**What it tests:** Host can delete messages from other users (implicit in test_host_can_delete_message)
**How it works:** Host deletes participant's message
**Expected result:** 200 OK, message deleted
**Why it matters:** Hosts have moderation powers

### 7.2 Message Soft Deletion Tests (6 tests)

**Test Class:** `MessageSoftDeletionTests`

These tests verify that messages are never physically deleted from the database - only flagged as deleted.

#### `test_message_not_physically_deleted`
**What it tests:** Message record still exists in database after deletion
**How it works:** Deletes message, queries `Message.objects.filter(id=message_id).exists()`
**Expected result:** Returns True (message exists)
**Why it matters:** Data preservation for audit trails and potential recovery

#### `test_is_deleted_flag_set_to_true`
**What it tests:** `is_deleted` field is set to True
**How it works:** Deletes message, refreshes from DB, checks `message.is_deleted`
**Expected result:** `is_deleted == True`
**Why it matters:** Core soft delete mechanism

#### `test_message_content_preserved_after_deletion`
**What it tests:** All message data is preserved (content, username, timestamp, etc.)
**How it works:** Stores original values, deletes message, compares all fields
**Expected result:** All fields unchanged except `is_deleted`
**Why it matters:** Data integrity for audit logs

#### `test_already_deleted_message_returns_success`
**What it tests:** Deleting already-deleted message is idempotent
**How it works:** Deletes message twice with same request
**Expected result:** Both return 200 OK, second includes `already_deleted: true` flag
**Why it matters:** Prevents errors from duplicate delete requests

#### `test_deleted_message_count_preserved`
**What it tests:** Message count doesn't decrease after deletion
**How it works:** Counts messages before and after deletion
**Expected result:** Count remains the same
**Why it matters:** Verifies soft delete doesn't remove records

#### `test_deleted_messages_excluded_from_queries`
**What it tests:** Deleted messages don't appear in message list queries (implicit - tested via API)
**Why it matters:** Deleted messages should be hidden from users

### 7.3 Message Cache Invalidation Tests (4 tests)

**Test Class:** `MessageCacheInvalidationTests`

These tests verify that Redis cache is properly cleared when messages are deleted.

#### `test_cache_remove_called_on_deletion`
**What it tests:** `MessageCache.remove_message()` is called during deletion
**How it works:** Mocks `MessageCache.remove_message`, deletes message, verifies mock was called
**Expected result:** Mock called with correct chat_code and message_id
**Why it matters:** Ensures cache invalidation is triggered

#### `test_cache_invalidation_removes_message_from_messages_cache`
**What it tests:** Message removed from main messages Redis cache
**How it works:** Adds message to cache, verifies presence, deletes message, verifies absence
**Expected result:** Message not in cache after deletion
**Why it matters:** Prevents deleted messages from appearing via cached data

#### `test_cache_invalidation_removes_message_from_pinned_cache`
**What it tests:** Pinned messages removed from pinned cache
**How it works:** Pins message, adds to pinned cache, deletes, verifies removal from pinned cache
**Expected result:** Message not in pinned cache after deletion
**Why it matters:** Pinned message cache must be synchronized

#### `test_cache_invalidation_removes_reactions_cache`
**What it tests:** Reaction cache cleared for deleted message
**How it works:** Caches reactions for message, deletes message, verifies reaction cache cleared
**Expected result:** No reactions cached after deletion
**Why it matters:** Complete cache cleanup - reactions for deleted messages should not persist

### 7.4 Message Deletion WebSocket Tests (2 tests)

**Test Class:** `MessageDeletionWebSocketTests`

These tests verify real-time broadcasting of deletion events to all connected clients.

#### `test_websocket_broadcast_called_on_deletion`
**What it tests:** WebSocket `group_send` is called when message deleted
**How it works:** Mocks Django Channels `get_channel_layer()`, deletes message, verifies `group_send` called
**Expected result:** `group_send()` called with correct group name (`chat_{code}`) and message data
**Why it matters:** Real-time updates to all connected clients

#### `test_websocket_message_includes_correct_message_id`
**What it tests:** WebSocket event contains correct message ID
**How it works:** Mocks channel layer, deletes message, inspects `group_send` call arguments
**Expected result:** Message data includes `{type: 'message_deleted', message_id: '<uuid>'}`
**Why it matters:** Frontend needs message ID to remove from UI

### 7.5 Message Deletion Edge Cases Tests (5 tests)

**Test Class:** `MessageDeletionEdgeCasesTests`

#### `test_delete_nonexistent_message_returns_404`
**What it tests:** Deleting non-existent message UUID returns 404
**How it works:** Host tries to delete fake UUID
**Expected result:** 404 Not Found
**Why it matters:** Proper error handling for invalid IDs

#### `test_delete_message_from_wrong_chat_returns_404`
**What it tests:** Message from Chat A can't be deleted via Chat B endpoint
**How it works:** Creates message in Chat A, tries to delete via `/api/chats/CHATB/messages/{id}/delete/`
**Expected result:** 404 Not Found, message NOT deleted
**Why it matters:** Prevents cross-chat manipulation

#### `test_delete_from_inactive_chat_returns_404`
**What it tests:** Can't delete messages from inactive chats
**How it works:** Sets chat `is_active=False`, tries to delete message
**Expected result:** 404 Not Found
**Why it matters:** Inactive chats are effectively archived

#### `test_response_includes_message_id`
**What it tests:** Successful deletion returns message ID in response
**How it works:** Deletes message, checks response JSON structure
**Expected result:** `{success: true, message_id: '<uuid>', message: '...'}`
**Why it matters:** API contract - frontend can confirm correct message was deleted

#### `test_deletion_succeeds_even_if_cache_removal_fails`
**What it tests:** Database deletion succeeds even if Redis cache removal fails
**How it works:** Mocks `MessageCache.remove_message()` to return False, deletes message
**Expected result:** 200 OK, message marked `is_deleted` in database
**Why it matters:** Redis failures are non-fatal - PostgreSQL is source of truth

---

## 10. Partial Cache Hits Tests (`chats/tests/tests_partial_cache_hits.py`)

**File Location:** `backend/chats/tests/tests_partial_cache_hits.py`
**Test Count:** 8 tests
**Test Class:** `PartialCacheHitTests`

### Overview

Verifies Redis hybrid cache/database query handling when cache contains fewer messages than requested (partial hits). Tests real-world scenarios where users scroll through message history that's split between Redis cache and PostgreSQL database.

#### `test_partial_cache_hit_30_cached_50_requested`
**What it tests:** Cache has 30 messages, user requests 50
**Expected result:** First 30 from cache + remaining 20 from database, chronological ordering (oldest first)
**Verifies:** Source is `hybrid_redis_postgresql`
**Why it matters:** Performance optimization for large message histories - uses cache as much as possible

#### `test_exact_cache_match_50_cached_50_requested`
**What it tests:** Cache has exact 50 messages requested
**Expected result:** All 50 from Redis, no database queries
**Verifies:** Source is `redis`
**Why it matters:** Ensures pure cache hits are identified and used efficiently

#### `test_cache_overflow_100_cached_50_requested`
**What it tests:** Cache has 100 messages, user requests 50
**Expected result:** Only most recent 50 returned, all from cache
**Verifies:** Source is `redis`
**Why it matters:** Tests cache size management and prevents memory waste

#### `test_full_cache_miss_backfill`
**What it tests:** Cache is empty, user requests 50
**Expected result:** All from database with backfill to cache, subsequent request hits cache
**Verifies:** Source is `postgresql_fallback` initially, then `redis` after backfill
**Why it matters:** Ensures cache is populated on miss for future performance

####  `test_pagination_with_partial_backfill`
**What it tests:** Database has 100 messages, cache has 30 (most recent), user requests 50 then paginates
**Expected result:** Hybrid query followed by pagination through older messages
**Why it matters:** Real-world usage pattern - users scroll through message history

#### `test_partial_cache_hit_with_empty_database_tail`
**What it tests:** Cache has 30 messages, user requests 50, but database only has 40 total
**Expected result:** Returns all 40 available (not 50), source is `hybrid_redis_postgresql`, no duplicates
**Why it matters:** Edge case handling - prevents off-by-one errors

#### `test_performance_hybrid_vs_full_db`
**What it tests:** Compares performance: full DB query vs hybrid query vs pure cache
**Benchmark:** 200 messages from PostgreSQL vs 150 from cache + 50 from DB vs 200 from Redis
**Expected result:** Logs performance metrics for benchmarking
**Why it matters:** Quantifies performance gains from Redis integration

#### `test_security_limit_enforcement_with_partial_cache`
**What it tests:** User requests 99,999 messages with partial cache hit
**Expected result:** System caps at `MESSAGE_HISTORY_MAX_COUNT` (default: 500)
**Why it matters:** Security - prevents excessive memory use and DoS attacks

**Running This Suite:**
```bash
./venv/bin/python manage.py test chats.tests.tests_partial_cache_hits
```

---

## 11. User Blocking Tests (`chats/tests/tests_user_blocking.py`)

**File Location:** `backend/chats/tests/tests_user_blocking.py`
**Test Count:** 28 tests
**Test Classes:** `UserBlockingBasicTests` (9 tests), `UserBlockingRedisCacheTests` (7 tests), `UserBlockingWebSocketTests` (5 tests), `UserBlockingPerformanceTests` (3 tests), `UserBlockingEdgeCaseTests` (4 tests)

### 9.1 User Blocking Basic Tests (9 tests)

**Test Class:** `UserBlockingBasicTests`

These tests verify the core user blocking functionality including authorization, username validation, and SQL injection prevention.

#### `test_authenticated_user_can_block_another_user`
**What it tests:** Authenticated users can block other users site-wide
**How it works:** Alice authenticates, creates chat participation for Bob, blocks Bob via `/api/chats/user-blocks/block/`
**Expected result:** 201 Created, UserBlock entry created in database
**Why it matters:** Core blocking functionality for registered users

#### `test_unauthenticated_user_cannot_block`
**What it tests:** Anonymous users cannot use blocking feature
**How it works:** Attempts to block without authentication
**Expected result:** 401 Unauthorized
**Why it matters:** Blocking is a registered-user-only feature

#### `test_cannot_block_self`
**What it tests:** Users cannot block themselves
**How it works:** Alice tries to block herself (case-insensitive check)
**Expected result:** 400 Bad Request with "cannot block yourself" error
**Why it matters:** Prevents self-blocking edge case

#### `test_block_nonexistent_user`
**What it tests:** Blocking non-existent username silently succeeds (prevents user enumeration)
**How it works:** Alice tries to block "NonExistentUser999" (not in ChatParticipation table)
**Expected result:** 200 OK with `created: false` and `block_id: null`, NO database entry created
**Why it matters:** Prevents user enumeration attacks AND database pollution (defense in depth against SQL injection)

#### `test_block_sql_injection_attempt`
**What it tests:** SQL injection attempts in username field are prevented and not stored
**How it works:** Tests 6 SQL injection patterns:
- `'; DROP TABLE chats_userblock; --`
- `' UNION SELECT * FROM accounts_user --`
- `'; DELETE FROM chats_userblock WHERE '1'='1`
- `admin' OR '1'='1`
- `' OR 1=1 --`
- `'; UPDATE accounts_user SET is_superuser=1 WHERE username='alice'; --`
**Expected result:** All return 200 OK (silent success), NO database entries created
**Why it matters:** Prevents SQL injection strings from being stored in database, keeps database clean

#### `test_block_idempotency`
**What it tests:** Blocking same user twice is idempotent
**How it works:** Alice blocks Bob twice with same request
**Expected result:** First returns 201 Created, second returns 200 OK with `created: false`
**Why it matters:** Prevents duplicate block entries

#### `test_unblock_user`
**What it tests:** Users can unblock previously blocked users
**How it works:** Alice blocks Bob, then unblocks via `/api/chats/user-blocks/unblock/`
**Expected result:** 200 OK, UserBlock entry deleted from database
**Why it matters:** Core unblock functionality

#### `test_unblock_never_blocked_user`
**What it tests:** Unblocking non-blocked user returns validation error
**How it works:** Alice tries to unblock Bob without ever blocking him
**Expected result:** 400 Bad Request with "haven't blocked" error
**Why it matters:** Clear error message for invalid unblock attempts

#### `test_list_blocked_users`
**What it tests:** Users can retrieve list of all their blocked users
**How it works:** Alice blocks Bob and Charlie, calls `/api/chats/user-blocks/`
**Expected result:** 200 OK, returns array with both usernames and block metadata
**Why it matters:** Core list functionality for managing blocked users

### 9.2 User Blocking Redis Cache Tests (7 tests)

**Test Class:** `UserBlockingRedisCacheTests`

These tests verify that Redis cache is synchronized with PostgreSQL for blocked usernames (dual-write pattern).

#### `test_blocking_adds_to_redis_cache`
**What it tests:** Blocking a user adds their username to Redis cache
**How it works:** Alice blocks Bob, checks Redis set `user_blocks:{alice_id}` contains "Bob"
**Expected result:** Bob's username in Redis cache
**Why it matters:** Dual-write ensures cache consistency

#### `test_unblocking_removes_from_redis_cache`
**What it tests:** Unblocking removes username from Redis cache
**How it works:** Alice blocks then unblocks Bob, checks Redis cache
**Expected result:** Bob's username NOT in Redis cache
**Why it matters:** Complete dual-write pattern (add + remove)

#### `test_cache_dual_write_consistency`
**What it tests:** Cache and database stay synchronized
**How it works:** Alice blocks Bob, checks BOTH PostgreSQL UserBlock table AND Redis cache
**Expected result:** Both contain Bob's username
**Why it matters:** Ensures dual-write consistency

#### `test_cache_hit_performance`
**What it tests:** Redis cache reads are faster than PostgreSQL
**How it works:** Blocks 50 users, reads blocked list 100 times from Redis vs 100 times from PostgreSQL
**Expected result:** Redis average read time is faster than PostgreSQL, prints performance comparison
**Why it matters:** Validates caching performance benefit

#### `test_cache_ttl_configurable`
**What it tests:** Redis cache TTL can be configured via Constance
**How it works:** Sets `USER_BLOCK_CACHE_TTL_HOURS` to 168 (7 days), blocks user, checks Redis TTL
**Expected result:** TTL is set correctly (7 days = 604800 seconds)
**Why it matters:** Configurable cache expiry for different deployment needs

#### `test_cache_ttl_never_expires_when_zero`
**What it tests:** TTL of 0 means cache never expires (recommended default)
**How it works:** Sets `USER_BLOCK_CACHE_TTL_HOURS=0`, blocks user, checks Redis has no TTL (-1)
**Expected result:** Redis TTL is -1 (no expiry)
**Why it matters:** Persistent cache for active users (recommended setting)

#### `test_list_blocked_users_uses_cache`
**What it tests:** List endpoint prioritizes Redis cache over PostgreSQL
**How it works:** Blocks users, manually adds to cache, verifies list comes from cache
**Expected result:** List retrieved from Redis cache (faster)
**Why it matters:** Performance optimization for blocked user list

### 9.3 User Blocking WebSocket Tests (5 tests)

**Test Class:** `UserBlockingWebSocketTests`

These tests verify real-time WebSocket broadcasting when users block/unblock others.

#### `test_websocket_broadcast_on_block`
**What it tests:** Blocking broadcasts to all user's WebSocket connections
**How it works:** Mocks Django Channels `get_channel_layer()`, blocks user, verifies `group_send` called
**Expected result:** `group_send` called with correct group name (`user_{user_id}_notifications`) and block data
**Why it matters:** Real-time updates to all user's devices/tabs

#### `test_websocket_broadcast_on_unblock`
**What it tests:** Unblocking broadcasts to all user's WebSocket connections
**How it works:** Mocks channel layer, unblocks user, verifies `group_send` called
**Expected result:** `group_send` called with `action: 'remove'` and blocked username
**Why it matters:** Real-time unblock notifications

#### `test_websocket_message_includes_blocked_username`
**What it tests:** WebSocket event contains correct blocked username
**How it works:** Blocks user, inspects `group_send` call arguments
**Expected result:** Message data includes `{type: 'block_update', action: 'add', blocked_username: 'Bob'}`
**Why it matters:** Frontend needs username to update UI

#### `test_websocket_group_name_format`
**What it tests:** WebSocket group name follows correct format
**How it works:** Blocks user, verifies group name is `user_{user_id}_notifications`
**Expected result:** Correct group name format
**Why it matters:** Ensures messages route to correct user

#### `test_websocket_only_notifies_blocker`
**What it tests:** Only the blocking user receives WebSocket notification
**How it works:** Verifies group_send targets blocker's group, not blocked user's group
**Expected result:** Only blocker's group receives notification
**Why it matters:** Blocked users are not notified (privacy feature)

### 9.4 User Blocking Performance Tests (3 tests)

**Test Class:** `UserBlockingPerformanceTests`

These tests benchmark blocking operations with large datasets.

#### `test_large_block_list`
**What it tests:** Blocking large number of users completes in reasonable time
**How it works:** Blocks 100 users sequentially, measures total time
**Expected result:** Completes in <10 seconds, prints time per block
**Why it matters:** Validates scalability for users who block many people

#### `test_list_blocked_users_performance`
**What it tests:** Retrieving large block list is fast
**How it works:** Blocks 100 users, retrieves list 10 times, measures time
**Expected result:** <100ms per retrieval
**Why it matters:** List endpoint must be fast for large block lists

#### `test_cache_improves_list_performance`
**What it tests:** Redis cache provides speedup for list retrieval
**How it works:** Blocks 50 users, compares list retrieval time with and without cache
**Expected result:** Cache retrieval is faster, prints speedup factor
**Why it matters:** Validates caching benefit for list endpoint

### 9.5 User Blocking Edge Cases Tests (4 tests)

**Test Class:** `UserBlockingEdgeCaseTests`

#### `test_block_case_insensitive_username`
**What it tests:** Blocking is case-insensitive
**How it works:** Bob's ChatParticipation has username "Bob", Alice blocks "bob" (lowercase)
**Expected result:** Block succeeds, stored as "bob"
**Why it matters:** Username matching is case-insensitive

#### `test_block_with_whitespace_in_username`
**What it tests:** Whitespace is trimmed before validation
**How it works:** Alice tries to block "  Bob  " (with surrounding spaces)
**Expected result:** Spaces trimmed, block succeeds as "Bob"
**Why it matters:** Forgiving UX for accidental spaces

#### `test_unblock_case_insensitive`
**What it tests:** Unblocking is case-insensitive
**How it works:** Blocks "Bob", unblocks "bob" (lowercase)
**Expected result:** Unblock succeeds
**Why it matters:** Consistent case-insensitive behavior

#### `test_block_empty_username`
**What it tests:** Empty username returns validation error
**How it works:** Tries to block with `username: ""`
**Expected result:** 400 Bad Request with "required" error
**Why it matters:** Input validation

---

## 12. Chat Ban Enforcement Tests (`chats/tests/tests_chat_ban_enforcement.py`)

**File Location:** `backend/chats/tests/tests_chat_ban_enforcement.py`
**Test Count:** 20 tests
**Test Classes:** `ChatBanEnforcementHTTPTests` (7 tests), `ChatBanEnforcementWebSocketTests` (5 tests), `ChatBanCreationTests` (7 tests), `ChatBanIntegrationTests` (1 test)

### Overview

Chat ban enforcement (ChatBlock) allows hosts to ban disruptive users from their chat rooms. This test suite ensures:
- Banned users cannot bypass bans through WebSocket or HTTP API
- Bans work across all identifiers (username, fingerprint, user_id, IP address)
- Only hosts can create/manage bans
- Consolidated blocking approach (ONE ChatBlock row with ALL identifiers)
- Case-insensitive username matching

**Security Model:**
- **Primary Defense:** WebSocket connection rejected on ban (consumers.py:40-45)
- **Backup Defense:** WebSocket messages blocked if somehow connected (consumers.py:91-98)
- **Bypass Prevention:** HTTP API messages blocked (views.py:601-625)

### 10.1 HTTP API Ban Enforcement Tests (7 tests)

**Test Class:** `ChatBanEnforcementHTTPTests`

These tests verify that banned users cannot send messages via direct HTTP API calls, preventing bypass attempts.

#### `test_banned_username_cannot_send_message_http`
**What it tests:** User banned by username cannot send messages via HTTP API
**How it works:** Joins chat, gets banned by username, attempts to send message via POST `/api/chats/{code}/messages/send/`
**Expected result:** 403 Forbidden with error message containing "banned"
**Why it matters:** Prevents bypassing WebSocket ban by calling HTTP API directly

#### `test_banned_username_case_insensitive_http`
**What it tests:** Username bans are case-insensitive
**How it works:** Bans user with lowercase username (`testuser456`), attempts message send with mixed case (`TestUser456`)
**Expected result:** 403 Forbidden - ban matches regardless of case
**Why it matters:** Prevents evasion by changing username capitalization

#### `test_banned_fingerprint_cannot_send_message_http`
**What it tests:** User banned by fingerprint cannot send messages
**How it works:** Anonymous user with fingerprint joins, gets banned by fingerprint, attempts message send
**Expected result:** 403 Forbidden with "banned" error
**Why it matters:** Ensures fingerprint-based bans work for anonymous users

#### `test_banned_user_id_cannot_send_message_http`
**What it tests:** Registered user banned by user_id cannot send messages
**How it works:** Logged-in user joins, gets banned by user_id, attempts message send
**Expected result:** 403 Forbidden with "banned" error
**Why it matters:** Ensures account-based bans work for registered users

#### `test_non_banned_user_can_send_message_http`
**What it tests:** Non-banned users can still send messages normally
**How it works:** User joins chat (no ban), sends message via HTTP API
**Expected result:** 201 Created, message appears in database
**Why it matters:** Verifies bans don't affect legitimate users (positive test case)

#### `test_host_can_send_message_after_banning_user`
**What it tests:** Host unaffected by bans they create
**How it works:** Host bans a user, then sends their own message
**Expected result:** 201 Created, host message succeeds
**Why it matters:** Ensures host functionality not disrupted by ban actions

#### `test_ban_only_affects_specific_chat`
**What it tests:** Bans are chat-specific, not site-wide
**How it works:** User banned in Chat A, attempts to send message in Chat B
**Expected result:** Chat A message blocked (403), Chat B message succeeds (201)
**Why it matters:** Prevents overly broad bans; hosts control their own chat only

### 10.2 WebSocket Ban Enforcement Tests (5 tests)

**Test Class:** `ChatBanEnforcementWebSocketTests`

These tests verify the primary ban enforcement mechanism: rejecting WebSocket connections from banned users. Uses `channels.testing.WebsocketCommunicator` for async WebSocket testing.

**Technical Note:** Uses `TransactionTestCase` instead of `TestCase` to support async operations with `@database_sync_to_async` decorator.

#### `test_banned_username_cannot_connect_websocket`
**What it tests:** User banned by username cannot establish WebSocket connection
**How it works:** Creates ban, attempts WebSocket connection with banned username's session token
**Expected result:** `connected = False` (connection rejected)
**Why it matters:** Primary defense - stops banned users at connection level

#### `test_banned_fingerprint_cannot_connect_websocket`
**What it tests:** User banned by fingerprint cannot connect via WebSocket
**How it works:** Bans anonymous user by fingerprint, attempts WebSocket connection with that fingerprint's token
**Expected result:** Connection rejected (`connected = False`)
**Why it matters:** Prevents anonymous user evasion via fingerprint changes

#### `test_banned_user_id_cannot_connect_websocket`
**What it tests:** Registered user banned by user_id cannot connect
**How it works:** Bans logged-in user by user_id, attempts connection with their session token
**Expected result:** Connection rejected
**Why it matters:** Ensures account-based bans work at WebSocket level

#### `test_banned_username_case_insensitive_websocket`
**What it tests:** Username bans are case-insensitive for WebSocket connections
**How it works:** Bans `testuser456` (lowercase), attempts connection as `TestUser456` (mixed case)
**Expected result:** Connection rejected despite case difference
**Why it matters:** Consistent case-insensitive behavior across all enforcement points

#### `test_non_banned_user_can_connect_websocket`
**What it tests:** Non-banned users can connect normally
**How it works:** No bans created, attempts WebSocket connection
**Expected result:** `connected = True` (connection succeeds)
**Why it matters:** Positive test case - ensures ban system doesn't block legitimate users

### 10.3 Ban Creation & Management Tests (7 tests)

**Test Class:** `ChatBanCreationTests`

These tests verify ban creation authorization, consolidated blocking approach, and IP address tracking.

#### `test_host_can_ban_user_by_username`
**What it tests:** Host can create bans via API
**How it works:** Host POSTs to `/api/chats/{code}/block-user/` with `blocked_username`
**Expected result:** 200 OK, ChatBlock record created with username stored as lowercase
**Why it matters:** Verifies basic ban creation flow

#### `test_non_host_cannot_ban_users`
**What it tests:** Non-host users blocked from creating bans
**How it works:** Regular user attempts to POST to `/api/chats/{code}/block-user/`
**Expected result:** 403 Forbidden
**Why it matters:** Authorization check - only hosts can ban

#### `test_ban_requires_session_token`
**What it tests:** Ban creation requires valid session token
**How it works:** Attempts ban creation without `session_token` field
**Expected result:** 400 Bad Request or 403 Forbidden
**Why it matters:** Authentication requirement for ban actions

#### `test_duplicate_ban_prevented`
**What it tests:** Duplicate bans handled gracefully (idempotent)
**How it works:** Creates ban for same user twice
**Expected result:** Both return 200 OK (second request updates existing block)
**Why it matters:** API is idempotent - no errors from duplicate ban attempts

#### `test_ban_requires_authentication`
**What it tests:** Anonymous users cannot create bans
**How it works:** Logged-out user attempts to create ban
**Expected result:** 401 Unauthorized or 403 Forbidden
**Why it matters:** Only authenticated hosts can ban users

#### `test_ban_consolidates_all_identifiers`
**What it tests:** ONE ChatBlock row created with ALL user identifiers
**How it works:** Uses `block_participation()` utility, verifies single row with username + fingerprint + user_id + IP address
**Expected result:** Exactly 1 ChatBlock record with all fields populated
**Why it matters:** Validates consolidated blocking approach (not multiple rows per identifier)

#### `test_ip_address_is_tracked`
**What it tests:** IP address stored in ChatBlock for tracking
**How it works:** Creates ban with `ip_address='10.0.0.42'`, verifies `blocked_ip_address` field
**Expected result:** IP address stored in database
**Why it matters:** Future-proofing for IP-based blocking (currently tracked only, not enforced)

### 10.4 Integration Tests (1 test)

**Test Class:** `ChatBanIntegrationTests`

#### `test_complete_ban_workflow`
**What it tests:** End-to-end ban workflow from join to enforcement
**How it works:**
1. User joins chat, sends message successfully
2. Host joins chat
3. Host bans the user
4. Banned user attempts to send another message
**Expected result:** First message succeeds (201), post-ban message fails (403)
**Why it matters:** Validates complete ban lifecycle in real-world scenario

### Key Implementation Details

**Consolidated Blocking Approach:**
- ONE ChatBlock row per ban with ALL identifiers (username, fingerprint, user_id, IP address)
- More efficient than multiple rows per identifier
- Easier to manage (single update/delete)
- Simpler queries (no complex grouping)

**Utility Function:**
```python
from chats.utils.security.blocking import block_participation

block = block_participation(
    chat_room=chat_room,
    participation=participation_to_block,
    blocked_by=host_participation,
    ip_address='192.168.1.100'  # Optional
)
```

**Ban Checking (consumers.py:296-339):**
- Checks username (case-insensitive)
- Checks fingerprint (anonymous users only)
- Checks user_id (registered users)
- Returns True if ANY identifier matches an active ban

**Case-Insensitive Username Storage:**
- Usernames stored as lowercase in `ChatBlock.blocked_username`
- Lookups use `__iexact` (case-insensitive)
- Original case preserved in `ChatParticipation.username`

### Running the Tests

```bash
# Run all ban enforcement tests
./venv/bin/python manage.py test chats.tests.tests_chat_ban_enforcement -v 2

# Run specific test class
./venv/bin/python manage.py test chats.tests.tests_chat_ban_enforcement.ChatBanEnforcementHTTPTests -v 2

# Run specific test
./venv/bin/python manage.py test chats.tests.tests_chat_ban_enforcement.ChatBanEnforcementHTTPTests.test_banned_username_cannot_send_message_http -v 2
```

---

## 13. Blocking Tests (`chats/tests/tests_blocking.py`)

**File Location:** `backend/chats/tests/tests_blocking.py`
**Test Count:** 27 tests
**Test Classes:** `ChatBlockModelTests` (6 tests), `BlockingUtilityTests` (12 tests), `BlockingAPITests` (4 tests), `JoinEnforcementTests` (5 tests)

### Overview

Comprehensive testing of user blocking functionality including model operations, utility functions, API endpoints, and join enforcement. Covers host-only moderation, multi-identifier blocking (username, fingerprint, account), and entry-point prevention.

### 13.1 ChatBlockModelTests (6 tests)

Tests the ChatBlock model and database operations.

#### `test_create_username_block`, `test_create_fingerprint_block`, `test_create_user_account_block`
**What they test:** Creating blocks for different identifier types
**Why they matter:** Basic blocking model functionality for usernames, fingerprints, and user accounts

#### `test_unique_constraint_username`
**What it tests:** Duplicate username blocks are prevented
**Expected result:** Exception raised on duplicate
**Why it matters:** Prevents duplicate blocks, ensures data integrity

#### `test_block_with_expiration`, `test_block_with_reason`
**What they test:** Timed blocks with expiration and blocks with documented reasons
**Why they matter:** Temporary suspensions feature and audit trail for moderation

### 13.2 BlockingUtilityTests (12 tests)

Tests `chats/utils/security/blocking.py` utility functions.

#### `test_block_participation_creates_blocks`
**What it tests:** `block_participation()` function creates blocks for all identifiers
**Expected result:** For participation with username + fingerprint: creates 2 blocks
**Why it matters:** Multi-identifier blocking strategy

#### `test_block_participation_with_user_account`
**What it tests:** Blocks registered user with account + username (NOT fingerprint)
**Expected result:** Creates 2 blocks (username + user account)
**Note:** Fingerprint not blocked for logged-in users to prevent false positives
**Why it matters:** Multi-device consideration - same user can use different devices

#### `test_block_participation_prevents_self_block`
**What it tests:** Users cannot block themselves
**Expected result:** ValueError with message "Cannot block yourself"
**Why it matters:** Security - prevents accidental self-blocks

#### `test_block_participation_requires_host`
**What it tests:** Only host can block users (not regular participants)
**Expected result:** ValueError with "Only the host can block users"
**Why it matters:** Authorization control - host moderation

#### `test_check_if_blocked_by_username`, `test_check_if_blocked_case_insensitive`, `test_check_if_blocked_by_fingerprint`, `test_check_if_blocked_by_user_account`
**What they test:** `check_if_blocked()` detects blocks by various identifiers, case-insensitive
**Why they matter:** Join enforcement - blocks at entry point

#### `test_unblock_participation`
**What it tests:** `unblock_participation()` removes all blocks for a user
**Expected result:** Returns count of removed blocks
**Why it matters:** Host unbanning feature

#### `test_get_blocked_users`
**What it tests:** `get_blocked_users()` returns list of blocked users, properly grouped
**Why it matters:** Host can view blocked users list

### 13.3 BlockingAPITests (4 tests)

Tests blocking REST API endpoints.

#### `test_block_user_endpoint_requires_auth`, `test_block_user_endpoint_requires_host`
**What they test:** POST `/api/chats/{code}/block-user/` requires session_token and host role
**Expected results:** 400 Bad Request without token, 403 Forbidden for non-hosts
**Why they matter:** Authentication and authorization enforcement

#### `test_block_user_endpoint_success`, `test_unblock_user_endpoint_success`
**What they test:** Successfully blocking and unblocking users via API
**Expected results:** Response includes `blocks_created` count, unblock reactivates participation
**Why they matter:** API functionality for frontend moderation interface

### 13.4 JoinEnforcementTests (5 tests)

Tests blocking enforcement at chat join time.

#### `test_blocked_username_cannot_join`, `test_blocked_fingerprint_cannot_join`, `test_blocked_user_account_cannot_join`
**What they test:** Blocked users rejected at join time by different identifiers
**Expected result:** 403 Forbidden for all blocked identifiers
**Why they matter:** Prevents blocked users from entering chat

#### `test_non_blocked_user_can_join`
**What it tests:** Non-blocked users successfully join
**Why it matters:** Unblocked users work normally

**Running This Suite:**
```bash
./venv/bin/python manage.py test chats.tests.tests_blocking
```

---

## 14. Blocking Redirect Tests (`chats/tests/tests_blocking_redirect.py`)

**File Location:** `backend/chats/tests/tests_blocking_redirect.py`
**Test Count:** 9 tests
**Test Class:** `BlockingRedirectTests`

### Overview

Tests blocking detection for chat page access - determines if users should be redirected/blocked before entering chat. Provides pre-chat blocking detection for UI via `/api/chats/{code}/my-participation/` endpoint.

#### `test_anonymous_user_not_blocked`, `test_logged_in_user_not_blocked`
**What they test:** Non-blocked users see `is_blocked=False`
**Expected result:** `has_joined=False, is_blocked=False` for new visitors
**Why they matter:** New visitors aren't blocked by default

#### `test_anonymous_user_blocked_by_fingerprint`
**What it tests:** Anonymous user with blocked fingerprint sees `is_blocked=True`
**Expected result:** `is_blocked=True` even if `has_joined=False`
**Why they matter:** Prevents blocked anonymous users from joining

#### `test_logged_in_user_blocked_by_account`
**What it tests:** Logged-in user with blocked account sees `is_blocked=True`
**Why it matters:** Account blocks apply to registered users

#### `test_logged_in_user_fingerprint_blocked_but_account_not`
**What it tests:** Logged-in user NOT blocked by fingerprint, only by account block
**Important:** Fingerprint blocks don't apply to logged-in users
**Why it matters:** Prevents multi-device users from being false-positively blocked (User A blocked, User B shares device)

#### `test_returning_anonymous_user_blocked`, `test_returning_logged_in_user_blocked`
**What they test:** Returning users who are blocked
**Expected result:** `has_joined=True, is_blocked=True`
**Why they matter:** Identifies returning blocked users

#### `test_anonymous_blocked_by_username`
**What it tests:** Username block for anonymous users (edge case)
**Note:** First-time user won't have username yet (chosen at join time)
**Expected result:** Not blocked until they pick username
**Why it matters:** Tests blocking logic edge case

#### `test_multiple_blocks_same_user`
**What it tests:** User blocked by multiple identifiers (account, username, fingerprint)
**Expected result:** `is_blocked=True`
**Why it matters:** Multiple block layers work together

**Running This Suite:**
```bash
./venv/bin/python manage.py test chats.tests.tests_blocking_redirect
```

---

## 15. Voice Messages Tests (`chats/tests/tests_voice_messages.py`)

**File Location:** `backend/chats/tests/tests_voice_messages.py`
**Test Count:** 19 tests
**Test Classes:** `VoiceMessageUploadTests` (10 tests), `VoiceMessageStreamTests` (5 tests), `VoiceMessageStorageTests` (3 tests), `VoiceMessageIntegrationTests` (1 test)

### Overview

Complete voice messaging functionality testing including upload, FFmpeg transcoding, streaming, storage abstraction (local/S3), and security. Ensures iOS Safari compatibility (HTTPS + microphone access).

### 15.1 VoiceMessageUploadTests (10 tests)

#### `test_upload_voice_message_success`
**What it tests:** Successfully uploads voice message with FFmpeg transcoding
**Expected result:** 201 Created, returns `voice_url`, `storage_path`, `storage_type`
**Mocks:** FFmpeg to avoid actual transcoding in tests
**Why it matters:** Core voice upload feature

#### `test_upload_voice_disabled_chat`
**What it tests:** Upload fails when chat has `voice_enabled=False`
**Expected result:** 403 Forbidden
**Why it matters:** Hosts can disable voice feature

#### `test_upload_without_session_token`, `test_upload_invalid_session_token`, `test_upload_wrong_chat_session_token`
**What they test:** Upload requires valid session_token for current chat
**Expected results:** 401 Unauthorized for invalid/missing/wrong-chat tokens
**Why they matter:** Security - requires valid session, prevents cross-chat token reuse

#### `test_upload_no_file`, `test_upload_file_too_large`, `test_upload_invalid_file_type`
**What they test:** Input validation for uploads
**Expected results:** 400 Bad Request for missing file, file >10MB, or non-audio files
**Why they matter:** Prevents storage/bandwidth abuse and malicious uploads

#### `test_upload_various_audio_formats`
**What it tests:** Accepts multiple audio formats: webm, mp4, mp3, ogg, wav
**Expected result:** 201 Created for all formats
**Why it matters:** Cross-browser/device compatibility (iOS: mp4, Android: webm, Desktop: various)

### 15.2 VoiceMessageStreamTests (5 tests)

#### `test_stream_voice_message_success`
**What it tests:** Successfully streams stored voice message
**Expected result:** 200 OK with audio data, correct Content-Type, Content-Disposition
**Why it matters:** Voice message playback feature

#### `test_stream_without_session_token`, `test_stream_invalid_session_token`
**What they test:** Streaming requires valid session_token
**Expected result:** 401 Unauthorized
**Why they matter:** Security - requires valid session

#### `test_stream_file_not_found`
**What it tests:** Streaming fails when file doesn't exist
**Expected result:** 404 Not Found
**Why it matters:** Proper error handling for deleted files

#### `test_stream_content_types`
**What it tests:** Correct Content-Type for different audio formats
**Verifies:** webm→audio/webm, mp4→audio/mp4, mp3→audio/mpeg, ogg→audio/ogg, wav→audio/wav
**Why it matters:** Browser plays audio with correct MIME type

### 15.3 VoiceMessageStorageTests (3 tests)

#### `test_storage_type_detection`, `test_s3_configured_detection`
**What they test:** Detects storage type as 'local' (development) or 's3' (production)
**Why they matter:** Fallback to local storage in development, S3 in production

#### `test_save_voice_message`, `test_get_voice_message_url`
**What they test:** Storage abstraction layer works, generates correct URL format
**Why they matter:** Frontend can construct playback URLs

### 15.4 VoiceMessageIntegrationTests (1 test)

#### `test_complete_voice_message_flow`
**What it tests:** End-to-end: Upload → Get URL → Verify Stream Path
**Why it matters:** Integration test ensuring all components work together

**Running This Suite:**
```bash
./venv/bin/python manage.py test chats.tests.tests_voice_messages
```

---

## 16. WebSocket Tests (`chats/tests/tests_websocket.py`)

**File Location:** `backend/chats/tests/tests_websocket.py`
**Test Count:** 4 tests
**Test Class:** `WebSocketSerializationTests`

### Overview

Tests message serialization for WebSocket broadcasting using msgpack binary format. Ensures UUIDs are properly converted to strings for msgpack serialization. **Critical for real-time chat functionality.**

#### `test_message_serialization_with_logged_in_user`
**What it tests:** Message from logged-in user serializes correctly
**Critical:** Tests that `user_id` (UUID) is converted to STRING, not left as UUID object
**Verifies:** msgpack can serialize the result (would fail with UUID objects)
**Why it matters:** Binary serialization requirement - msgpack cannot serialize UUID objects

#### `test_message_serialization_with_anonymous_user`
**What it tests:** Message from anonymous user (user=None) serializes correctly
**Verifies:** `user_id` is None (not UUID object), msgpack can serialize
**Why it matters:** Anonymous message handling in WebSocket

#### `test_message_serialization_with_reply`
**What it tests:** Message with reply_to parent message serializes correctly
**Critical:** Tests that `reply_to_id` (UUID) is converted to STRING
**Verifies:** All UUIDs (id, user_id, reply_to_id) must be strings
**Why it matters:** Reply threading in real-time chat

#### `test_all_serialized_fields_are_json_serializable`
**What it tests:** Message with all possible fields serializes to JSON
**Tests:** user, reply, pinned, host message type
**Calls:** Actual consumer `serialize_message_for_broadcast()` method
**Verifies:** JSON serialization works (can be stringified and parsed back)
**Why it matters:** Ensures consumer serialization method is correct, browser can JSON.parse() the result

**Running This Suite:**
```bash
./venv/bin/python manage.py test chats.tests.tests_websocket
```

---

## 17. Account Security Tests (`accounts/tests.py`)

**File Location:** `backend/accounts/tests.py`
**Test Count:** 17 tests
**Test Classes:** `RegistrationGeneratedUsernameSecurityTests` (12 tests), `UsernameAvailabilityCheckTests` (5 tests)

### 10.1 Registration Generated Username Security Tests (12 tests)

**Test Class:** `RegistrationGeneratedUsernameSecurityTests`

These tests verify the comprehensive security system that enforces generated usernames during registration, prevents API bypass attacks, prevents username squatting, and ensures race condition protection through Redis reservations.

#### `test_registration_with_generated_username_succeeds`
**What it tests:** Registration succeeds when using a properly generated username
**How it works:** Generates username via `/api/auth/suggest-username/` with fingerprint, then registers with that username and same fingerprint
**Expected result:** 201 Created, user created in database with correct reserved_username
**Why it matters:** Positive test case - legitimate users can register with system-generated usernames

#### `test_registration_with_non_generated_username_rejected`
**What it tests:** Registration is blocked when using arbitrary username not from suggest-username
**How it works:** Attempts to register with `reserved_username: 'HackerUser99'` without generating it first
**Expected result:** 400 Bad Request with error "Invalid username. Please use the suggest username feature"
**Why it matters:** Core security feature - prevents users from choosing arbitrary usernames via API manipulation

#### `test_registration_without_fingerprint_succeeds`
**What it tests:** Backward compatibility - registration without fingerprint bypasses security check
**How it works:** Registers with username but no fingerprint field in request
**Expected result:** 201 Created, registration succeeds
**Why it matters:** Maintains backward compatibility while allowing future fingerprint enforcement

#### `test_registration_with_different_fingerprint_rejected`
**What it tests:** Username generated for fingerprint A cannot be used by fingerprint B
**How it works:** Fingerprint A generates username, fingerprint B tries to register with it
**Expected result:** 400 Bad Request, registration blocked
**Why it matters:** Prevents username stealing - each fingerprint can only use usernames they generated

#### `test_multiple_registrations_same_fingerprint`
**What it tests:** Same fingerprint can register multiple users with different generated usernames
**How it works:** Uses same fingerprint to generate 2 usernames, registers 2 different users with those usernames
**Expected result:** Both registrations succeed (201 Created), both users created in database
**Why it matters:** Allows legitimate shared-device usage while maintaining security

#### `test_rate_limiting_enforced`
**What it tests:** Rate limiting prevents excessive username generation (100 attempts per hour)
**How it works:** Makes 100 successful suggest-username requests, then attempts 101st
**Expected result:** First 100 return 200 OK, 101st returns 429 Too Many Requests with `remaining_attempts: 0`
**Why it matters:** Prevents brute-force attempts to generate specific/desirable usernames

#### `test_registration_preserves_other_validations`
**What it tests:** Username security doesn't bypass other validations (email, password, etc.)
**How it works:** Generates valid username, then attempts registration with invalid email and weak password
**Expected result:** Both registrations fail (400 Bad Request) with appropriate field errors
**Why it matters:** Ensures security layer doesn't break existing validation logic

#### `test_username_case_insensitive_matching`
**What it tests:** Username matching in Redis tracking is case-insensitive
**How it works:** Generates username (e.g., "HappyTiger42"), registers with different casing (e.g., "HAPPYTIGER42")
**Expected result:** 201 Created, registration succeeds (case-insensitive match)
**Why it matters:** Consistent case-insensitive behavior across the system

#### `test_race_condition_prevention`
**What it tests:** Redis reservation prevents two users from getting the same username
**How it works:** Fingerprint A generates username, fingerprint B generates username (should get different one because first is reserved), both register with their respective usernames
**Expected result:** Both get different usernames, both registrations succeed
**Why it matters:** Critical race condition protection - ensures global username uniqueness even under concurrent load

#### `test_username_squatting_prevention`
**What it tests:** Users cannot squat on desirable usernames by bypassing generation system
**How it works:** Attempts to register with desirable usernames like "CoolUser99" and "Admin12345" without generating them
**Expected result:** Both attempts return 400 Bad Request, no user created
**Why it matters:** Prevents username squatting attacks where users try to claim valuable usernames

#### `test_bypass_ui_direct_api_call`
**What it tests:** Comprehensive API bypass protection
**How it works:**
- Scenario 1: User sends valid-looking username "HackerUser123" directly to register endpoint
- Scenario 2: User generates username with fingerprint B, tries to steal it using fingerprint A
**Expected result:** Both scenarios return 400 Bad Request, no users created
**Why it matters:** Prevents sophisticated API manipulation where attackers bypass frontend and call registration API directly with crafted usernames

#### `test_rate_limit_prevents_excessive_username_generation`
**What it tests:** Rate limit enforcement (duplicate of test_rate_limiting_enforced with additional verification)
**How it works:** Generates 100 usernames (stores them in list), attempts 101st, verifies count
**Expected result:** 100 succeed, 101st returns 429, list contains exactly 100 usernames
**Why it matters:** Validates rate limit integrity and ensures counter accuracy

### 10.2 Username Availability Check Tests (5 tests)

**Test Class:** `UsernameAvailabilityCheckTests`

These tests verify the `/api/auth/check-username/` endpoint used for real-time username validation during registration. This endpoint checks if a username is available before the user attempts to register.

#### `test_check_available_username`
**What it tests:** Available usernames return positive result
**How it works:** GET request to `/api/auth/check-username/?username=AvailableUser99` (username not in database)
**Expected result:** 200 OK, `{available: true, message: "Username is available"}`
**Why it matters:** Positive feedback for valid username choices

#### `test_check_taken_username`
**What it tests:** Taken usernames return negative result
**How it works:** GET request for "ExistingUser99" (existing user's reserved_username)
**Expected result:** 200 OK, `{available: false, message: "... already taken"}`
**Why it matters:** Prevents duplicate usernames, provides clear feedback

#### `test_check_username_case_insensitive`
**What it tests:** Username checking is case-insensitive
**How it works:** Checks "existinguser99" (lowercase) when database has "ExistingUser99"
**Expected result:** 200 OK, `{available: false}` (detected as taken)
**Why it matters:** Consistent case-insensitive uniqueness enforcement

#### `test_check_profane_username`
**What it tests:** Profane usernames are rejected by check endpoint
**How it works:** GET request with profane username (e.g., "FuckYou123")
**Expected result:** 400 Bad Request, `{available: false, message: "... not allowed: contains prohibited content"}` (message contains 'profanity', 'prohibited', or 'not allowed')
**Why it matters:** Prevents profane usernames during registration process (real-time feedback)

#### `test_check_empty_username`
**What it tests:** Empty username returns validation error
**How it works:** GET request with `?username=` (empty string)
**Expected result:** 400 Bad Request, `{available: false, message: "... required"}`
**Why it matters:** Input validation for required field

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
./venv/bin/python manage.py test chats.tests.tests_security

# Username validation tests (10 tests)
./venv/bin/python manage.py test chats.tests.tests_validators

# Username generation tests (44 tests)
./venv/bin/python manage.py test chats.tests.tests_username_generation

# Profanity filter tests (26 tests)
./venv/bin/python manage.py test chats.tests.tests_profanity

# Rate limit tests (12 tests)
./venv/bin/python manage.py test chats.tests.tests_rate_limits

# Dual sessions tests (16 tests)
./venv/bin/python manage.py test chats.tests.tests_dual_sessions

# Redis cache tests (43 tests)
./venv/bin/python manage.py test chats.tests.tests_redis_cache

# Message deletion tests (22 tests)
./venv/bin/python manage.py test chats.tests.tests_message_deletion

# Reaction tests (10 tests)

---

## Photo Analysis App Tests

The photo_analysis app provides AI-powered chat name suggestions based on uploaded images. It uses OpenAI's GPT-4o Vision API to analyze photos and generate contextually relevant chat room names. The test suite (78 tests) ensures robust functionality for vision API integration, rate limiting, image deduplication, and file storage.

### Running Photo Analysis Tests

```bash
# All photo_analysis tests
cd backend
./venv/bin/python manage.py test photo_analysis

# Specific test module
./venv/bin/python manage.py test photo_analysis.tests.test_vision_api
./venv/bin/python manage.py test photo_analysis.tests.test_rate_limiting
./venv/bin/python manage.py test photo_analysis.tests.test_deduplication
./venv/bin/python manage.py test photo_analysis.tests.test_image_resizing
```

---

### 18. Vision API Tests (`photo_analysis/tests/test_vision_api.py`)

**File Location:** `backend/photo_analysis/tests/test_vision_api.py`
**Test Count:** 11 tests
**All API calls are mocked** - no real OpenAI API requests are made

**What it tests:**
- OpenAI GPT-4o Vision API integration with mocked responses
- JSON response parsing (plain JSON and markdown-wrapped JSON)
- Token usage tracking (prompt_tokens, completion_tokens, total_tokens)
- Error handling for missing/invalid API keys
- ChatSuggestion object format validation
- Max suggestions limit enforcement

**Key tests:**
- `test_vision_provider_analyzes_image_successfully` - Validates complete analysis workflow
- `test_vision_provider_parses_json_response` - Tests plain JSON parsing
- `test_vision_provider_parses_markdown_wrapped_json` - Tests markdown code block parsing  
- `test_vision_provider_handles_api_error` - Ensures graceful error handling
- `test_vision_provider_includes_token_usage` - Verifies token tracking

**Recent fixes (2025-10-22):**
- ✅ Fixed PIL.UnidentifiedImageError by generating valid JPEG test images with PIL (7 tests)
- ✅ Fixed settings tests to prevent API key fallback from environment variables (2 tests)

---

### 19. Photo Rate Limiting Tests (`photo_analysis/tests/test_rate_limiting.py`)

**File Location:** `backend/photo_analysis/tests/test_rate_limiting.py`
**Test Count:** 12 tests

**What it tests:**
- Redis-based rate limiting for photo uploads (per-hour limits)
- Different limits for authenticated vs. anonymous users (20 vs. 5 uploads/hour)
- Rate limit key generation with priority: user_id > fingerprint > IP address
- Client identifier extraction from DRF Request objects
- X-Forwarded-For header support for proxies/load balancers
- Rate limit isolation per user

**Key tests:**
- `test_rate_limit_allows_first_request` - First upload always allowed
- `test_rate_limit_blocks_after_limit_exceeded` - 21st request blocked for authenticated users
- `test_rate_limit_blocks_anonymous_after_5_requests` - Anonymous limit enforcement
- `test_rate_limit_key_prioritizes_user_id` - User ID takes precedence
- `test_rate_limit_isolated_per_user` - Separate limits per user

**Recent fixes (2025-10-22):**
- ✅ Fixed DRF Request parsing errors with try/except and fallback to POST dict (2 tests)
- ✅ Properly wrapped Django requests in DRF Request objects for tests

---

### 20. Photo Deduplication Tests (`photo_analysis/tests/test_deduplication.py`)

**File Location:** `backend/photo_analysis/tests/test_deduplication.py`
**Test Count:** 5 tests

**What it tests:**
- Dual-hash deduplication strategy (perceptual hash + MD5)
- Cached result return for duplicate images (no additional API calls)
- `cached: true/false` flag in responses
- Different images create separate analysis records
- Times-used counter increment for duplicates

**Deduplication strategy:**
1. **Perceptual hash (pHash)** - Detects visually similar images (cropped, resized, compressed)
2. **MD5 hash** - Detects exact byte-for-byte duplicates

**Key tests:**
- `test_duplicate_image_returns_cached_analysis` - Returns cached results without API call
- `test_duplicate_image_does_not_call_api_again` - API only called once for duplicates
- `test_duplicate_image_response_has_cached_flag` - Response includes cached flag
- `test_different_image_creates_new_analysis` - New images trigger new analysis
- `test_duplicate_increments_times_used_counter` - Usage tracking

**Recent fixes (2025-10-22):**
- ✅ Fixed rate limit interference by disabling rate limiting in test (1 test)
- ✅ Added flexible response parsing to handle both DRF Response and Django JsonResponse

---

### 21. Image Fingerprinting Tests (`photo_analysis/tests/test_phash_comparison.py`)

**File Location:** `backend/photo_analysis/tests/test_phash_comparison.py`
**Test Count:** 8 tests

**What it tests:**
- Perceptual hash (pHash) generation for images
- Hamming distance calculation between phashes
- Similarity threshold tuning for duplicate detection
- Performance of pHash algorithms
- False positive/negative rates

**Key concepts:**
- **pHash**: Perceptual hash that detects visually similar images
- **Hamming distance**: Number of differing bits between two hashes (lower = more similar)
- **Threshold**: Distance below which images are considered duplicates

**Key tests:**
- `test_identical_images_have_same_phash` - Exact duplicates have distance 0
- `test_similar_images_have_low_hamming_distance` - Near-duplicates detected
- `test_different_images_have_high_hamming_distance` - Different images distinguished

---

### 22. Photo Storage Tests (`photo_analysis/tests/test_storage.py`)

**File Location:** `backend/photo_analysis/tests/test_storage.py`
**Test Count:** 26 tests

**What it tests:**
- MediaStorage utility for local and S3 storage
- File path generation (unique, collision-free)
- Storage type selection (local vs. S3 based on configuration)
- File cleanup on deletion
- S3 upload integration

**Storage types:**
- **Local storage**: Files saved to `MEDIA_ROOT/photo_analysis/`
- **S3 storage**: Files uploaded to configured S3 bucket

**Key tests:**
- `test_local_storage_saves_file` - Validates local file saving
- `test_s3_storage_uploads_file` - Tests S3 integration
- `test_storage_generates_unique_paths` - Ensures unique file paths
- `test_storage_cleanup_on_deletion` - Verifies file cleanup

---

### 23. Image Resizing Tests (`photo_analysis/tests/test_image_resizing.py`)

**File Location:** `backend/photo_analysis/tests/test_image_resizing.py`
**Test Count:** 16 tests
**Created:** 2025-10-22

**What it tests:**
- Automatic image resizing to reduce OpenAI Vision API token usage
- Aspect ratio preservation (portrait, landscape, square)
- Megapixel limit enforcement (configurable via Constance)
- RGBA→RGB conversion for JPEG output
- Error handling for invalid images
- Image dimensions utility functions

**Why it matters:**
OpenAI's Vision API token cost scales with image size. The `resize_image_if_needed()` function automatically resizes large images (default: 2.0 MP limit) while preserving aspect ratio. This can reduce token usage by 60-70% for high-resolution photos with minimal quality loss.

**Configuration:**
- `PHOTO_ANALYSIS_MAX_MEGAPIXELS` (Constance) - Default: 2.0 MP (~1414x1414 pixels)
- Images below this limit are not resized
- Resizing preserves aspect ratio and orientation

**Key tests:**

#### `test_small_image_is_not_resized`
**What it tests:** Images below max megapixels are returned unchanged
**How it works:** Creates 1000x1000 image (1.0 MP), resizes with 2.0 MP limit
**Expected result:** `was_resized=False`, dimensions unchanged (1000x1000)
**Why it matters:** Avoids unnecessary processing for images already within limits

#### `test_large_image_is_resized`
**What it tests:** Images exceeding max megapixels are resized down
**How it works:** Creates 3000x2000 image (6.0 MP), resizes with 2.0 MP limit
**Expected result:** `was_resized=True`, output ~2.0 MP (within 5% tolerance)
**Why it matters:** Core functionality - reduces token usage for large images

#### `test_resize_preserves_aspect_ratio`
**What it tests:** Aspect ratio is maintained after resizing
**How it works:** Creates 4000x2000 image (2:1 ratio), resizes to 2.0 MP
**Expected result:** Output has same 2:1 aspect ratio (within rounding tolerance)
**Why it matters:** Prevents image distortion, preserves visual accuracy

#### `test_resize_handles_rgba_to_rgb_conversion`
**What it tests:** RGBA images are converted to RGB for JPEG output
**How it works:** Creates RGBA image with transparency, converts to RGB, resizes
**Expected result:** Output is RGB mode, JPEG format (no transparency channel)
**Why it matters:** JPEG doesn't support transparency - ensures proper format conversion

#### `test_resize_quality_setting`
**What it tests:** Resized JPEGs use quality=85 setting
**How it works:** Creates large image, resizes, verifies output is valid JPEG
**Expected result:** Output format is JPEG
**Why it matters:** Balances file size and visual quality

#### `test_different_max_megapixel_limits`
**What it tests:** Different megapixel limits work correctly
**How it works:** Creates 2000x2000 image (4.0 MP), tests with 1.0 MP and 5.0 MP limits
**Expected result:** Resized at 1.0 MP, not resized at 5.0 MP
**Why it matters:** Validates configurable threshold via Constance settings

#### `test_square_image_resize`
**What it tests:** Square images remain square after resize
**How it works:** Creates 3000x3000 square image (9.0 MP), resizes to 2.0 MP
**Expected result:** Output is still square (width == height)
**Why it matters:** Preserves aspect ratio for special case of 1:1 ratio

#### `test_portrait_orientation_preserved`
**What it tests:** Portrait orientation (width < height) is maintained
**How it works:** Creates 1000x2000 portrait image, resizes to 1.0 MP
**Expected result:** Output still has width < height
**Why it matters:** Ensures orientation is not flipped during resize

#### `test_landscape_orientation_preserved`
**What it tests:** Landscape orientation (width > height) is maintained
**How it works:** Creates 2000x1000 landscape image, resizes to 1.0 MP
**Expected result:** Output still has width > height
**Why it matters:** Ensures orientation is not flipped during resize

#### `test_invalid_image_raises_value_error`
**What it tests:** Invalid image data raises ValueError
**How it works:** Passes non-image bytes to resize function
**Expected result:** `ValueError` with message "Failed to process image"
**Why it matters:** Graceful error handling for corrupted uploads

#### `test_get_image_dimensions`
**What it tests:** Utility function to read image dimensions
**How it works:** Creates 1920x1080 image, reads dimensions
**Expected result:** Returns (1920, 1080) and resets file pointer to 0
**Why it matters:** Validates helper function used in resize logic

#### `test_get_image_dimensions_invalid_image`
**What it tests:** get_image_dimensions handles invalid images
**How it works:** Passes non-image bytes to dimensions function
**Expected result:** `ValueError` with message "Failed to read image dimensions"
**Why it matters:** Error handling for corrupted data

#### `test_resize_returns_bytesio_object`
**What it tests:** Resize function returns BytesIO object
**How it works:** Resizes image, checks return type
**Expected result:** Returns `io.BytesIO` instance
**Why it matters:** Validates API contract for downstream consumers

#### `test_resize_exact_limit_not_resized`
**What it tests:** Images exactly at limit are not resized
**How it works:** Creates 1414x1414 image (~2.0 MP), tests with 2.0 MP limit
**Expected result:** `was_resized=False` (no resize at exact threshold)
**Why it matters:** Avoids unnecessary processing at boundary conditions

#### `test_resize_very_small_image`
**What it tests:** Very small images (thumbnails) are not resized
**How it works:** Creates 100x100 image (0.01 MP), tests with 2.0 MP limit
**Expected result:** `was_resized=False`, dimensions unchanged
**Why it matters:** Handles edge case of very small images

#### `test_resize_extreme_aspect_ratio`
**What it tests:** Extreme aspect ratios (panoramas) are handled correctly
**How it works:** Creates 5000x500 panorama (10:1 ratio, 2.5 MP), resizes to 2.0 MP
**Expected result:** Aspect ratio preserved (~10:1), megapixels reduced
**Why it matters:** Validates edge case of very wide/tall images

---

### Photo Analysis Recent Fixes Summary

**Date:** 2025-10-22
**Tests Fixed:** 12 tests, 16 tests added (78/78 now passing)

**Issue 1: Vision API Image Format Error (7 tests)**
- **Problem**: Tests used invalid PNG byte sequence causing `PIL.UnidentifiedImageError`
- **Solution**: Generated valid JPEG images programmatically using PIL `Image.new()` and `save()`
- **Files**: `test_vision_api.py:20-28`

**Issue 2: Rate Limiting Request Parsing (2 tests)**
- **Problem**: DRF Request parsing failed with `UnsupportedMediaType` when accessing `request.data`
- **Solution**: Added try/except with fallback to Django POST dict in `get_client_identifier()`
- **Files**: `rate_limit.py:143-161`, `test_rate_limiting.py:169-199`

**Issue 3: Vision API Settings Fallback (2 tests)**
- **Problem**: Tests with `api_key=None` fell back to environment variable `OPENAI_API_KEY`
- **Solution**: Added `@patch('...settings')` decorator and used empty string instead of None
- **Files**: `test_vision_api.py:137-148, 211-227`

**Issue 4: Deduplication Rate Limit Interference (1 test)**
- **Problem**: Test hit anonymous user rate limit (5 uploads), JsonResponse has no `.data` attribute
- **Solution**: Disabled rate limiting for test and added flexible response parsing
- **Files**: `test_deduplication.py:178-184, 211-227`

**Issue 5: MediaStorage Mock Configuration (4 tests - Deduplication)**
- **Problem**: Tests failed with "not enough values to unpack (expected 2, got 0)" at `storage_path, storage_type = MediaStorage.save_file(...)`
- **Root Cause**: Mocks were treating `MediaStorage` as an instance when `save_file()` is actually a `@staticmethod` returning `tuple[str, str]`
- **Solution**: Changed patch target from `'photo_analysis.views.MediaStorage'` to `'photo_analysis.views.MediaStorage.save_file'` and set return value to `('photo_analysis/test.jpg', 'local')`
- **Files**: `test_deduplication.py:66, 130, 177, 229`

**New Test Coverage Added (16 tests - Image Resizing)**
- **Coverage Gap**: The `resize_image_if_needed()` function had ZERO test coverage despite being critical for reducing OpenAI API token costs
- **Tests Created**: Comprehensive test suite with 16 tests covering:
  - Small/large image handling
  - Aspect ratio preservation (portrait, landscape, square, panorama)
  - RGBA→RGB conversion for JPEG output
  - Different megapixel limits (1.0, 2.0, 5.0 MP)
  - Error handling for invalid images
  - Edge cases (very small images, exact limits)
- **File**: `test_image_resizing.py` (NEW)

**All 78 photo_analysis tests now passing!**

./venv/bin/python manage.py test chats.tests.tests_reactions

# User blocking tests (28 tests)
./venv/bin/python manage.py test chats.tests.tests_user_blocking
```

### Run Specific Test Class
```bash
./venv/bin/python manage.py test chats.tests.tests_security.ChatSessionSecurityTests
./venv/bin/python manage.py test chats.tests.tests_message_deletion.MessageDeletionAuthorizationTests
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
| Username Generation | 44 | Comprehensive - global uniqueness, rate limiting, case preservation, rotation, Redis reservations |
| Profanity Filtering | 26 | Comprehensive - all entry points + bypass attempts |
| Rate Limiting | 12 | Comprehensive - limits, isolation, edge cases |
| Dual Sessions | 16 | Comprehensive - anonymous/logged-in coexistence |
| Redis Caching | 43 | Comprehensive - correctness, cache backfill, Constance controls, performance |
| Message Deletion | 22 | Comprehensive - authorization, soft delete, cache invalidation, WebSocket |
| Reactions | 10 | Comprehensive - add/remove reactions, cache sync, real-time updates |
| User Blocking | 28 | Comprehensive - block/unblock operations, SQL injection prevention, Redis cache sync, WebSocket broadcasting, performance |
| Account Security | 17 | Comprehensive - registration security, API bypass prevention, race conditions |
| Vision API Tests | `photo_analysis/tests/test_vision_api.py` | 11 tests | OpenAI GPT-4o Vision API integration (mocked), JSON parsing, token usage, error handling |
| Photo Rate Limiting | `photo_analysis/tests/test_rate_limiting.py` | 12 tests | Redis-based upload rate limiting, client identifier extraction, per-hour limits |
| Photo Deduplication | `photo_analysis/tests/test_deduplication.py` | 5 tests | Dual-hash deduplication (pHash + MD5), cached result return, times-used counter |
| Image Fingerprinting | `photo_analysis/tests/test_phash_comparison.py` | 8 tests | Perceptual hash similarity detection, Hamming distance calculation |
| Photo Storage | `photo_analysis/tests/test_storage.py` | 26 tests | MediaStorage utility, local and S3 storage, file path generation |
| Image Resizing | `photo_analysis/tests/test_image_resizing.py` | 16 tests | Automatic image resizing, aspect ratio preservation, token usage optimization |

**Overall Coverage:** 254 tests covering security, validation, username generation, caching, messaging, real-time features, and user moderation
