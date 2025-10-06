"""
Tests for voice message functionality.
Tests voice upload, streaming, permissions, and storage.
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from unittest.mock import patch, MagicMock
import io

from accounts.models import User
from .models import ChatRoom, Message
from .security import ChatSessionValidator


class VoiceMessageUploadTests(TestCase):
    """Tests for voice message upload endpoint"""

    def setUp(self):
        self.client = APIClient()

        # Create test user
        self.user = User.objects.create_user(
            email='host@test.com',
            password='testpass123',
            reserved_username='testhost'
        )

        # Create chat room with voice enabled
        self.chat_enabled = ChatRoom.objects.create(
            name='Voice Chat',
            host=self.user,
            voice_enabled=True
        )

        # Create chat room with voice disabled
        self.chat_disabled = ChatRoom.objects.create(
            name='No Voice Chat',
            host=self.user,
            voice_enabled=False
        )

        # Generate session tokens
        self.session_token_enabled = ChatSessionValidator.create_session_token(
            chat_code=self.chat_enabled.code,
            username='testuser'
        )

        self.session_token_disabled = ChatSessionValidator.create_session_token(
            chat_code=self.chat_disabled.code,
            username='testuser'
        )

    def create_audio_file(self):
        """Create a mock audio file for testing"""
        audio_content = b'fake audio content for testing'
        return SimpleUploadedFile(
            'test_voice.webm',
            audio_content,
            content_type='audio/webm'
        )

    def test_upload_voice_message_success(self):
        """Test successful voice message upload"""
        url = reverse('chats:voice-upload', kwargs={'code': self.chat_enabled.code})
        audio_file = self.create_audio_file()

        response = self.client.post(url, {
            'voice_message': audio_file,
            'session_token': self.session_token_enabled
        }, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('voice_url', response.data)
        self.assertIn('storage_path', response.data)
        self.assertIn('storage_type', response.data)

    def test_upload_voice_disabled_chat(self):
        """Test upload fails when voice is disabled"""
        url = reverse('chats:voice-upload', kwargs={'code': self.chat_disabled.code})
        audio_file = self.create_audio_file()

        response = self.client.post(url, {
            'voice_message': audio_file,
            'session_token': self.session_token_disabled
        }, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('not enabled', response.data['error'])

    def test_upload_without_session_token(self):
        """Test upload fails without session token"""
        url = reverse('chats:voice-upload', kwargs={'code': self.chat_enabled.code})
        audio_file = self.create_audio_file()

        response = self.client.post(url, {
            'voice_message': audio_file
        }, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('Session token required', response.data['error'])

    def test_upload_invalid_session_token(self):
        """Test upload fails with invalid session token"""
        url = reverse('chats:voice-upload', kwargs={'code': self.chat_enabled.code})
        audio_file = self.create_audio_file()

        response = self.client.post(url, {
            'voice_message': audio_file,
            'session_token': 'invalid_token'
        }, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_upload_wrong_chat_session_token(self):
        """Test upload fails with session token from different chat"""
        url = reverse('chats:voice-upload', kwargs={'code': self.chat_enabled.code})
        audio_file = self.create_audio_file()

        response = self.client.post(url, {
            'voice_message': audio_file,
            'session_token': self.session_token_disabled  # Wrong chat
        }, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('Invalid session', response.data['error'])

    def test_upload_no_file(self):
        """Test upload fails without file"""
        url = reverse('chats:voice-upload', kwargs={'code': self.chat_enabled.code})

        response = self.client.post(url, {
            'session_token': self.session_token_enabled
        }, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('No voice message file', response.data['error'])

    def test_upload_file_too_large(self):
        """Test upload fails when file exceeds size limit"""
        url = reverse('chats:voice-upload', kwargs={'code': self.chat_enabled.code})

        # Create file larger than 10MB
        large_content = b'x' * (11 * 1024 * 1024)  # 11MB
        large_file = SimpleUploadedFile(
            'large_voice.webm',
            large_content,
            content_type='audio/webm'
        )

        response = self.client.post(url, {
            'voice_message': large_file,
            'session_token': self.session_token_enabled
        }, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('too large', response.data['error'])

    def test_upload_invalid_file_type(self):
        """Test upload fails with non-audio file"""
        url = reverse('chats:voice-upload', kwargs={'code': self.chat_enabled.code})

        text_file = SimpleUploadedFile(
            'test.txt',
            b'not an audio file',
            content_type='text/plain'
        )

        response = self.client.post(url, {
            'voice_message': text_file,
            'session_token': self.session_token_enabled
        }, format='multipart')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid file type', response.data['error'])

    def test_upload_various_audio_formats(self):
        """Test upload accepts various audio formats"""
        url = reverse('chats:voice-upload', kwargs={'code': self.chat_enabled.code})

        audio_formats = [
            ('test.webm', 'audio/webm'),
            ('test.mp4', 'audio/mp4'),
            ('test.mp3', 'audio/mpeg'),
            ('test.ogg', 'audio/ogg'),
            ('test.wav', 'audio/wav'),
        ]

        for filename, content_type in audio_formats:
            audio_file = SimpleUploadedFile(
                filename,
                b'fake audio content',
                content_type=content_type
            )

            response = self.client.post(url, {
                'voice_message': audio_file,
                'session_token': self.session_token_enabled
            }, format='multipart')

            self.assertEqual(response.status_code, status.HTTP_201_CREATED,
                           f"Failed for {content_type}")


class VoiceMessageStreamTests(TestCase):
    """Tests for voice message streaming endpoint"""

    def setUp(self):
        self.client = APIClient()

        # Create test user and chat
        self.user = User.objects.create_user(
            email='user@test.com',
            password='testpass123',
            reserved_username='testuser'
        )

        self.chat = ChatRoom.objects.create(
            name='Test Chat',
            host=self.user,
            voice_enabled=True
        )

        self.session_token = ChatSessionValidator.create_session_token(
            chat_code=self.chat.code,
            username='testuser'
        )

    @patch('chats.storage.MediaStorage.file_exists')
    @patch('chats.storage.MediaStorage.get_file')
    def test_stream_voice_message_success(self, mock_get_file, mock_file_exists):
        """Test successful voice message streaming"""
        mock_file_exists.return_value = True
        mock_file_obj = io.BytesIO(b'fake audio data')
        mock_get_file.return_value = mock_file_obj

        url = reverse('chats:voice-stream', kwargs={'storage_path': 'voice_messages/test.webm'})
        response = self.client.get(f"{url}?session_token={self.session_token}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'audio/webm')
        self.assertIn('Content-Disposition', response)

    @patch('chats.storage.MediaStorage.file_exists')
    def test_stream_without_session_token(self, mock_file_exists):
        """Test streaming fails without session token"""
        mock_file_exists.return_value = True

        url = reverse('chats:voice-stream', kwargs={'storage_path': 'voice_messages/test.webm'})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('chats.storage.MediaStorage.file_exists')
    def test_stream_invalid_session_token(self, mock_file_exists):
        """Test streaming fails with invalid session token"""
        mock_file_exists.return_value = True

        url = reverse('chats:voice-stream', kwargs={'storage_path': 'voice_messages/test.webm'})
        response = self.client.get(f"{url}?session_token=invalid")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('chats.storage.MediaStorage.file_exists')
    def test_stream_file_not_found(self, mock_file_exists):
        """Test streaming fails when file doesn't exist"""
        mock_file_exists.return_value = False

        url = reverse('chats:voice-stream', kwargs={'storage_path': 'voice_messages/notfound.webm'})
        response = self.client.get(f"{url}?session_token={self.session_token}")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch('chats.storage.MediaStorage.file_exists')
    @patch('chats.storage.MediaStorage.get_file')
    def test_stream_content_types(self, mock_get_file, mock_file_exists):
        """Test correct content-type for different audio formats"""
        mock_file_exists.return_value = True
        mock_file_obj = io.BytesIO(b'fake audio data')
        mock_get_file.return_value = mock_file_obj

        content_type_map = {
            'test.webm': 'audio/webm',
            'test.mp4': 'audio/mp4',
            'test.mp3': 'audio/mpeg',
            'test.ogg': 'audio/ogg',
            'test.wav': 'audio/wav',
        }

        for filename, expected_type in content_type_map.items():
            url = reverse('chats:voice-stream', kwargs={'storage_path': f'voice_messages/{filename}'})
            response = self.client.get(f"{url}?session_token={self.session_token}")

            self.assertEqual(response['Content-Type'], expected_type,
                           f"Wrong content type for {filename}")


