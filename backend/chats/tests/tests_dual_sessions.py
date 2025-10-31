"""
Tests for dual sessions architecture and IP-based rate limiting

This test suite covers:
1. Dual sessions: Logged-in and anonymous users can have separate participations
2. IP-based rate limiting: Anonymous users limited to 3 usernames per IP per chat
3. Reserved username badge: Correctly identifies when a user is using their reserved_username
"""

import allure
import json

from accounts.models import User
from chats.models import ChatParticipation, ChatRoom
from django.test import TestCase
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient


@allure.feature('Chat Sessions')
@allure.story('Dual Sessions Architecture')
class DualSessionsTests(TestCase):
    """Test dual sessions architecture"""

    def setUp(self):
        self.client = APIClient()
        cache.clear()

        # Create a test user with reserved_username
        self.user = User.objects.create_user(
            email="testuser@example.com", password="testpass123", reserved_username="Robert"
        )

        # Create a public chat room
        self.host = User.objects.create_user(
            email="host@example.com", password="hostpass123", reserved_username="HostUser"
        )
        self.chat_room = ChatRoom.objects.create(
            name="Test Chat", code="TESTCODE", host=self.host, access_mode=ChatRoom.ACCESS_PUBLIC
        )

        # Host must join first
        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host,
            username='HostUser',
            fingerprint='host_fingerprint',
            ip_address='127.0.0.1'
        )

    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()

    def generate_username(self, fingerprint):
        """Helper method to generate a username for anonymous users"""
        suggest_url = f"/api/chats/HostUser/{self.chat_room.code}/suggest-username/"
        response = self.client.post(suggest_url, json.dumps({'fingerprint': fingerprint}), content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data['username']

    @allure.title("Anonymous join creates anonymous participation")
    @allure.description("Anonymous user joins chat with fingerprint")
    @allure.severity(allure.severity_level.NORMAL)
    def test_anonymous_join_creates_anonymous_participation(self):
        """Anonymous user joins chat with fingerprint"""
        # Generate username first
        fingerprint = "anon-fingerprint-123"
        username = self.generate_username(fingerprint)

        url = f"/api/chats/HostUser/{self.chat_room.code}/join/"
        data = {"username": username, "fingerprint": fingerprint}

        response = self.client.post(url, json.dumps(data), content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], username)

        # Verify anonymous participation created
        participation = ChatParticipation.objects.get(
            chat_room=self.chat_room, fingerprint=fingerprint, user__isnull=True
        )
        self.assertEqual(participation.username, username)

    @allure.title("Logged-in join creates user participation")
    @allure.description("Logged-in user joins chat")
    @allure.severity(allure.severity_level.NORMAL)
    def test_logged_in_join_creates_user_participation(self):
        """Logged-in user joins chat"""
        self.client.force_authenticate(user=self.user)
        url = f"/api/chats/HostUser/{self.chat_room.code}/join/"
        data = {"username": "Robert", "fingerprint": "user-fingerprint-456"}

        response = self.client.post(url, json.dumps(data), content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "Robert")

        # Verify user participation created
        participation = ChatParticipation.objects.get(chat_room=self.chat_room, user=self.user)
        self.assertEqual(participation.username, "Robert")

    @allure.title("Duplicate usernames blocked across user types")
    @allure.description("Logged-in users cannot use usernames already taken by anonymous users")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_dual_sessions_prevent_duplicate_usernames(self):
        """Logged-in users cannot use usernames already taken by anonymous users"""
        # 1. Generate username for anonymous user
        anon_fingerprint = "anon-fingerprint-123"
        username = self.generate_username(anon_fingerprint)

        # 2. Anonymous user joins with generated username
        url = f"/api/chats/HostUser/{self.chat_room.code}/join/"
        anon_data = {"username": username, "fingerprint": anon_fingerprint}
        response = self.client.post(url, json.dumps(anon_data), content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 3. Logged-in user tries to join with same username (case variation) - should FAIL
        self.client.force_authenticate(user=self.user)
        user_data = {"username": username.upper(), "fingerprint": "user-fingerprint-456"}
        response = self.client.post(url, json.dumps(user_data), content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("already in use", str(response.data))

        # 4. Verify only anonymous participation exists
        anon_participation = ChatParticipation.objects.get(
            chat_room=self.chat_room, fingerprint=anon_fingerprint, user__isnull=True
        )
        self.assertEqual(anon_participation.username, username)

        # 5. Verify logged-in user did NOT create a participation
        user_participation_exists = ChatParticipation.objects.filter(
            chat_room=self.chat_room, user=self.user
        ).exists()
        self.assertFalse(user_participation_exists)

    @allure.title("MyParticipation prioritizes logged-in user")
    @allure.description("MyParticipationView returns logged-in participation when both exist with same fingerprint")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_my_participation_prioritizes_logged_in_user(self):
        """MyParticipationView returns logged-in participation when both exist with same fingerprint"""
        # Create both anonymous and user participations with DIFFERENT usernames but same fingerprint
        # (This tests the edge case where someone joined as anonymous, then logged in with different username)
        ChatParticipation.objects.create(
            chat_room=self.chat_room, fingerprint="fingerprint-123", username="GuestUser99", ip_address="127.0.0.1"
        )
        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.user,
            fingerprint="fingerprint-123",
            username="Robert",
            ip_address="127.0.0.1",
        )

        # Check as logged-in user
        self.client.force_authenticate(user=self.user)
        url = f"/api/chats/HostUser/{self.chat_room.code}/my-participation/"
        response = self.client.get(url, {"fingerprint": "fingerprint-123"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["has_joined"])
        self.assertEqual(response.data["username"], "Robert")  # User participation, not anonymous

    @allure.title("MyParticipation returns anonymous when not logged in")
    @allure.description("MyParticipationView returns anonymous participation when not logged in")
    @allure.severity(allure.severity_level.NORMAL)
    def test_my_participation_returns_anonymous_when_not_logged_in(self):
        """MyParticipationView returns anonymous participation when not logged in"""
        # Create anonymous participation
        ChatParticipation.objects.create(
            chat_room=self.chat_room, fingerprint="fingerprint-123", username="robert", ip_address="127.0.0.1"
        )

        # Check as anonymous user
        url = f"/api/chats/HostUser/{self.chat_room.code}/my-participation/"
        response = self.client.get(url, {"fingerprint": "fingerprint-123"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["has_joined"])
        self.assertEqual(response.data["username"], "robert")

    @allure.title("MyParticipation no fallback from logged-in to anonymous")
    @allure.description("Logged-in user doesn't see anonymous participation")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_my_participation_no_fallback_from_logged_in_to_anonymous(self):
        """Logged-in user doesn't see anonymous participation"""
        # Create ONLY anonymous participation
        ChatParticipation.objects.create(
            chat_room=self.chat_room, fingerprint="fingerprint-123", username="robert", ip_address="127.0.0.1"
        )

        # Check as logged-in user (different from anonymous participation)
        self.client.force_authenticate(user=self.user)
        url = f"/api/chats/HostUser/{self.chat_room.code}/my-participation/"
        response = self.client.get(url, {"fingerprint": "fingerprint-123"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["has_joined"])  # No user participation found


@allure.feature('User Authentication')
@allure.story('Reserved Username Badge')
class ReservedUsernameBadgeTests(TestCase):
    """Test reserved_username badge detection"""

    def setUp(self):
        self.client = APIClient()

        # Create user with reserved_username
        self.user = User.objects.create_user(
            email="testuser@example.com", password="testpass123", reserved_username="CoolUser"
        )

        # Create chat room
        self.host = User.objects.create_user(
            email="host@example.com", password="hostpass123", reserved_username="HostUser"
        )
        self.chat_room = ChatRoom.objects.create(
            name="Test Chat", code="TESTCODE", host=self.host, access_mode=ChatRoom.ACCESS_PUBLIC
        )

        # Host must join first
        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host,
            username='HostUser',
            fingerprint='host_fingerprint',
            ip_address='127.0.0.1'
        )

    @allure.title("Username is reserved when exact match")
    @allure.description("Badge shown when participation username matches reserved_username exactly")
    @allure.severity(allure.severity_level.NORMAL)
    def test_username_is_reserved_when_exact_match(self):
        """Badge shown when participation username matches reserved_username exactly"""
        participation = ChatParticipation.objects.create(
            chat_room=self.chat_room, user=self.user, username="CoolUser", ip_address="127.0.0.1"
        )

        self.client.force_authenticate(user=self.user)
        url = f"/api/chats/HostUser/{self.chat_room.code}/my-participation/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["username_is_reserved"])

    @allure.title("Username is reserved when case-insensitive match")
    @allure.description("Badge shown when participation username matches reserved_username (case-insensitive)")
    @allure.severity(allure.severity_level.NORMAL)
    def test_username_is_reserved_when_case_insensitive_match(self):
        """Badge shown when participation username matches reserved_username (case-insensitive)"""
        participation = ChatParticipation.objects.create(
            chat_room=self.chat_room, user=self.user, username="cooluser", ip_address="127.0.0.1"  # lowercase
        )

        self.client.force_authenticate(user=self.user)
        url = f"/api/chats/HostUser/{self.chat_room.code}/my-participation/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["username_is_reserved"])

    @allure.title("Username is not reserved when different")
    @allure.description("Badge NOT shown when participation username differs from reserved_username")
    @allure.severity(allure.severity_level.NORMAL)
    def test_username_is_not_reserved_when_different(self):
        """Badge NOT shown when participation username differs from reserved_username"""
        participation = ChatParticipation.objects.create(
            chat_room=self.chat_room, user=self.user, username="DifferentName", ip_address="127.0.0.1"
        )

        self.client.force_authenticate(user=self.user)
        url = f"/api/chats/HostUser/{self.chat_room.code}/my-participation/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["username_is_reserved"])

    @allure.title("Username is not reserved for anonymous users")
    @allure.description("Badge NOT shown for anonymous users (no reserved_username)")
    @allure.severity(allure.severity_level.NORMAL)
    def test_username_is_not_reserved_for_anonymous_users(self):
        """Badge NOT shown for anonymous users (no reserved_username)"""
        participation = ChatParticipation.objects.create(
            chat_room=self.chat_room, fingerprint="anon-fingerprint", username="robert", ip_address="127.0.0.1"
        )

        url = f"/api/chats/HostUser/{self.chat_room.code}/my-participation/"
        response = self.client.get(url, {"fingerprint": "anon-fingerprint"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["username_is_reserved"])


@allure.feature('Rate Limiting')
@allure.story('IP-Based Rate Limiting')
class IPRateLimitingTests(TestCase):
    """Test IP-based rate limiting for anonymous users"""

    def setUp(self):
        self.client = APIClient()
        cache.clear()

        # Create chat room
        self.host = User.objects.create_user(
            email="host@example.com", password="hostpass123", reserved_username="HostUser"
        )
        self.chat_room = ChatRoom.objects.create(
            name="Test Chat", code="TESTCODE", host=self.host, access_mode=ChatRoom.ACCESS_PUBLIC
        )

        # Host must join first
        ChatParticipation.objects.create(
            chat_room=self.chat_room,
            user=self.host,
            username='HostUser',
            fingerprint='host_fingerprint',
            ip_address='127.0.0.1'
        )

    def tearDown(self):
        """Clear cache after each test"""
        cache.clear()

    def generate_username(self, fingerprint):
        """Helper method to generate a username for anonymous users"""
        suggest_url = f"/api/chats/HostUser/{self.chat_room.code}/suggest-username/"
        response = self.client.post(suggest_url, json.dumps({'fingerprint': fingerprint}), content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        return response.data['username']

    @allure.title("Anonymous user can join within limit")
    @allure.description("Anonymous users can join up to 3 times from same IP")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_anonymous_user_can_join_within_limit(self):
        """Anonymous users can join up to 3 times from same IP"""
        url = f"/api/chats/HostUser/{self.chat_room.code}/join/"

        # Join 3 times with different fingerprints (same IP)
        for i in range(3):
            fingerprint = f"fingerprint-{i+1}"
            username = self.generate_username(fingerprint)
            data = {"username": username, "fingerprint": fingerprint}
            response = self.client.post(
                url, json.dumps(data), content_type="application/json", REMOTE_ADDR="192.168.1.100"
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify 3 participations created
        count = ChatParticipation.objects.filter(
            chat_room=self.chat_room, ip_address="192.168.1.100", user__isnull=True
        ).count()
        self.assertEqual(count, 3)

    @allure.title("Anonymous user blocked at limit")
    @allure.description("Anonymous users blocked when trying to join 4th time from same IP")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_anonymous_user_blocked_at_limit(self):
        """Anonymous users blocked when trying to join 4th time from same IP"""
        # Create 3 existing participations with generated usernames
        for i in range(3):
            fingerprint = f"fingerprint-{i+1}"
            username = self.generate_username(fingerprint)
            ChatParticipation.objects.create(
                chat_room=self.chat_room,
                fingerprint=fingerprint,
                username=username,
                ip_address="192.168.1.100",
            )

        # Try to join 4th time with generated username
        url = f"/api/chats/HostUser/{self.chat_room.code}/join/"
        fourth_fingerprint = "fingerprint-4"
        fourth_username = self.generate_username(fourth_fingerprint)
        data = {"username": fourth_username, "fingerprint": fourth_fingerprint}
        response = self.client.post(
            url, json.dumps(data), content_type="application/json", REMOTE_ADDR="192.168.1.100"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Max anonymous usernames", str(response.data))

    @allure.title("Returning anonymous user not blocked")
    @allure.description("Returning anonymous users can rejoin even if IP is at limit")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_returning_anonymous_user_not_blocked(self):
        """Returning anonymous users can rejoin even if IP is at limit"""
        # Create 3 existing participations
        for i in range(3):
            ChatParticipation.objects.create(
                chat_room=self.chat_room,
                fingerprint=f"fingerprint-{i+1}",
                username=f"user{i+1}123",
                ip_address="192.168.1.100",
            )

        # Returning user (existing fingerprint) can rejoin
        url = f"/api/chats/HostUser/{self.chat_room.code}/join/"
        data = {
            "username": "user1123",  # Same username as fingerprint-1
            "fingerprint": "fingerprint-1",  # Existing fingerprint
        }
        response = self.client.post(
            url, json.dumps(data), content_type="application/json", REMOTE_ADDR="192.168.1.100"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @allure.title("Different IP not affected by limit")
    @allure.description("IP limit is per-IP (different IPs can each have 3 anonymous users)")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_different_ip_not_affected_by_limit(self):
        """IP limit is per-IP (different IPs can each have 3 anonymous users)"""
        # Create 3 participations from IP 1 with generated usernames
        for i in range(3):
            fingerprint = f"ip1-fingerprint-{i+1}"
            username = self.generate_username(fingerprint)
            ChatParticipation.objects.create(
                chat_room=self.chat_room,
                fingerprint=fingerprint,
                username=username,
                ip_address="192.168.1.100",
            )

        # User from different IP can still join with generated username
        url = f"/api/chats/HostUser/{self.chat_room.code}/join/"
        ip2_fingerprint = "ip2-fingerprint-1"
        ip2_username = self.generate_username(ip2_fingerprint)
        data = {"username": ip2_username, "fingerprint": ip2_fingerprint}
        response = self.client.post(
            url, json.dumps(data), content_type="application/json", REMOTE_ADDR="192.168.1.200"  # Different IP
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @allure.title("Logged-in user not affected by IP limit")
    @allure.description("Logged-in users can join even if IP has 3 anonymous participations")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_logged_in_user_not_affected_by_ip_limit(self):
        """Logged-in users can join even if IP has 3 anonymous participations"""
        # Create 3 anonymous participations from same IP
        for i in range(3):
            ChatParticipation.objects.create(
                chat_room=self.chat_room,
                fingerprint=f"fingerprint-{i+1}",
                username=f"user{i+1}123",
                ip_address="192.168.1.100",
            )

        # Logged-in user can still join from same IP
        user = User.objects.create_user(
            email="test@example.com", password="testpass123", reserved_username="LoggedInUser"
        )
        self.client.force_authenticate(user=user)

        url = f"/api/chats/HostUser/{self.chat_room.code}/join/"
        data = {"username": "LoggedInUser", "fingerprint": "logged-in-fingerprint"}
        response = self.client.post(
            url, json.dumps(data), content_type="application/json", REMOTE_ADDR="192.168.1.100"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @allure.title("IP limit is per-chat")
    @allure.description("IP limit is per-chat (same IP can join 3 times in each chat)")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_ip_limit_per_chat(self):
        """IP limit is per-chat (same IP can join 3 times in each chat)"""
        # Create second chat room
        chat_room_2 = ChatRoom.objects.create(
            name="Second Chat", code="TESTCOD2", host=self.host, access_mode=ChatRoom.ACCESS_PUBLIC
        )

        # Host must join second chat first
        ChatParticipation.objects.create(
            chat_room=chat_room_2,
            user=self.host,
            username='HostUser',
            fingerprint='host_fingerprint_chat2',
            ip_address='127.0.0.1'
        )

        # Create 3 participations in first chat with generated usernames
        for i in range(3):
            fingerprint = f"chat1-fingerprint-{i+1}"
            username = self.generate_username(fingerprint)
            ChatParticipation.objects.create(
                chat_room=self.chat_room,
                fingerprint=fingerprint,
                username=username,
                ip_address="192.168.1.100",
            )

        # User from same IP can still join second chat with generated username
        url = f"/api/chats/HostUser/{chat_room_2.code}/join/"
        chat2_fingerprint = "chat2-fingerprint-1"
        # Generate username for second chat
        suggest_url = f"/api/chats/HostUser/{chat_room_2.code}/suggest-username/"
        suggest_response = self.client.post(suggest_url, json.dumps({'fingerprint': chat2_fingerprint}), content_type="application/json")
        self.assertEqual(suggest_response.status_code, status.HTTP_200_OK)
        chat2_username = suggest_response.data['username']

        data = {"username": chat2_username, "fingerprint": chat2_fingerprint}
        response = self.client.post(
            url, json.dumps(data), content_type="application/json", REMOTE_ADDR="192.168.1.100"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
