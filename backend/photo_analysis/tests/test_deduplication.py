"""
Tests for deduplication functionality in photo analysis.

Tests dual-hash deduplication strategy (pHash + MD5) and ensures
duplicate images return cached results without calling the OpenAI API again.
"""
import io
import json
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status
from PIL import Image

from photo_analysis.models import PhotoAnalysis
from photo_analysis.utils.fingerprinting.file_hash import calculate_md5
from photo_analysis.utils.fingerprinting.image_hash import calculate_phash

User = get_user_model()


class DeduplicationTests(TestCase):
    """Test suite for image deduplication functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )

        # Generate a test image programmatically (100x100 brown/coffee colored image)
        test_image = Image.new('RGB', (100, 100), color=(101, 67, 33))  # Coffee brown color
        test_image_bytes_io = io.BytesIO()
        test_image.save(test_image_bytes_io, format='JPEG', quality=95)
        test_image_bytes_io.seek(0)
        self.test_image_bytes = test_image_bytes_io.read()

    def _create_mock_vision_response(self):
        """Create a mock OpenAI vision response."""
        mock_response = Mock()
        mock_response.model = 'gpt-4o'
        mock_response.created = 1234567890
        mock_response.choices = [
            Mock(
                index=0,
                message=Mock(
                    role='assistant',
                    content='```json\n{"suggestions": [{"name": "Coffee Chat", "key": "coffee-chat", "description": "A cozy chat about coffee"}]}\n```'
                ),
                finish_reason='stop'
            )
        ]
        mock_response.usage = Mock(
            prompt_tokens=1250,
            completion_tokens=180,
            total_tokens=1430
        )
        return mock_response

    @patch('photo_analysis.views.get_vision_provider')
    @patch('photo_analysis.views.MediaStorage')
    def test_duplicate_image_returns_cached_analysis(self, mock_storage, mock_get_vision_provider):
        """Test that uploading the same image twice returns cached analysis."""
        # Configure mocks
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = True
        mock_provider.get_model_name.return_value = 'gpt-4o'
        mock_get_vision_provider.return_value = mock_provider

        mock_storage_instance = MagicMock()
        mock_storage_instance.is_s3_configured.return_value = False
        mock_storage_instance.save_local.return_value = 'photo_analysis/test.jpg'
        mock_storage.return_value = mock_storage_instance

        # Mock vision provider response
        from photo_analysis.utils.vision.base import AnalysisResult, ChatSuggestion
        mock_analysis_result = AnalysisResult(
            suggestions=[
                ChatSuggestion(
                    name='Coffee Chat',
                    key='coffee-chat',
                    description='A cozy chat about coffee'
                )
            ],
            raw_response={'model': 'gpt-4o'},
            token_usage={'prompt_tokens': 1250, 'completion_tokens': 180, 'total_tokens': 1430},
            model='gpt-4o'
        )
        mock_provider.analyze_image.return_value = mock_analysis_result

        # First upload - should call API
        image_file_1 = SimpleUploadedFile(
            name='test1.jpg',
            content=self.test_image_bytes,
            content_type='image/jpeg'
        )

        response1 = self.client.post(
            '/api/photo-analysis/upload/',
            {'image': image_file_1, 'fingerprint': 'test-fp-123'},
            format='multipart'
        )

        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response1.data.get('cached'))
        self.assertEqual(mock_provider.analyze_image.call_count, 1)

        # Second upload with same image - should return cached
        image_file_2 = SimpleUploadedFile(
            name='test2.jpg',  # Different filename
            content=self.test_image_bytes,  # Same content
            content_type='image/jpeg'
        )

        response2 = self.client.post(
            '/api/photo-analysis/upload/',
            {'image': image_file_2, 'fingerprint': 'test-fp-456'},
            format='multipart'
        )

        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertTrue(response2.data.get('cached'))
        # API should still only have been called once (from first upload)
        self.assertEqual(mock_provider.analyze_image.call_count, 1)

    @patch('photo_analysis.views.get_vision_provider')
    @patch('photo_analysis.views.MediaStorage')
    def test_duplicate_image_does_not_call_api_again(self, mock_storage, mock_get_vision_provider):
        """Test that duplicate images don't trigger additional API calls."""
        # Configure mocks
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = True
        mock_provider.get_model_name.return_value = 'gpt-4o'
        mock_get_vision_provider.return_value = mock_provider

        mock_storage_instance = MagicMock()
        mock_storage_instance.is_s3_configured.return_value = False
        mock_storage_instance.save_local.return_value = 'photo_analysis/test.jpg'
        mock_storage.return_value = mock_storage_instance

        # Mock vision provider response
        from photo_analysis.utils.vision.base import AnalysisResult, ChatSuggestion
        mock_analysis_result = AnalysisResult(
            suggestions=[ChatSuggestion(name='Test', key='test', description='Test')],
            raw_response={'model': 'gpt-4o'},
            token_usage={'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150},
            model='gpt-4o'
        )
        mock_provider.analyze_image.return_value = mock_analysis_result

        # First upload
        image_file = SimpleUploadedFile(
            name='test.jpg',
            content=self.test_image_bytes,
            content_type='image/jpeg'
        )
        self.client.post('/api/photo-analysis/upload/', {'image': image_file}, format='multipart')

        # Verify API was called once
        initial_call_count = mock_provider.analyze_image.call_count
        self.assertEqual(initial_call_count, 1)

        # Upload same image again
        image_file_dup = SimpleUploadedFile(
            name='test_duplicate.jpg',
            content=self.test_image_bytes,
            content_type='image/jpeg'
        )
        self.client.post('/api/photo-analysis/upload/', {'image': image_file_dup}, format='multipart')

        # API should not have been called again
        self.assertEqual(mock_provider.analyze_image.call_count, initial_call_count)

    @patch('photo_analysis.utils.rate_limit.config')
    @patch('photo_analysis.views.get_vision_provider')
    @patch('photo_analysis.views.MediaStorage')
    def test_duplicate_image_response_has_cached_flag(self, mock_storage, mock_get_vision_provider, mock_config):
        """Test that cached responses include 'cached': true flag."""
        # Disable rate limiting for this test
        mock_config.PHOTO_ANALYSIS_ENABLE_RATE_LIMITING = False

        # Configure mocks
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = True
        mock_provider.get_model_name.return_value = 'gpt-4o'
        mock_get_vision_provider.return_value = mock_provider

        mock_storage_instance = MagicMock()
        mock_storage_instance.is_s3_configured.return_value = False
        mock_storage_instance.save_local.return_value = 'photo_analysis/test.jpg'
        mock_storage.return_value = mock_storage_instance

        # Mock vision provider response
        from photo_analysis.utils.vision.base import AnalysisResult, ChatSuggestion
        mock_analysis_result = AnalysisResult(
            suggestions=[ChatSuggestion(name='Test', key='test', description='Test')],
            raw_response={'model': 'gpt-4o'},
            token_usage={'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150},
            model='gpt-4o'
        )
        mock_provider.analyze_image.return_value = mock_analysis_result

        # First upload - should have cached: false
        image_file_1 = SimpleUploadedFile(
            name='test1.jpg',
            content=self.test_image_bytes,
            content_type='image/jpeg'
        )
        response1 = self.client.post('/api/photo-analysis/upload/', {'image': image_file_1}, format='multipart')

        # Parse response data (works for both Response and JsonResponse)
        data1 = response1.data if hasattr(response1, 'data') else json.loads(response1.content)
        self.assertIn('cached', data1)
        self.assertFalse(data1['cached'])

        # Second upload - should have cached: true
        image_file_2 = SimpleUploadedFile(
            name='test2.jpg',
            content=self.test_image_bytes,
            content_type='image/jpeg'
        )
        response2 = self.client.post('/api/photo-analysis/upload/', {'image': image_file_2}, format='multipart')

        # Parse response data (works for both Response and JsonResponse)
        data2 = response2.data if hasattr(response2, 'data') else json.loads(response2.content)
        self.assertIn('cached', data2)
        self.assertTrue(data2['cached'])

    @patch('photo_analysis.views.get_vision_provider')
    @patch('photo_analysis.views.MediaStorage')
    def test_different_image_creates_new_analysis(self, mock_storage, mock_get_vision_provider):
        """Test that different images create separate analysis records."""
        # Configure mocks
        mock_provider = MagicMock()
        mock_provider.is_available.return_value = True
        mock_provider.get_model_name.return_value = 'gpt-4o'
        mock_get_vision_provider.return_value = mock_provider

        mock_storage_instance = MagicMock()
        mock_storage_instance.is_s3_configured.return_value = False
        mock_storage_instance.save_local.return_value = 'photo_analysis/test.jpg'
        mock_storage.return_value = mock_storage_instance

        # Mock vision provider response
        from photo_analysis.utils.vision.base import AnalysisResult, ChatSuggestion
        mock_analysis_result = AnalysisResult(
            suggestions=[ChatSuggestion(name='Test', key='test', description='Test')],
            raw_response={'model': 'gpt-4o'},
            token_usage={'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150},
            model='gpt-4o'
        )
        mock_provider.analyze_image.return_value = mock_analysis_result

        # Upload first image
        image_file_1 = SimpleUploadedFile(
            name='test1.jpg',
            content=self.test_image_bytes,
            content_type='image/jpeg'
        )
        response1 = self.client.post('/api/photo-analysis/upload/', {'image': image_file_1}, format='multipart')
        self.assertEqual(response1.status_code, status.HTTP_201_CREATED)

        # Create a different image (modify bytes slightly)
        different_image_bytes = bytearray(self.test_image_bytes)
        if len(different_image_bytes) > 100:
            different_image_bytes[50] = (different_image_bytes[50] + 1) % 256
        different_image_bytes = bytes(different_image_bytes)

        # Upload second (different) image
        image_file_2 = SimpleUploadedFile(
            name='test2.jpg',
            content=different_image_bytes,
            content_type='image/jpeg'
        )
        response2 = self.client.post('/api/photo-analysis/upload/', {'image': image_file_2}, format='multipart')

        # Should create new analysis (not cached)
        self.assertEqual(response2.status_code, status.HTTP_201_CREATED)
        self.assertFalse(response2.data.get('cached'))

        # Verify different analysis IDs
        analysis_id_1 = response1.data['analysis']['id']
        analysis_id_2 = response2.data['analysis']['id']
        self.assertNotEqual(analysis_id_1, analysis_id_2)

        # Verify two separate database records
        self.assertEqual(PhotoAnalysis.objects.count(), 2)

    def test_duplicate_increments_times_used_counter(self):
        """Test that usage counter can be incremented (future feature)."""
        # Create test analysis record
        file_hash = calculate_md5(self.test_image_bytes)
        phash = calculate_phash(self.test_image_bytes)

        analysis = PhotoAnalysis.objects.create(
            image_phash=phash,
            file_hash=file_hash,
            file_size=len(self.test_image_bytes),
            image_path='photo_analysis/test.jpg',
            storage_type='local',
            suggestions={'suggestions': [], 'count': 0},
            ai_vision_model='gpt-4o',
            times_used=0
        )

        # Verify initial count
        self.assertEqual(analysis.times_used, 0)

        # Increment usage
        analysis.increment_usage()

        # Verify increment
        self.assertEqual(analysis.times_used, 1)

        # Increment again
        analysis.increment_usage()
        self.assertEqual(analysis.times_used, 2)

        # Verify persistence
        analysis.refresh_from_db()
        self.assertEqual(analysis.times_used, 2)