class VoiceMessageStorageTests(TestCase):
    """Tests for voice message storage functionality"""

    def test_storage_type_detection(self):
        """Test storage type detection based on AWS config"""
        from chats.storage import MediaStorage

        # Mock settings for local storage
        with patch('chats.storage.settings') as mock_settings:
            mock_settings.AWS_ACCESS_KEY_ID = ''
            mock_settings.AWS_SECRET_ACCESS_KEY = ''
            mock_settings.AWS_STORAGE_BUCKET_NAME = ''

            self.assertFalse(MediaStorage.is_s3_configured())
            self.assertEqual(MediaStorage.get_storage_type(), 'local')

    def test_s3_configured_detection(self):
        """Test S3 detection when AWS credentials present"""
        from chats.storage import MediaStorage

        with patch('chats.storage.settings') as mock_settings:
            mock_settings.AWS_ACCESS_KEY_ID = 'test_key'
            mock_settings.AWS_SECRET_ACCESS_KEY = 'test_secret'
            mock_settings.AWS_STORAGE_BUCKET_NAME = 'test_bucket'

            self.assertTrue(MediaStorage.is_s3_configured())
            self.assertEqual(MediaStorage.get_storage_type(), 's3')

    @patch('chats.storage.default_storage.save')
    def test_save_voice_message(self, mock_save):
        """Test saving voice message to storage"""
        from chats.storage import save_voice_message

        mock_file = MagicMock()
        mock_file.read.return_value = b'fake audio data'
        mock_save.return_value = 'voice_messages/test.webm'

        storage_path, storage_type = save_voice_message(mock_file, 'test.webm')

        self.assertIn('voice_messages', storage_path)
        self.assertIn(storage_type, ['local', 's3'])

    def test_get_voice_message_url(self):
        """Test voice message URL generation"""
        from chats.storage import get_voice_message_url

        url = get_voice_message_url('voice_messages/test.webm')

        self.assertTrue(url.startswith('/api/media/'))
        self.assertIn('voice_messages/test.webm', url)


