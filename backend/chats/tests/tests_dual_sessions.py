"""
Tests for dual sessions architecture and IP-based rate limiting

This test suite covers:
1. Dual sessions: Logged-in and anonymous users can have separate participations
2. IP-based rate limiting: Anonymous users limited to 3 usernames per IP per chat
3. Reserved username badge: Correctly identifies when a user is using their reserved_username
"""

import json

from accounts.models import User
from chats.models import ChatParticipation, ChatRoom
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient


class DualSessionsTests(TestCase):
    """Test dual sessions architecture"""

    def setUp(self):
        self.client = APIClient()

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

    def test_anonymous_join_creates_anonymous_participation(self):
        """Anonymous user joins chat with fingerprint"""
        url = f"/api/chats/{self.chat_room.code}/join/"
        data = {"username": "robert", "fingerprint": "anon-fingerprint-123"}

        response = self.client.post(url, json.dumps(data), content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "robert")

        # Verify anonymous participation created
        participation = ChatParticipation.objects.get(
            chat_room=self.chat_room, fingerprint="anon-fingerprint-123", user__isnull=True
        )
        self.assertEqual(participation.username, "robert")

    def test_logged_in_join_creates_user_participation(self):
        """Logged-in user joins chat"""
        self.client.force_authenticate(user=self.user)
        url = f"/api/chats/{self.chat_room.code}/join/"
        data = {"username": "Robert", "fingerprint": "user-fingerprint-456"}

        response = self.client.post(url, json.dumps(data), content_type="application/json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "Robert")

        # Verify user participation created
        participation = ChatParticipation.objects.get(chat_room=self.chat_room, user=self.user)
        self.assertEqual(participation.username, "Robert")

    def test_dual_sessions_allow_same_username(self):
        """Anonymous and logged-in users can use the same username simultaneously"""
        # 1. Anonymous user joins as "robert"
        url = f"/api/chats/{self.chat_room.code}/join/"
        anon_data = {"username": "robert", "fingerprint": "anon-fingerprint-123"}
        response = self.client.post(url, json.dumps(anon_data), content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 2. Logged-in user joins as "Robert" (case-insensitive same username)
        self.client.force_authenticate(user=self.user)
        user_data = {"username": "Robert", "fingerprint": "user-fingerprint-456"}
        response = self.client.post(url, json.dumps(user_data), content_type="application/json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 3. Verify both participations exist
        anon_participation = ChatParticipation.objects.get(
            chat_room=self.chat_room, fingerprint="anon-fingerprint-123", user__isnull=True
        )
        user_participation = ChatParticipation.objects.get(chat_room=self.chat_room, user=self.user)

        self.assertEqual(anon_participation.username, "robert")
        self.assertEqual(user_participation.username, "Robert")

    def test_my_participation_prioritizes_logged_in_user(self):
        """MyParticipationView returns logged-in participation when both exist"""
        # Create both anonymous and user participations
        ChatParticipation.objects.create(
            chat_room=self.chat_room, fingerprint="fingerprint-123", username="robert", ip_address="127.0.0.1"
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
        url = f"/api/chats/{self.chat_room.code}/my-participation/"
        response = self.client.get(url, {"fingerprint": "fingerprint-123"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["has_joined"])
        self.assertEqual(response.data["username"], "Robert")  # User participation, not anonymous

    def test_my_participation_returns_anonymous_when_not_logged_in(self):
        """MyParticipationView returns anonymous participation when not logged in"""
        # Create anonymous participation
        ChatParticipation.objects.create(
            chat_room=self.chat_room, fingerprint="fingerprint-123", username="robert", ip_address="127.0.0.1"
        )

        # Check as anonymous user
        url = f"/api/chats/{self.chat_room.code}/my-participation/"
        response = self.client.get(url, {"fingerprint": "fingerprint-123"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["has_joined"])
        self.assertEqual(response.data["username"], "robert")

    def test_my_participation_no_fallback_from_logged_in_to_anonymous(self):
        """Logged-in user doesn't see anonymous participation"""
        # Create ONLY anonymous participation
        ChatParticipation.objects.create(
            chat_room=self.chat_room, fingerprint="fingerprint-123", username="robert", ip_address="127.0.0.1"
        )

        # Check as logged-in user (different from anonymous participation)
        self.client.force_authenticate(user=self.user)
        url = f"/api/chats/{self.chat_room.code}/my-participation/"
        response = self.client.get(url, {"fingerprint": "fingerprint-123"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["has_joined"])  # No user participation found


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

    def test_username_is_reserved_when_exact_match(self):
        """Badge shown when participation username matches reserved_username exactly"""
        participation = ChatParticipation.objects.create(
            chat_room=self.chat_room, user=self.user, username="CoolUser", ip_address="127.0.0.1"
        )

        self.client.force_authenticate(user=self.user)
        url = f"/api/chats/{self.chat_room.code}/my-participation/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["username_is_reserved"])

    def test_username_is_reserved_when_case_insensitive_match(self):
        """Badge shown when participation username matches reserved_username (case-insensitive)"""
        participation = ChatParticipation.objects.create(
            chat_room=self.chat_room, user=self.user, username="cooluser", ip_address="127.0.0.1"  # lowercase
        )

        self.client.force_authenticate(user=self.user)
        url = f"/api/chats/{self.chat_room.code}/my-participation/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["username_is_reserved"])

    def test_username_is_not_reserved_when_different(self):
        """Badge NOT shown when participation username differs from reserved_username"""
        participation = ChatParticipation.objects.create(
            chat_room=self.chat_room, user=self.user, username="DifferentName", ip_address="127.0.0.1"
        )

        self.client.force_authenticate(user=self.user)
        url = f"/api/chats/{self.chat_room.code}/my-participation/"
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["username_is_reserved"])

    def test_username_is_not_reserved_for_anonymous_users(self):
        """Badge NOT shown for anonymous users (no reserved_username)"""
        participation = ChatParticipation.objects.create(
            chat_room=self.chat_room, fingerprint="anon-fingerprint", username="robert", ip_address="127.0.0.1"
        )

        url = f"/api/chats/{self.chat_room.code}/my-participation/"
        response = self.client.get(url, {"fingerprint": "anon-fingerprint"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["username_is_reserved"])


class IPRateLimitingTests(TestCase):
    """Test IP-based rate limiting for anonymous users"""

    def setUp(self):
        self.client = APIClient()

        # Create chat room
        self.host = User.objects.create_user(
            email="host@example.com", password="hostpass123", reserved_username="HostUser"
        )
        self.chat_room = ChatRoom.objects.create(
            name="Test Chat", code="TESTCODE", host=self.host, access_mode=ChatRoom.ACCESS_PUBLIC
        )

    def test_anonymous_user_can_join_within_limit(self):
        """Anonymous users can join up to 3 times from same IP"""
        url = f"/api/chats/{self.chat_room.code}/join/"

        # Join 3 times with different fingerprints (same IP)
        for i in range(3):
            data = {"username": f"user{i+1}123", "fingerprint": f"fingerprint-{i+1}"}
            response = self.client.post(
                url, json.dumps(data), content_type="application/json", REMOTE_ADDR="192.168.1.100"
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify 3 participations created
        count = ChatParticipation.objects.filter(
            chat_room=self.chat_room, ip_address="192.168.1.100", user__isnull=True
        ).count()
        self.assertEqual(count, 3)

    def test_anonymous_user_blocked_at_limit(self):
        """Anonymous users blocked when trying to join 4th time from same IP"""
        # Create 3 existing participations
        for i in range(3):
            ChatParticipation.objects.create(
                chat_room=self.chat_room,
                fingerprint=f"fingerprint-{i+1}",
                username=f"user{i+1}123",
                ip_address="192.168.1.100",
            )

        # Try to join 4th time
        url = f"/api/chats/{self.chat_room.code}/join/"
        data = {"username": "user4567", "fingerprint": "fingerprint-4"}
        response = self.client.post(
            url, json.dumps(data), content_type="application/json", REMOTE_ADDR="192.168.1.100"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Maximum anonymous usernames", str(response.data))

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
        url = f"/api/chats/{self.chat_room.code}/join/"
        data = {
            "username": "user1123",  # Same username as fingerprint-1
            "fingerprint": "fingerprint-1",  # Existing fingerprint
        }
        response = self.client.post(
            url, json.dumps(data), content_type="application/json", REMOTE_ADDR="192.168.1.100"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_different_ip_not_affected_by_limit(self):
        """IP limit is per-IP (different IPs can each have 3 anonymous users)"""
        # Create 3 participations from IP 1
        for i in range(3):
            ChatParticipation.objects.create(
                chat_room=self.chat_room,
                fingerprint=f"ip1-fingerprint-{i+1}",
                username=f"ip1user{i+1}",
                ip_address="192.168.1.100",
            )

        # User from different IP can still join
        url = f"/api/chats/{self.chat_room.code}/join/"
        data = {"username": "ip2user123", "fingerprint": "ip2-fingerprint-1"}
        response = self.client.post(
            url, json.dumps(data), content_type="application/json", REMOTE_ADDR="192.168.1.200"  # Different IP
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

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

        url = f"/api/chats/{self.chat_room.code}/join/"
        data = {"username": "LoggedInUser", "fingerprint": "logged-in-fingerprint"}
        response = self.client.post(
            url, json.dumps(data), content_type="application/json", REMOTE_ADDR="192.168.1.100"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_ip_limit_per_chat(self):
        """IP limit is per-chat (same IP can join 3 times in each chat)"""
        # Create second chat room
        chat_room_2 = ChatRoom.objects.create(
            name="Second Chat", code="TESTCOD2", host=self.host, access_mode=ChatRoom.ACCESS_PUBLIC
        )

        # Create 3 participations in first chat
        for i in range(3):
            ChatParticipation.objects.create(
                chat_room=self.chat_room,
                fingerprint=f"chat1-fingerprint-{i+1}",
                username=f"chat1user{i+1}",
                ip_address="192.168.1.100",
            )

        # User from same IP can still join second chat
        url = f"/api/chats/{chat_room_2.code}/join/"
        data = {"username": "chat2user123", "fingerprint": "chat2-fingerprint-1"}
        response = self.client.post(
            url, json.dumps(data), content_type="application/json", REMOTE_ADDR="192.168.1.100"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
