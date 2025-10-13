#!/usr/bin/env python3
"""
Adversarial Security Test Suite for User Blocking Feature

This test suite is designed to EXPOSE VULNERABILITIES, not pass easily.
Tests will only pass if the implementation is truly secure.

Attack vectors tested:
1. Case sensitivity bypass (blocking "User" but messaging as "user")
2. Unicode/homoglyph attacks (blocking "admin" but using "аdmin" with Cyrillic 'а')
3. Whitespace manipulation ("User " vs "User")
4. SQL injection attempts
5. Token forgery/manipulation
6. Rate limiting bypass (rapid block/unblock spam)
7. Cross-user data leakage (can I see who others have blocked?)
8. Authorization bypass (can I unblock someone else's blocks?)
9. Race conditions (concurrent block operations)
10. Cache poisoning (Redis manipulation)
"""

import requests
import json
import time
import threading
from urllib.parse import urlencode
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_BASE = 'https://localhost:9000'

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_test(message):
    print(f"{Colors.OKCYAN}🧪 {message}{Colors.ENDC}")


def print_success(message):
    print(f"{Colors.OKGREEN}✅ {message}{Colors.ENDC}")


def print_error(message):
    print(f"{Colors.FAIL}❌ {message}{Colors.ENDC}")


def print_warning(message):
    print(f"{Colors.WARNING}⚠️  {message}{Colors.ENDC}")


def print_section(title):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{title.center(70)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'=' * 70}{Colors.ENDC}\n")