class VoiceMessageIntegrationTests(TestCase):
    """Integration tests for complete voice message flow"""

    def setUp(self):
        self.client = APIClient()

        # Create test user
        self.user = User.objects.create_user(
            email='user@test.com',
            password='testpass123',
            reserved_username='testuser'
        )

        # Create chat with voice enabled
        self.chat = ChatRoom.objects.create(
            name='Voice Chat',
            host=self.user,
            voice_enabled=True
        )

        self.session_token = ChatSessionValidator.create_session_token(
            chat_code=self.chat.code,
            username='testuser'
        )

    def test_complete_voice_message_flow(self):
        """Test complete flow: upload -> get URL -> stream"""
        # 1. Upload voice message
        upload_url = reverse('chats:voice-upload', kwargs={'code': self.chat.code})
        audio_file = SimpleUploadedFile(
            'test_voice.webm',
            b'fake audio content',
            content_type='audio/webm'
        )

        upload_response = self.client.post(upload_url, {
            'voice_message': audio_file,
            'session_token': self.session_token
        }, format='multipart')

        self.assertEqual(upload_response.status_code, status.HTTP_201_CREATED)
        voice_url = upload_response.data['voice_url']
        storage_path = upload_response.data['storage_path']

        # 2. Stream voice message (would need mocking for actual storage)
        # This verifies the URL format is correct
        self.assertTrue(voice_url.startswith('/api/media/'))
        self.assertIn('voice_messages/', voice_url)
