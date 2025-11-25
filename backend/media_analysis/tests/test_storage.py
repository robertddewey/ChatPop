"""
Tests for media storage functionality (local and S3 - mocked).

Tests MediaStorage utility class used for saving/retrieving images
from both local filesystem and S3, with all S3 operations fully mocked.
"""
import io
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
from django.core.files.storage import Storage
from django.core.files.base import ContentFile

from chatpop.utils.media.storage import MediaStorage


class MediaStorageTests(TestCase):
    """Test suite for MediaStorage utility class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create test image bytes (minimal PNG)
        self.test_image_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'
        self.test_image_file = io.BytesIO(self.test_image_bytes)
        self.test_image_file.name = 'test.png'

    @override_settings(
        AWS_ACCESS_KEY_ID='test-key-id',
        AWS_SECRET_ACCESS_KEY='test-secret-key',
        AWS_STORAGE_BUCKET_NAME='test-bucket'
    )
    def test_is_s3_configured_returns_true_when_credentials_present(self):
        """Test that is_s3_configured returns True when AWS credentials are set."""
        self.assertTrue(MediaStorage.is_s3_configured())

    @override_settings(
        AWS_ACCESS_KEY_ID=None,
        AWS_SECRET_ACCESS_KEY=None,
        AWS_STORAGE_BUCKET_NAME=None
    )
    def test_is_s3_configured_returns_false_when_credentials_missing(self):
        """Test that is_s3_configured returns False when AWS credentials are missing."""
        self.assertFalse(MediaStorage.is_s3_configured())

    @override_settings(
        AWS_ACCESS_KEY_ID='test-key-id',
        AWS_SECRET_ACCESS_KEY='test-secret-key',
        AWS_STORAGE_BUCKET_NAME='test-bucket'
    )
    def test_get_storage_type_returns_s3_when_configured(self):
        """Test that get_storage_type returns 's3' when AWS is configured."""
        self.assertEqual(MediaStorage.get_storage_type(), 's3')

    @override_settings(
        AWS_ACCESS_KEY_ID=None,
        AWS_SECRET_ACCESS_KEY=None,
        AWS_STORAGE_BUCKET_NAME=None
    )
    def test_get_storage_type_returns_local_when_not_configured(self):
        """Test that get_storage_type returns 'local' when AWS is not configured."""
        self.assertEqual(MediaStorage.get_storage_type(), 'local')

    @patch('chatpop.utils.media.storage.default_storage')
    @override_settings(
        AWS_ACCESS_KEY_ID=None,
        AWS_SECRET_ACCESS_KEY=None,
        AWS_STORAGE_BUCKET_NAME=None
    )
    def test_save_file_to_local_storage(self, mock_storage):
        """Test saving a file to local storage."""
        # Configure mock
        mock_storage.save.return_value = 'media_analysis/test.png'

        # Save file
        storage_path, storage_type = MediaStorage.save_file(
            file_obj=self.test_image_file,
            directory='media_analysis',
            filename='test.png'
        )

        # Verify
        self.assertEqual(storage_path, 'media_analysis/test.png')
        self.assertEqual(storage_type, 'local')
        mock_storage.save.assert_called_once()

        # Verify file content was read and passed correctly
        call_args = mock_storage.save.call_args
        self.assertEqual(call_args[0][0], 'media_analysis/test.png')
        self.assertIsInstance(call_args[0][1], ContentFile)

    @patch('chatpop.utils.media.storage.default_storage')
    @override_settings(
        AWS_ACCESS_KEY_ID='test-key-id',
        AWS_SECRET_ACCESS_KEY='test-secret-key',
        AWS_STORAGE_BUCKET_NAME='test-bucket'
    )
    def test_save_file_to_s3_storage(self, mock_storage):
        """Test saving a file to S3 storage (mocked)."""
        # Configure mock
        mock_storage.save.return_value = 'media_analysis/test.png'

        # Save file
        storage_path, storage_type = MediaStorage.save_file(
            file_obj=self.test_image_file,
            directory='media_analysis',
            filename='test.png'
        )

        # Verify
        self.assertEqual(storage_path, 'media_analysis/test.png')
        self.assertEqual(storage_type, 's3')
        mock_storage.save.assert_called_once()

    @patch('chatpop.utils.media.storage.default_storage')
    def test_save_file_generates_unique_filename_when_not_provided(self, mock_storage):
        """Test that save_file auto-generates unique filename if not provided."""
        # Configure mock
        mock_storage.save.return_value = 'media_analysis/generated.png'

        # Save file without filename
        storage_path, storage_type = MediaStorage.save_file(
            file_obj=self.test_image_file,
            directory='media_analysis',
            filename=None
        )

        # Verify
        self.assertTrue(storage_path.startswith('media_analysis/'))
        self.assertTrue(storage_path.endswith('.png'))  # Extension from file.name
        mock_storage.save.assert_called_once()

    @patch('chatpop.utils.media.storage.default_storage')
    def test_delete_file_successfully(self, mock_storage):
        """Test successful file deletion."""
        # Configure mock
        mock_storage.exists.return_value = True
        mock_storage.delete.return_value = None

        # Delete file
        result = MediaStorage.delete_file('media_analysis/test.png')

        # Verify
        self.assertTrue(result)
        mock_storage.exists.assert_called_once_with('media_analysis/test.png')
        mock_storage.delete.assert_called_once_with('media_analysis/test.png')

    @patch('chatpop.utils.media.storage.default_storage')
    def test_delete_file_returns_false_when_file_not_exists(self, mock_storage):
        """Test that delete_file returns False when file doesn't exist."""
        # Configure mock
        mock_storage.exists.return_value = False

        # Delete file
        result = MediaStorage.delete_file('media_analysis/nonexistent.png')

        # Verify
        self.assertFalse(result)
        mock_storage.exists.assert_called_once_with('media_analysis/nonexistent.png')
        mock_storage.delete.assert_not_called()

    @patch('chatpop.utils.media.storage.default_storage')
    def test_delete_file_handles_exceptions_gracefully(self, mock_storage):
        """Test that delete_file handles exceptions without crashing."""
        # Configure mock to raise exception
        mock_storage.exists.side_effect = Exception('Storage error')

        # Delete file
        result = MediaStorage.delete_file('media_analysis/test.png')

        # Verify
        self.assertFalse(result)

    def test_get_file_url_returns_correct_proxy_path(self):
        """Test that get_file_url returns correct proxy URL path."""
        url = MediaStorage.get_file_url('media_analysis/test.png')

        self.assertEqual(url, '/api/chats/media/media_analysis/test.png')

    @patch('chatpop.utils.media.storage.default_storage')
    def test_get_file_returns_file_when_exists(self, mock_storage):
        """Test that get_file returns file object when file exists."""
        # Configure mock
        mock_file = io.BytesIO(self.test_image_bytes)
        mock_storage.exists.return_value = True
        mock_storage.open.return_value = mock_file

        # Get file
        result = MediaStorage.get_file('media_analysis/test.png')

        # Verify
        self.assertIsNotNone(result)
        self.assertEqual(result, mock_file)
        mock_storage.exists.assert_called_once_with('media_analysis/test.png')
        mock_storage.open.assert_called_once_with('media_analysis/test.png', 'rb')

    @patch('chatpop.utils.media.storage.default_storage')
    def test_get_file_returns_none_when_not_exists(self, mock_storage):
        """Test that get_file returns None when file doesn't exist."""
        # Configure mock
        mock_storage.exists.return_value = False

        # Get file
        result = MediaStorage.get_file('media_analysis/nonexistent.png')

        # Verify
        self.assertIsNone(result)
        mock_storage.exists.assert_called_once_with('media_analysis/nonexistent.png')
        mock_storage.open.assert_not_called()

    @patch('chatpop.utils.media.storage.default_storage')
    def test_get_file_handles_exceptions_gracefully(self, mock_storage):
        """Test that get_file handles exceptions without crashing."""
        # Configure mock to raise exception
        mock_storage.exists.side_effect = Exception('Storage error')

        # Get file
        result = MediaStorage.get_file('media_analysis/test.png')

        # Verify
        self.assertIsNone(result)

    @patch('chatpop.utils.media.storage.default_storage')
    def test_file_exists_returns_true_when_exists(self, mock_storage):
        """Test that file_exists returns True when file exists."""
        # Configure mock
        mock_storage.exists.return_value = True

        # Check existence
        result = MediaStorage.file_exists('media_analysis/test.png')

        # Verify
        self.assertTrue(result)
        mock_storage.exists.assert_called_once_with('media_analysis/test.png')

    @patch('chatpop.utils.media.storage.default_storage')
    def test_file_exists_returns_false_when_not_exists(self, mock_storage):
        """Test that file_exists returns False when file doesn't exist."""
        # Configure mock
        mock_storage.exists.return_value = False

        # Check existence
        result = MediaStorage.file_exists('media_analysis/nonexistent.png')

        # Verify
        self.assertFalse(result)
        mock_storage.exists.assert_called_once_with('media_analysis/nonexistent.png')

    @patch('chatpop.utils.media.storage.default_storage')
    @override_settings(
        AWS_ACCESS_KEY_ID='test-key-id',
        AWS_SECRET_ACCESS_KEY='test-secret-key',
        AWS_STORAGE_BUCKET_NAME='test-bucket'
    )
    def test_storage_type_recorded_correctly_for_s3(self, mock_storage):
        """Test that storage_type 's3' is returned when S3 is configured."""
        # Configure mock
        mock_storage.save.return_value = 'media_analysis/test.png'

        # Save file
        storage_path, storage_type = MediaStorage.save_file(
            file_obj=self.test_image_file,
            directory='media_analysis',
            filename='test.png'
        )

        # Verify storage type is 's3'
        self.assertEqual(storage_type, 's3')

    @patch('chatpop.utils.media.storage.default_storage')
    @override_settings(
        AWS_ACCESS_KEY_ID=None,
        AWS_SECRET_ACCESS_KEY=None,
        AWS_STORAGE_BUCKET_NAME=None
    )
    def test_storage_type_recorded_correctly_for_local(self, mock_storage):
        """Test that storage_type 'local' is returned when S3 is not configured."""
        # Configure mock
        mock_storage.save.return_value = 'media_analysis/test.png'

        # Save file
        storage_path, storage_type = MediaStorage.save_file(
            file_obj=self.test_image_file,
            directory='media_analysis',
            filename='test.png'
        )

        # Verify storage type is 'local'
        self.assertEqual(storage_type, 'local')

    @patch('chatpop.utils.media.storage.default_storage')
    def test_save_file_preserves_directory_structure(self, mock_storage):
        """Test that save_file preserves directory structure in path."""
        # Configure mock
        mock_storage.save.return_value = 'media_analysis/subfolder/test.png'

        # Save file with nested directory
        storage_path, storage_type = MediaStorage.save_file(
            file_obj=self.test_image_file,
            directory='media_analysis/subfolder',
            filename='test.png'
        )

        # Verify path structure
        self.assertEqual(storage_path, 'media_analysis/subfolder/test.png')
        self.assertIn('media_analysis/subfolder', storage_path)
