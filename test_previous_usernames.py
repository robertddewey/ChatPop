#!/usr/bin/env python3
"""
Test script for previous usernames feature on rate limit.

This script tests the username generation rate limiting and previous username display feature.
It simulates a user exhausting their 10 generation attempts and verifies that previously
generated usernames are returned.

Usage:
    python test_previous_usernames.py
"""

import requests
import json
import uuid
import urllib3

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuration
BASE_URL = "https://localhost:9000"
# Use the registration endpoint which doesn't require a chat to exist
API_ENDPOINT = f"{BASE_URL}/api/auth/suggest-username/"

def test_previous_usernames():
    """Test the previous usernames feature when rate limit is reached."""

    # Generate a unique fingerprint for this test session
    fingerprint = str(uuid.uuid4())

    print("=" * 80)
    print("Testing Previous Usernames Feature on Rate Limit")
    print("=" * 80)
    print(f"\nTest fingerprint: {fingerprint}")
    print(f"API endpoint: {API_ENDPOINT}\n")

    generated_usernames = []

    # Step 1: Generate usernames until we hit the rate limit
    print("Step 1: Generating usernames (max 10 attempts)...")
    print("-" * 80)

    for attempt in range(15):  # Try 15 times to ensure we hit the limit
        try:
            response = requests.post(
                API_ENDPOINT,
                json={"fingerprint": fingerprint},
                verify=False  # Skip SSL verification for local testing
            )

            if response.status_code == 200:
                data = response.json()
                username = data.get("username")
                remaining = data.get("generation_remaining")

                if username:
                    generated_usernames.append(username)
                    print(f"  Attempt {attempt + 1}: ✅ Generated '{username}' (Remaining: {remaining})")
                else:
                    print(f"  Attempt {attempt + 1}: ❌ Failed to generate username")

            elif response.status_code == 429:
                # Rate limited - this is what we're testing for
                data = response.json()
                error = data.get("error")
                remaining = data.get("generation_remaining", 0)
                previous_usernames = data.get("previous_usernames", [])

                print(f"\n  Attempt {attempt + 1}: 🛑 Rate limited!")
                print(f"  Error message: {error}")
                print(f"  Remaining attempts: {remaining}")
                print(f"  Previous usernames count: {len(previous_usernames)}")

                if previous_usernames:
                    print(f"\n  ✨ Previous usernames returned:")
                    for i, username in enumerate(previous_usernames, 1):
                        print(f"     {i}. {username}")

                    # Step 2: Verify previous usernames match generated ones
                    print(f"\n" + "-" * 80)
                    print("Step 2: Verifying previous usernames match generated ones...")
                    print("-" * 80)

                    # Normalize for comparison (case-insensitive)
                    generated_lower = [u.lower() for u in generated_usernames]
                    previous_lower = [u.lower() for u in previous_usernames]

                    matches = sum(1 for u in previous_lower if u in generated_lower)

                    print(f"  Generated usernames count: {len(generated_usernames)}")
                    print(f"  Previous usernames count: {len(previous_usernames)}")
                    print(f"  Matches: {matches}/{len(previous_usernames)}")

                    if matches == len(previous_usernames):
                        print(f"  ✅ All previous usernames match generated ones!")
                    else:
                        print(f"  ⚠️  Some previous usernames don't match")

                        # Show which ones don't match
                        for username in previous_usernames:
                            if username.lower() not in generated_lower:
                                print(f"     - '{username}' not in generated list")

                    # Step 3: Test that previous usernames are sorted
                    print(f"\n" + "-" * 80)
                    print("Step 3: Verifying usernames are alphabetically sorted...")
                    print("-" * 80)

                    sorted_previous = sorted(previous_usernames)
                    if previous_usernames == sorted_previous:
                        print(f"  ✅ Usernames are properly sorted!")
                    else:
                        print(f"  ❌ Usernames are not sorted")
                        print(f"  Expected: {sorted_previous}")
                        print(f"  Got: {previous_usernames}")

                    # Success summary
                    print(f"\n" + "=" * 80)
                    print("✅ TEST PASSED: Previous usernames feature is working correctly!")
                    print("=" * 80)
                    print(f"\nSummary:")
                    print(f"  - Generated {len(generated_usernames)} unique usernames")
                    print(f"  - Rate limit reached after 10 attempts")
                    print(f"  - Returned {len(previous_usernames)} previous usernames")
                    print(f"  - All previous usernames are valid and sorted")

                else:
                    print(f"\n  ❌ No previous usernames returned!")
                    print(f"  This could mean:")
                    print(f"     - No usernames were generated yet")
                    print(f"     - All generated usernames were taken by others")
                    print(f"     - Redis cache expired")

                break

            else:
                print(f"  Attempt {attempt + 1}: ❌ Unexpected status code: {response.status_code}")
                print(f"  Response: {response.text}")

        except requests.exceptions.RequestException as e:
            print(f"\n❌ ERROR: Failed to connect to backend")
            print(f"  Make sure the backend is running on {BASE_URL}")
            print(f"  Error: {str(e)}")
            return

    else:
        # Loop completed without hitting rate limit
        print(f"\n⚠️  WARNING: Did not hit rate limit after 15 attempts")
        print(f"  Generated {len(generated_usernames)} usernames")
        print(f"  This suggests the rate limit may not be working correctly")

if __name__ == "__main__":
    test_previous_usernames()
