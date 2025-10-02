from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from decimal import Decimal
from .models import ChatRoom, BackRoom, BackRoomMember, BackRoomMessage

User = get_user_model()


class BackRoomMessageTests(TestCase):
    """Tests for Back Room messaging functionality"""

    def setUp(self):
        # Create test users
        self.host = User.objects.create_user(
            email='host@test.com',
            password='testpass123',
            display_name='Host User'
        )
        self.member_user = User.objects.create_user(
            email='member@test.com',
            password='testpass123',
            display_name='Member User'
        )
        self.non_member = User.objects.create_user(
            email='nonmember@test.com',
            password='testpass123',
            display_name='Non Member'
        )

        # Create chat room
        self.chat_room = ChatRoom.objects.create(
            name='Test Chat',
            description='Test Description',
            host=self.host,
            access_mode='public'
        )

        # Create back room
        self.back_room = BackRoom.objects.create(
            chat_room=self.chat_room,
            price_per_seat=Decimal('10.00'),
            max_seats=5,
            seats_occupied=1,
            is_active=True
        )

        # Create back room member
        self.member = BackRoomMember.objects.create(
            back_room=self.back_room,
            username='TestMember',
            user=self.member_user,
            amount_paid=Decimal('10.00'),
            is_active=True
        )

        self.client = APIClient()

    def test_back_room_model_creation(self):
        """Test BackRoom model creation and properties"""
        self.assertEqual(self.back_room.seats_available, 4)
        self.assertFalse(self.back_room.is_full)
        self.assertEqual(str(self.back_room), f"BackRoom for {self.chat_room.name}")

    def test_back_room_message_model_creation(self):
        """Test BackRoomMessage model creation"""
        message = BackRoomMessage.objects.create(
            back_room=self.back_room,
            username='TestMember',
            user=self.member_user,
            content='Test message',
            message_type=BackRoomMessage.MESSAGE_NORMAL
        )
        self.assertEqual(message.username, 'TestMember')
        self.assertEqual(message.content, 'Test message')
        self.assertFalse(message.is_deleted)

    def test_host_can_view_messages(self):
        """Test that host can view back room messages"""
        self.client.force_authenticate(user=self.host)

        # Create a message
        BackRoomMessage.objects.create(
            back_room=self.back_room,
            username='Host',
            user=self.host,
            content='Host message'
        )

        response = self.client.get(
            f'/api/chats/{self.chat_room.code}/backroom/messages/',
            {'username': 'Host'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_member_can_view_messages(self):
        """Test that back room members can view messages"""
        self.client.force_authenticate(user=self.member_user)

        # Create a message
        BackRoomMessage.objects.create(
            back_room=self.back_room,
            username='TestMember',
            user=self.member_user,
            content='Member message'
        )

        response = self.client.get(
            f'/api/chats/{self.chat_room.code}/backroom/messages/',
            {'username': 'TestMember'}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_member_cannot_view_messages(self):
        """Test that non-members cannot view back room messages"""
        self.client.force_authenticate(user=self.non_member)

        response = self.client.get(
            f'/api/chats/{self.chat_room.code}/backroom/messages/',
            {'username': 'NonMember'}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_host_can_send_message(self):
        """Test that host can send back room messages"""
        self.client.force_authenticate(user=self.host)

        response = self.client.post(
            f'/api/chats/{self.chat_room.code}/backroom/messages/send/',
            {
                'username': 'Host',
                'content': 'Host message in back room'
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['message_type'], BackRoomMessage.MESSAGE_HOST)

    def test_member_can_send_message(self):
        """Test that members can send back room messages"""
        self.client.force_authenticate(user=self.member_user)

        response = self.client.post(
            f'/api/chats/{self.chat_room.code}/backroom/messages/send/',
            {
                'username': 'TestMember',
                'content': 'Member message in back room'
            }
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['message_type'], BackRoomMessage.MESSAGE_NORMAL)

    def test_non_member_cannot_send_message(self):
        """Test that non-members cannot send back room messages"""
        self.client.force_authenticate(user=self.non_member)

        response = self.client.post(
            f'/api/chats/{self.chat_room.code}/backroom/messages/send/',
            {
                'username': 'NonMember',
                'content': 'Should not work'
            }
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_only_host_can_view_members(self):
        """Test that only host can view back room member list"""
        self.client.force_authenticate(user=self.host)

        response = self.client.get(
            f'/api/chats/{self.chat_room.code}/backroom/members/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['username'], 'TestMember')

    def test_non_host_cannot_view_members(self):
        """Test that non-host users cannot view member list"""
        self.client.force_authenticate(user=self.member_user)

        response = self.client.get(
            f'/api/chats/{self.chat_room.code}/backroom/members/'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_back_room_full_status(self):
        """Test back room full status calculation"""
        self.back_room.seats_occupied = 5
        self.back_room.save()

        self.assertTrue(self.back_room.is_full)
        self.assertEqual(self.back_room.seats_available, 0)

    def test_message_reply_functionality(self):
        """Test message reply to another message"""
        # Create original message
        original = BackRoomMessage.objects.create(
            back_room=self.back_room,
            username='TestMember',
            user=self.member_user,
            content='Original message'
        )

        # Create reply
        reply = BackRoomMessage.objects.create(
            back_room=self.back_room,
            username='Host',
            user=self.host,
            content='Reply message',
            reply_to=original
        )

        self.assertEqual(reply.reply_to, original)
        self.assertEqual(original.replies.first(), reply)


class BackRoomIntegrationTests(TestCase):
    """Integration tests for Back Room feature"""

    def setUp(self):
        self.host = User.objects.create_user(
            email='host@test.com',
            password='testpass123'
        )
        self.chat_room = ChatRoom.objects.create(
            name='Test Chat',
            host=self.host
        )
        self.client = APIClient()

    def test_chat_room_without_back_room(self):
        """Test accessing back room endpoints when none exists"""
        self.client.force_authenticate(user=self.host)

        response = self.client.get(
            f'/api/chats/{self.chat_room.code}/backroom/messages/',
            {'username': 'Host'}
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_empty_message_validation(self):
        """Test that empty messages are rejected"""
        back_room = BackRoom.objects.create(
            chat_room=self.chat_room,
            price_per_seat=Decimal('10.00'),
            max_seats=5
        )

        self.client.force_authenticate(user=self.host)

        response = self.client.post(
            f'/api/chats/{self.chat_room.code}/backroom/messages/send/',
            {
                'username': 'Host',
                'content': '   '  # Only whitespace
            }
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