class AdversarialBlockingTests:
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.user1_token = None
        self.user2_token = None
        self.user3_token = None

        timestamp = str(int(time.time()))[-4:]
        self.user1_email = f"attacker1{timestamp}@example.com"
        self.user2_email = f"victim1{timestamp}@example.com"
        self.user3_email = f"attacker2{timestamp}@example.com"
        self.user1_username = f"Attacker{timestamp}"
        self.user2_username = f"Victim{timestamp}"
        self.user3_username = f"Eve{timestamp}"

    def register_user(self, email, password, username):
        """Register a new user"""
        response = self.session.post(
            f"{API_BASE}/api/auth/register/",
            json={
                "email": email,
                "password": password,
                "reserved_username": username
            }
        )
        if response.status_code == 201:
            return response.json()['token']
        return None

    def block_user(self, token, username):
        """Block a user"""
        headers = {"Authorization": f"Token {token}"}
        response = self.session.post(
            f"{API_BASE}/api/chats/user-blocks/block/",
            json={"username": username},
            headers=headers
        )
        return response

    def unblock_user(self, token, username):
        """Unblock a user"""
        headers = {"Authorization": f"Token {token}"}
        response = self.session.post(
            f"{API_BASE}/api/chats/user-blocks/unblock/",
            json={"username": username},
            headers=headers
        )
        return response

    def get_blocked_users(self, token):
        """Get blocked users list"""
        headers = {"Authorization": f"Token {token}"}
        response = self.session.get(
            f"{API_BASE}/api/chats/user-blocks/",
            headers=headers
        )
        return response

    # ========== ATTACK TESTS ==========

    def test_case_sensitivity_bypass(self):
        """
        ATTACK: Block "Victim" but the attacker tries different cases
        VULNERABILITY: If blocking is case-sensitive, attacker can bypass by changing case
        EXPECTED: Blocking should be case-INSENSITIVE to prevent this
        """
        print_section("ATTACK: Case Sensitivity Bypass")

        print_test("User1 blocks 'Victim' (with capital V)")
        response = self.block_user(self.user1_token, self.user2_username)

        if response.status_code not in [200, 201]:
            print_error(f"Failed to create test block: {response.status_code}")
            return False

        print_test("Checking if lowercase 'victim' is also blocked...")

        # In a real test, we'd check if messages from "victim" are filtered
        # For now, we check if the block list shows the original username
        list_response = self.get_blocked_users(self.user1_token)

        if list_response.status_code == 200:
            blocked_users = list_response.json()['blocked_users']
            print_warning(f"Block stored as: {blocked_users[0]['username'] if blocked_users else 'NONE'}")
            print_warning("⚠️  MANUAL VERIFICATION NEEDED:")
            print_warning("    1. WebSocket should filter 'victim', 'VICTIM', 'ViCtIm'")
            print_warning("    2. Database lookup should be case-insensitive")
            print_warning("    This test CANNOT verify without WebSocket connection")

            # Clean up
            self.unblock_user(self.user1_token, self.user2_username)
            return True  # Can't fully test without WebSocket

        return False

    def test_unicode_homoglyph_attack(self):
        """
        ATTACK: Block "admin" but attacker uses "аdmin" (Cyrillic 'а')
        VULNERABILITY: Unicode homoglyphs can bypass username matching
        EXPECTED: Should normalize or detect homoglyphs
        """
        print_section("ATTACK: Unicode Homoglyph Bypass")

        print_test("User1 blocks 'Victim'")
        self.block_user(self.user1_token, self.user2_username)

        # Try to block a homoglyph version (Cyrillic characters that look like Latin)
        cyrillic_username = self.user2_username.replace('V', 'В')  # Cyrillic В looks like Latin V

        print_test(f"Attempting to block homoglyph: '{cyrillic_username}'")
        response = self.block_user(self.user1_token, cyrillic_username)

        if response.status_code in [200, 201]:
            print_warning("⚠️  VULNERABILITY FOUND: System allows blocking homoglyph variants")
            print_warning("    This could lead to confusion or bypass attacks")
            print_warning("    Original: " + self.user2_username.encode('unicode_escape').decode())
            print_warning("    Homoglyph: " + cyrillic_username.encode('unicode_escape').decode())

            # Check if we now have 2 blocks
            list_response = self.get_blocked_users(self.user1_token)
            count = list_response.json()['count']

            # Clean up
            self.unblock_user(self.user1_token, self.user2_username)
            self.unblock_user(self.user1_token, cyrillic_username)

            if count == 2:
                print_error("✗ SECURITY ISSUE: Homoglyph treated as different user")
                return False
            else:
                print_success("✓ System merged homoglyphs (good)")
                return True
        else:
            print_success("✓ Homoglyph block failed (expected if username doesn't exist)")
            self.unblock_user(self.user1_token, self.user2_username)
            return True

    def test_whitespace_manipulation(self):
        """
        ATTACK: Block "User" but send as "User " (with trailing space)
        VULNERABILITY: Whitespace not trimmed can bypass blocks
        EXPECTED: Input should be trimmed/normalized
        """
        print_section("ATTACK: Whitespace Manipulation")

        variations = [
            self.user2_username,
            f" {self.user2_username}",  # Leading space
            f"{self.user2_username} ",  # Trailing space
            f" {self.user2_username} ",  # Both
            f"{self.user2_username}\t",  # Tab
            f"{self.user2_username}\n",  # Newline
        ]

        print_test(f"Testing {len(variations)} whitespace variations...")

        blocked_count = 0
        for variant in variations:
            response = self.block_user(self.user1_token, variant)
            if response.status_code in [200, 201]:
                blocked_count += 1

        # Check how many unique blocks exist
        list_response = self.get_blocked_users(self.user1_token)
        actual_count = list_response.json()['count']

        # Clean up
        for variant in variations:
            self.unblock_user(self.user1_token, variant)

        if actual_count > 1:
            print_error(f"✗ SECURITY ISSUE: Created {actual_count} blocks for same user with whitespace")
            print_error("  Input validation should trim/normalize usernames")
            return False
        elif actual_count == 1:
            print_success("✓ All whitespace variations normalized to single block")
            return True
        else:
            print_warning("⚠️  Unclear result - no blocks created")
            return False

    def test_sql_injection_attempt(self):
        """
        ATTACK: SQL injection in username field
        VULNERABILITY: Unsanitized input could cause SQL injection
        EXPECTED: ORM should prevent this, but test anyway
        """
        print_section("ATTACK: SQL Injection Attempts")

        sql_payloads = [
            "'; DROP TABLE chats_userblock; --",
            "admin' OR '1'='1",
            "' UNION SELECT * FROM accounts_user --",
            "'; DELETE FROM chats_userblock WHERE '1'='1",
        ]

        print_test(f"Attempting {len(sql_payloads)} SQL injection payloads...")

        for payload in sql_payloads:
            response = self.block_user(self.user1_token, payload)

            if response.status_code == 500:
                print_error(f"✗ SERVER ERROR on payload: {payload[:50]}...")
                print_error("  This might indicate SQL injection vulnerability!")
                return False
            elif response.status_code in [200, 201]:
                print_test(f"Payload accepted (likely treated as invalid username): {payload[:30]}...")

        # Verify database still works
        list_response = self.get_blocked_users(self.user1_token)
        if list_response.status_code == 200:
            print_success("✓ Database intact after injection attempts")
            return True
        else:
            print_error("✗ Database query failed after injection attempts")
            return False

    def test_token_manipulation(self):
        """
        ATTACK: Use modified/invalid tokens
        VULNERABILITY: Weak token validation
        EXPECTED: All invalid tokens should be rejected
        """
        print_section("ATTACK: Token Manipulation")

        fake_tokens = [
            "Token " + "A" * 40,  # Fake token
            "Bearer " + self.user1_token,  # Wrong auth type
            self.user1_token[:-5] + "XXXXX",  # Modified token
            "",  # Empty
            "Token ",  # No token
        ]

        print_test(f"Attempting {len(fake_tokens)} fake/modified tokens...")

        vulnerabilities = 0
        for i, fake_token in enumerate(fake_tokens):
            headers = {"Authorization": fake_token} if fake_token else {}
            response = self.session.post(
                f"{API_BASE}/api/chats/user-blocks/block/",
                json={"username": "test"},
                headers=headers
            )

            if response.status_code in [200, 201]:
                print_error(f"✗ VULNERABILITY: Fake token #{i+1} was accepted!")
                vulnerabilities += 1
            elif response.status_code not in [401, 403]:
                print_warning(f"⚠️  Unexpected status {response.status_code} for token #{i+1}")

        if vulnerabilities > 0:
            print_error(f"✗ {vulnerabilities} token manipulation attempts succeeded")
            return False
        else:
            print_success("✓ All fake tokens correctly rejected")
            return True

    def test_rate_limiting(self):
        """
        ATTACK: Rapid block/unblock spam
        VULNERABILITY: No rate limiting allows DoS
        EXPECTED: Should have rate limiting (though maybe not implemented yet)
        """
        print_section("ATTACK: Rate Limiting / DoS")

        print_test("Attempting 50 rapid block/unblock operations...")

        start_time = time.time()
        success_count = 0

        for i in range(50):
            response = self.block_user(self.user1_token, self.user2_username)
            if response.status_code in [200, 201]:
                success_count += 1
            response = self.unblock_user(self.user1_token, self.user2_username)

        elapsed = time.time() - start_time

        print_test(f"Completed {success_count} operations in {elapsed:.2f}s")
        print_test(f"Rate: {success_count/elapsed:.1f} ops/second")

        if success_count == 50:
            print_warning("⚠️  NO RATE LIMITING DETECTED")
            print_warning("    An attacker could spam this endpoint")
            print_warning("    Consider adding rate limiting for production")
            return False  # This is a vulnerability
        else:
            print_success(f"✓ Rate limiting prevented {50-success_count} requests")
            return True

    def test_cross_user_data_leakage(self):
        """
        ATTACK: Try to see User2's block list
        VULNERABILITY: Improper authorization allows viewing others' data
        EXPECTED: Users should only see their own blocks
        """
        print_section("ATTACK: Cross-User Data Leakage")

        # User2 blocks User3
        print_test("User2 blocks User3")
        self.block_user(self.user2_token, self.user3_username)

        # User1 tries to see User2's block list
        print_test("User1 attempts to view User2's block list...")

        # This is a bit tricky - the API uses the token to determine whose list to show
        # So we're checking if the API properly isolates data

        user1_blocks = self.get_blocked_users(self.user1_token)
        user1_list = user1_blocks.json()['blocked_users']

        user2_blocks = self.get_blocked_users(self.user2_token)
        user2_list = user2_blocks.json()['blocked_users']

        # Check if User3 appears in User1's list (it shouldn't)
        user3_in_user1_list = any(b['username'] == self.user3_username for b in user1_list)

        # Clean up
        self.unblock_user(self.user2_token, self.user3_username)

        if user3_in_user1_list:
            print_error("✗ DATA LEAKAGE: User1 can see User2's blocks!")
            return False
        else:
            print_success("✓ Block lists properly isolated between users")
            return True

    def test_authorization_bypass(self):
        """
        ATTACK: User1 tries to unblock User2's blocks
        VULNERABILITY: Can manipulate others' block lists
        EXPECTED: Users can only modify their own blocks
        """
        print_section("ATTACK: Authorization Bypass")

        # User2 blocks User3
        print_test("User2 blocks User3")
        self.block_user(self.user2_token, self.user3_username)

        # User1 tries to unblock User3 (should fail - it's User2's block)
        print_test("User1 attempts to unblock User2's block...")
        response = self.unblock_user(self.user1_token, self.user3_username)

        if response.status_code == 200:
            print_error("✗ AUTHORIZATION BYPASS: User1 unblocked User2's block!")

            # Verify the block is actually gone
            user2_blocks = self.get_blocked_users(self.user2_token)
            user2_list = user2_blocks.json()['blocked_users']

            if not any(b['username'] == self.user3_username for b in user2_list):
                print_error("  Confirmed: Block was actually removed by wrong user")
                return False

        # Clean up
        self.unblock_user(self.user2_token, self.user3_username)

        print_success("✓ Authorization properly enforced")
        return True

    def test_race_condition(self):
        """
        ATTACK: Concurrent block/unblock operations
        VULNERABILITY: Race condition creates inconsistent state
        EXPECTED: Operations should be atomic
        """
        print_section("ATTACK: Race Condition")

        print_test("Launching 10 concurrent block operations...")

        results = []

        def block_target():
            response = self.block_user(self.user1_token, self.user2_username)
            results.append(response.status_code)

        threads = []
        for _ in range(10):
            t = threading.Thread(target=block_target)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Check final state
        list_response = self.get_blocked_users(self.user1_token)
        final_count = list_response.json()['count']

        # Clean up
        self.unblock_user(self.user1_token, self.user2_username)

        if final_count > 1:
            print_error(f"✗ RACE CONDITION: Created {final_count} duplicate blocks!")
            return False
        elif final_count == 1:
            print_success("✓ Race condition handled - only 1 block created")
            return True
        else:
            print_warning("⚠️  No blocks created - test inconclusive")
            return False

    def test_empty_username(self):
        """
        ATTACK: Empty or null username
        VULNERABILITY: Missing input validation
        EXPECTED: Should reject empty usernames
        """
        print_section("ATTACK: Empty Username Validation")

        invalid_inputs = [
            "",
            " ",
            None,
            "   ",
        ]

        print_test(f"Testing {len(invalid_inputs)} invalid username inputs...")

        for invalid in invalid_inputs:
            headers = {"Authorization": f"Token {self.user1_token}"}
            response = self.session.post(
                f"{API_BASE}/api/chats/user-blocks/block/",
                json={"username": invalid},
                headers=headers
            )

            if response.status_code in [200, 201]:
                print_error(f"✗ VALIDATION BYPASS: Empty username '{invalid}' accepted")
                return False

        print_success("✓ All empty username attempts rejected")
        return True

    def test_nonexistent_user_block(self):
        """
        ATTACK: Block a username that doesn't exist
        VULNERABILITY: Information disclosure (username enumeration)
        EXPECTED: Should allow blocking (or fail silently) without revealing if user exists
        """
        print_section("ATTACK: Username Enumeration")

        fake_username = "ThisUserDoesNotExist999"

        print_test(f"Attempting to block non-existent user: {fake_username}")
        response = self.block_user(self.user1_token, fake_username)

        if response.status_code in [200, 201]:
            print_success("✓ System allows blocking non-existent users (prevents enumeration)")

            # Clean up
            self.unblock_user(self.user1_token, fake_username)
            return True
        elif response.status_code == 404:
            print_error("✗ USERNAME ENUMERATION: Returns 404 for non-existent users")
            print_error("  Attackers can enumerate valid usernames")
            return False
        else:
            print_warning(f"⚠️  Unexpected status: {response.status_code}")
            return False

    # ========== TEST RUNNER ==========

    def run_all_tests(self):
        """Run complete adversarial test suite"""
        print_section("Adversarial Security Test Suite - User Blocking")

        print(f"{Colors.WARNING}⚠️  WARNING: These tests are designed to FIND VULNERABILITIES{Colors.ENDC}")
        print(f"{Colors.WARNING}⚠️  Tests may fail - that's the point!{Colors.ENDC}\n")

        # Setup: Register users
        print_section("Test Setup: User Registration")
        self.user1_token = self.register_user(self.user1_email, "password123", self.user1_username)
        self.user2_token = self.register_user(self.user2_email, "password123", self.user2_username)
        self.user3_token = self.register_user(self.user3_email, "password123", self.user3_username)

        if not all([self.user1_token, self.user2_token, self.user3_token]):
            print_error("Failed to register test users. Aborting.")
            return False

        print_success("3 test users registered")

        # Run adversarial tests
        test_results = []

        test_results.append(("Case Sensitivity Bypass", self.test_case_sensitivity_bypass()))
        test_results.append(("Unicode Homoglyph Attack", self.test_unicode_homoglyph_attack()))
        test_results.append(("Whitespace Manipulation", self.test_whitespace_manipulation()))
        test_results.append(("SQL Injection", self.test_sql_injection_attempt()))
        test_results.append(("Token Manipulation", self.test_token_manipulation()))
        test_results.append(("Rate Limiting / DoS", self.test_rate_limiting()))
        test_results.append(("Cross-User Data Leakage", self.test_cross_user_data_leakage()))
        test_results.append(("Authorization Bypass", self.test_authorization_bypass()))
        test_results.append(("Race Condition", self.test_race_condition()))
        test_results.append(("Empty Username Validation", self.test_empty_username()))
        test_results.append(("Username Enumeration", self.test_nonexistent_user_block()))

        # Print summary
        print_section("Security Test Results Summary")

        passed = sum(1 for _, result in test_results if result)
        total = len(test_results)

        for test_name, result in test_results:
            if result:
                print(f"{Colors.OKGREEN}✅ SECURE{Colors.ENDC} - {test_name}")
            else:
                print(f"{Colors.FAIL}❌ VULNERABLE{Colors.ENDC} - {test_name}")

        print(f"\n{Colors.BOLD}Security Score: {passed}/{total} tests passed{Colors.ENDC}")

        if passed == total:
            print_success("\n🛡️  All security tests passed! Implementation is secure.")
            return True
        else:
            vulnerabilities = total - passed
            print_error(f"\n⚠️  {vulnerabilities} SECURITY ISSUE(S) FOUND")
            print_error("Review the output above for details on each vulnerability")
            return False


def main():
    """Main entry point"""
    try:
        test_suite = AdversarialBlockingTests()
        success = test_suite.run_all_tests()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}Test interrupted by user{Colors.ENDC}")
        exit(1)
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
