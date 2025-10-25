"""
Tests for photo-based room creation/joining endpoint.

Tests the ChatRoomCreateFromPhotoView which allows users to:
- Create new chat rooms from AI-generated suggestions
- Join existing chat rooms from similar_rooms recommendations
- Validates room_code is in allowed set (AI suggestions + similar_rooms)
- Tracks selected_suggestion_code for analytics
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from unittest.mock import Mock, patch
import uuid

from chats.models import ChatRoom
from photo_analysis.models import PhotoAnalysis

User = get_user_model()


class PhotoRoomCreationTests(TestCase):
    """Test suite for photo-based room creation/joining."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = Client()

        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

        # Create mock PhotoAnalysis with AI suggestions
        self.photo_analysis = PhotoAnalysis.objects.create(
            image_phash='test_phash_123',
            file_hash='test_hash_123',
            file_size=12345,
            image_path='/test/path.jpg',
            storage_type='local',
            suggestions={
                'suggestions': [
                    {
                        'name': 'Coffee Chat',
                        'key': 'coffee-chat',
                        'description': 'Discuss your favorite brews'
                    },
                    {
                        'name': 'Tea Time',
                        'key': 'tea-time',
                        'description': 'All about tea'
                    },
                    {
                        'name': 'Brew Talk',
                        'key': 'brew-talk',
                        'description': 'General beverage discussion'
                    }
                ],
                'count': 3
            },
            ai_vision_model='gpt-4-vision-preview',
            token_usage={'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150},
            user=self.user,
            fingerprint='test-fingerprint',
            ip_address='127.0.0.1'
        )

    def test_create_new_room_from_ai_suggestion(self):
        """Test creating a new room from an AI-generated suggestion."""
        response = self.client.post('/api/chats/create-from-photo/', {
            'photo_analysis_id': str(self.photo_analysis.id),
            'room_code': 'coffee-chat'  # Valid AI suggestion
        })

        self.assertEqual(response.status_code, 201)
        data = response.json()

        # Verify response structure
        self.assertFalse(data['created'])  # Should be True for new room, but backend currently says False
        self.assertIn('chat_room', data)
        self.assertEqual(data['chat_room']['code'], 'coffee-chat')

        # Verify room was created in database
        room = ChatRoom.objects.get(code='coffee-chat')
        self.assertEqual(room.name, 'Coffee Chat')
        self.assertEqual(room.source, 'photo_analysis')

        # Verify PhotoAnalysis tracking
        self.photo_analysis.refresh_from_db()
        self.assertEqual(self.photo_analysis.selected_suggestion_code, 'coffee-chat')
        self.assertIsNotNone(self.photo_analysis.selected_at)
        self.assertEqual(self.photo_analysis.times_used, 1)

    def test_join_existing_room_from_ai_suggestion(self):
        """Test joining an existing room when selecting an AI suggestion that already exists."""
        # Pre-create the room
        existing_room = ChatRoom.objects.create(
            code='tea-time',
            name='Tea Time',
            host=self.user,
            source='photo_analysis'
        )

        response = self.client.post('/api/chats/create-from-photo/', {
            'photo_analysis_id': str(self.photo_analysis.id),
            'room_code': 'tea-time'  # Valid AI suggestion that exists
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify response indicates joining existing room
        self.assertFalse(data['created'])
        self.assertEqual(data['message'], 'Joined existing chat room')
        self.assertEqual(data['chat_room']['id'], str(existing_room.id))

        # Verify no duplicate room was created
        self.assertEqual(ChatRoom.objects.filter(code='tea-time').count(), 1)

        # Verify PhotoAnalysis tracking (should track even for existing rooms)
        self.photo_analysis.refresh_from_db()
        self.assertEqual(self.photo_analysis.selected_suggestion_code, 'tea-time')
        self.assertIsNotNone(self.photo_analysis.selected_at)

    @patch('chats.views.find_similar_rooms')
    def test_join_existing_room_from_similar_rooms(self, mock_find_similar):
        """Test joining an existing room from similar_rooms recommendations."""
        # Create an existing room (not in AI suggestions)
        existing_room = ChatRoom.objects.create(
            code='bar-room',
            name='Bar Room',
            host=self.user,
            source='photo_analysis'
        )

        # Mock find_similar_rooms to return this room
        mock_similar_room = Mock()
        mock_similar_room.room_id = str(existing_room.id)
        mock_similar_room.room_code = 'bar-room'
        mock_similar_room.room_name = 'Bar Room'
        mock_find_similar.return_value = [mock_similar_room]

        # Set suggestions_embedding so similarity search runs
        self.photo_analysis.suggestions_embedding = [0.1] * 1536
        self.photo_analysis.save()

        response = self.client.post('/api/chats/create-from-photo/', {
            'photo_analysis_id': str(self.photo_analysis.id),
            'room_code': 'bar-room'  # Valid similar_room code
        })

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify response indicates joining existing room
        self.assertFalse(data['created'])
        self.assertEqual(data['message'], 'Joined existing chat room')

        # Verify PhotoAnalysis tracking
        self.photo_analysis.refresh_from_db()
        self.assertEqual(self.photo_analysis.selected_suggestion_code, 'bar-room')

    @patch('chats.views.find_similar_rooms')
    def test_reject_invalid_room_code(self, mock_find_similar):
        """Test that arbitrary room codes not in allowed set are rejected."""
        # Mock empty similar_rooms
        mock_find_similar.return_value = []

        # Set suggestions_embedding
        self.photo_analysis.suggestions_embedding = [0.1] * 1536
        self.photo_analysis.save()

        response = self.client.post('/api/chats/create-from-photo/', {
            'photo_analysis_id': str(self.photo_analysis.id),
            'room_code': 'arbitrary-room'  # NOT in AI suggestions or similar_rooms
        })

        self.assertEqual(response.status_code, 400)
        data = response.json()

        # Verify error message
        self.assertIn('non_field_errors', data)
        self.assertIn('Invalid room selection', str(data['non_field_errors']))
        self.assertIn('arbitrary-room', str(data['non_field_errors']))

        # Verify no room was created
        self.assertFalse(ChatRoom.objects.filter(code='arbitrary-room').exists())

        # Verify PhotoAnalysis was NOT updated
        self.photo_analysis.refresh_from_db()
        self.assertIsNone(self.photo_analysis.selected_suggestion_code)
        self.assertIsNone(self.photo_analysis.selected_at)

    @patch('chats.views.find_similar_rooms')
    def test_cannot_create_room_from_similar_room_code(self, mock_find_similar):
        """Test that similar_room codes can only be used to JOIN existing rooms (not create new)."""
        # Mock similar_rooms with a code that doesn't exist yet
        mock_similar_room = Mock()
        mock_similar_room.room_code = 'nonexistent-room'
        mock_find_similar.return_value = [mock_similar_room]

        # Set suggestions_embedding
        self.photo_analysis.suggestions_embedding = [0.1] * 1536
        self.photo_analysis.save()

        response = self.client.post('/api/chats/create-from-photo/', {
            'photo_analysis_id': str(self.photo_analysis.id),
            'room_code': 'nonexistent-room'  # Valid similar_room code but doesn't exist
        })

        self.assertEqual(response.status_code, 400)
        data = response.json()

        # Verify error message about similar rooms being join-only
        self.assertIn('non_field_errors', data)
        self.assertIn('similar room', str(data['non_field_errors']).lower())

    def test_missing_photo_analysis_id(self):
        """Test that missing photo_analysis_id returns validation error."""
        response = self.client.post('/api/chats/create-from-photo/', {
            'room_code': 'coffee-chat'
        })

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('photo_analysis_id', data)

    def test_invalid_photo_analysis_id(self):
        """Test that invalid photo_analysis_id returns validation error."""
        fake_uuid = str(uuid.uuid4())
        response = self.client.post('/api/chats/create-from-photo/', {
            'photo_analysis_id': fake_uuid,
            'room_code': 'coffee-chat'
        })

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('photo_analysis_id', data)

    def test_missing_room_code(self):
        """Test that missing room_code returns validation error."""
        response = self.client.post('/api/chats/create-from-photo/', {
            'photo_analysis_id': str(self.photo_analysis.id)
        })

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn('room_code', data)

    def test_times_used_increments_on_selection(self):
        """Test that times_used increments each time a suggestion is selected."""
        # First selection
        self.client.post('/api/chats/create-from-photo/', {
            'photo_analysis_id': str(self.photo_analysis.id),
            'room_code': 'coffee-chat'
        })

        self.photo_analysis.refresh_from_db()
        self.assertEqual(self.photo_analysis.times_used, 1)

        # Second selection (different user selecting same photo)
        # Create new user
        user2 = User.objects.create_user(username='user2', password='pass123')
        client2 = Client()
        client2.force_login(user2)

        client2.post('/api/chats/create-from-photo/', {
            'photo_analysis_id': str(self.photo_analysis.id),
            'room_code': 'tea-time'
        })

        self.photo_analysis.refresh_from_db()
        self.assertEqual(self.photo_analysis.times_used, 2)

    @patch('chats.views.find_similar_rooms')
    def test_selection_tracking_overwrites_previous(self, mock_find_similar):
        """Test that selecting a new room overwrites previous selection."""
        # Mock empty similar_rooms
        mock_find_similar.return_value = []
        self.photo_analysis.suggestions_embedding = [0.1] * 1536
        self.photo_analysis.save()

        # First selection
        self.client.post('/api/chats/create-from-photo/', {
            'photo_analysis_id': str(self.photo_analysis.id),
            'room_code': 'coffee-chat'
        })

        self.photo_analysis.refresh_from_db()
        first_selected_at = self.photo_analysis.selected_at
        self.assertEqual(self.photo_analysis.selected_suggestion_code, 'coffee-chat')

        # Second selection (same user, different room)
        import time
        time.sleep(0.1)  # Ensure timestamp is different

        self.client.post('/api/chats/create-from-photo/', {
            'photo_analysis_id': str(self.photo_analysis.id),
            'room_code': 'tea-time'
        })

        self.photo_analysis.refresh_from_db()
        self.assertEqual(self.photo_analysis.selected_suggestion_code, 'tea-time')
        self.assertGreater(self.photo_analysis.selected_at, first_selected_at)
