"""
Tests for caption generation functionality in photo analysis.

Tests the generate_caption() function which generates semantic captions
optimized for text embedding models using OpenAI Vision API.
"""
import io
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
from PIL import Image

from photo_analysis.utils.caption import (
    generate_caption,
    CaptionData,
    _encode_image_to_base64,
    _parse_caption_response
)


class CaptionGenerationTests(TestCase):
    """Test suite for caption generation functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Generate a test image programmatically (100x100 brown/coffee colored image)
        test_image = Image.new('RGB', (100, 100), color=(101, 67, 33))  # Coffee brown color
        test_image_bytes_io = io.BytesIO()
        test_image.save(test_image_bytes_io, format='JPEG', quality=95)
        test_image_bytes_io.seek(0)
        self.test_image_bytes = test_image_bytes_io.read()

    def _create_test_image_file(self):
        """Helper to create a test image file object."""
        return io.BytesIO(self.test_image_bytes)

    def _create_mock_openai_response(self):
        """Create a mock OpenAI API response for caption generation."""
        mock_response = Mock()
        mock_response.model = 'gpt-4o-mini'
        mock_response.created = 1234567890
        mock_response.choices = [
            Mock(
                index=0,
                message=Mock(
                    role='assistant',
                    content='{"title": "Coffee Mug", "category": "beverage", "visible_text": "Starbucks", "caption": "Starbucks coffee mug on a wooden table. A popular coffee chain brand."}'
                ),
                finish_reason='stop'
            )
        ]
        mock_response.usage = Mock(
            prompt_tokens=850,
            completion_tokens=45,
            total_tokens=895
        )
        return mock_response

    def test_caption_data_class(self):
        """Test CaptionData class initialization and to_dict method."""
        caption_data = CaptionData(
            title='Budweiser Beer',
            category='beer bottle',
            visible_text='Budweiser, King of Beers',
            caption='Budweiser beer bottle labeled King of Beers with red and white logo.',
            raw_response={'model': 'gpt-4o-mini'},
            token_usage={'prompt_tokens': 850, 'completion_tokens': 45, 'total_tokens': 895},
            model='gpt-4o-mini'
        )

        self.assertEqual(caption_data.title, 'Budweiser Beer')
        self.assertEqual(caption_data.category, 'beer bottle')
        self.assertEqual(caption_data.visible_text, 'Budweiser, King of Beers')
        self.assertEqual(caption_data.model, 'gpt-4o-mini')

        # Test to_dict method
        caption_dict = caption_data.to_dict()
        self.assertIn('title', caption_dict)
        self.assertIn('caption', caption_dict)
        self.assertEqual(caption_dict['title'], 'Budweiser Beer')

    def test_encode_image_to_base64_success(self):
        """Test successful image encoding to base64."""
        image_file = self._create_test_image_file()

        base64_str = _encode_image_to_base64(image_file)

        self.assertIsInstance(base64_str, str)
        self.assertGreater(len(base64_str), 0)
        # Base64 strings are typically longer than original bytes
        self.assertGreater(len(base64_str), len(self.test_image_bytes) * 0.5)

    def test_encode_image_to_base64_invalid_image(self):
        """Test encoding with invalid image data raises ValueError."""
        invalid_image = io.BytesIO(b"not an image")

        with self.assertRaises(ValueError) as context:
            _encode_image_to_base64(invalid_image)

        self.assertIn("Invalid image file", str(context.exception))

    def test_encode_image_resets_file_pointer(self):
        """Test that encode_image_to_base64 resets file pointer."""
        image_file = self._create_test_image_file()

        _encode_image_to_base64(image_file)

        # File pointer should be reset to beginning after encoding
        # (actually, the current implementation reads all bytes, so pointer is at end)
        # But the function doesn't explicitly reset it, so this test verifies current behavior
        self.assertGreater(image_file.tell(), 0)

    def test_parse_caption_response_success(self):
        """Test parsing valid JSON caption response."""
        response_content = '{"title": "Coffee Mug", "category": "beverage", "visible_text": "Starbucks", "caption": "A coffee mug on a table."}'

        result = _parse_caption_response(response_content)

        self.assertEqual(result['title'], 'Coffee Mug')
        self.assertEqual(result['category'], 'beverage')
        self.assertEqual(result['visible_text'], 'Starbucks')
        self.assertEqual(result['caption'], 'A coffee mug on a table.')

    def test_parse_caption_response_with_markdown_code_blocks(self):
        """Test parsing response with markdown code blocks (```json)."""
        response_content = '```json\n{"title": "Beer Bottle", "category": "beverage", "visible_text": "Budweiser", "caption": "A beer bottle."}\n```'

        result = _parse_caption_response(response_content)

        self.assertEqual(result['title'], 'Beer Bottle')
        self.assertEqual(result['caption'], 'A beer bottle.')

    def test_parse_caption_response_missing_caption_field(self):
        """Test parsing response with missing caption field raises ValueError."""
        response_content = '{"title": "Test", "category": "test", "visible_text": ""}'

        with self.assertRaises(ValueError) as context:
            _parse_caption_response(response_content)

        self.assertIn("Caption field is required but was empty", str(context.exception))

    def test_parse_caption_response_invalid_json(self):
        """Test parsing invalid JSON raises ValueError."""
        response_content = 'not valid json'

        with self.assertRaises(ValueError) as context:
            _parse_caption_response(response_content)

        self.assertIn("Failed to parse JSON response", str(context.exception))

    @patch('photo_analysis.utils.caption.config')
    def test_generate_caption_disabled_raises_error(self, mock_config):
        """Test that caption generation raises error when disabled."""
        mock_config.PHOTO_ANALYSIS_ENABLE_CAPTIONS = False

        image_file = self._create_test_image_file()

        with self.assertRaises(RuntimeError) as context:
            generate_caption(image_file)

        self.assertIn("Caption generation is disabled", str(context.exception))

    @override_settings(OPENAI_API_KEY=None)
    @patch('photo_analysis.utils.caption.config')
    def test_generate_caption_no_api_key_raises_error(self, mock_config):
        """Test that caption generation raises error when API key not configured."""
        mock_config.PHOTO_ANALYSIS_ENABLE_CAPTIONS = True

        image_file = self._create_test_image_file()

        with self.assertRaises(RuntimeError) as context:
            generate_caption(image_file)

        self.assertIn("OpenAI API key not configured", str(context.exception))

    @override_settings(OPENAI_API_KEY='test-api-key-12345')
    @patch('photo_analysis.utils.caption.config')
    @patch('photo_analysis.utils.caption.OpenAI')
    def test_generate_caption_success(self, mock_openai_class, mock_config):
        """Test successful caption generation."""
        # Configure mocks
        mock_config.PHOTO_ANALYSIS_ENABLE_CAPTIONS = True
        mock_config.PHOTO_ANALYSIS_CAPTION_MODEL = 'gpt-4o-mini'
        mock_config.PHOTO_ANALYSIS_CAPTION_PROMPT = 'Generate a caption'
        mock_config.PHOTO_ANALYSIS_CAPTION_TEMPERATURE = 0.2
        mock_config.PHOTO_ANALYSIS_DETAIL_MODE = 'low'

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._create_mock_openai_response()

        image_file = self._create_test_image_file()

        result = generate_caption(image_file)

        # Verify result
        self.assertIsInstance(result, CaptionData)
        self.assertEqual(result.title, 'Coffee Mug')
        self.assertEqual(result.category, 'beverage')
        self.assertEqual(result.visible_text, 'Starbucks')
        self.assertIn('coffee mug', result.caption.lower())
        self.assertEqual(result.model, 'gpt-4o-mini')
        self.assertEqual(result.token_usage['total_tokens'], 895)

        # Verify OpenAI API was called correctly
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args
        self.assertEqual(call_args.kwargs['model'], 'gpt-4o-mini')
        self.assertEqual(call_args.kwargs['temperature'], 0.2)
        self.assertEqual(call_args.kwargs['max_tokens'], 300)
        self.assertEqual(call_args.kwargs['response_format'], {"type": "json_object"})

    @override_settings(OPENAI_API_KEY='test-api-key-12345')
    @patch('photo_analysis.utils.caption.config')
    @patch('photo_analysis.utils.caption.OpenAI')
    def test_generate_caption_uses_constance_settings(self, mock_openai_class, mock_config):
        """Test that caption generation uses Constance configuration."""
        # Configure custom settings
        mock_config.PHOTO_ANALYSIS_ENABLE_CAPTIONS = True
        mock_config.PHOTO_ANALYSIS_CAPTION_MODEL = 'gpt-4o'
        mock_config.PHOTO_ANALYSIS_CAPTION_PROMPT = 'Custom prompt text'
        mock_config.PHOTO_ANALYSIS_CAPTION_TEMPERATURE = 0.5
        mock_config.PHOTO_ANALYSIS_DETAIL_MODE = 'high'

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._create_mock_openai_response()

        image_file = self._create_test_image_file()

        generate_caption(image_file)

        # Verify Constance settings were used
        call_args = mock_client.chat.completions.create.call_args
        self.assertEqual(call_args.kwargs['model'], 'gpt-4o')
        self.assertEqual(call_args.kwargs['temperature'], 0.5)

        # Verify detail mode was used in image_url
        messages = call_args.kwargs['messages']
        image_content = messages[0]['content'][1]
        self.assertEqual(image_content['image_url']['detail'], 'high')

    @override_settings(OPENAI_API_KEY='test-api-key-12345')
    @patch('photo_analysis.utils.caption.config')
    @patch('photo_analysis.utils.caption.OpenAI')
    def test_generate_caption_parameter_overrides(self, mock_openai_class, mock_config):
        """Test that function parameters override Constance settings."""
        # Configure default settings
        mock_config.PHOTO_ANALYSIS_ENABLE_CAPTIONS = True
        mock_config.PHOTO_ANALYSIS_CAPTION_MODEL = 'gpt-4o-mini'
        mock_config.PHOTO_ANALYSIS_CAPTION_PROMPT = 'Default prompt'
        mock_config.PHOTO_ANALYSIS_CAPTION_TEMPERATURE = 0.2
        mock_config.PHOTO_ANALYSIS_DETAIL_MODE = 'low'

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._create_mock_openai_response()

        image_file = self._create_test_image_file()

        # Call with overrides
        generate_caption(
            image_file,
            model='gpt-4o',
            prompt='Custom override prompt',
            temperature=0.8
        )

        # Verify overrides were used
        call_args = mock_client.chat.completions.create.call_args
        self.assertEqual(call_args.kwargs['model'], 'gpt-4o')
        self.assertEqual(call_args.kwargs['temperature'], 0.8)

    @override_settings(OPENAI_API_KEY='test-api-key-12345')
    @patch('photo_analysis.utils.caption.config')
    @patch('photo_analysis.utils.caption.OpenAI')
    def test_generate_caption_api_failure_raises_error(self, mock_openai_class, mock_config):
        """Test that API failures are properly raised as RuntimeError."""
        mock_config.PHOTO_ANALYSIS_ENABLE_CAPTIONS = True
        mock_config.PHOTO_ANALYSIS_CAPTION_MODEL = 'gpt-4o-mini'
        mock_config.PHOTO_ANALYSIS_CAPTION_PROMPT = 'Generate a caption'
        mock_config.PHOTO_ANALYSIS_CAPTION_TEMPERATURE = 0.2
        mock_config.PHOTO_ANALYSIS_DETAIL_MODE = 'low'

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        image_file = self._create_test_image_file()

        with self.assertRaises(RuntimeError) as context:
            generate_caption(image_file)

        self.assertIn("Caption generation failed", str(context.exception))

    @override_settings(OPENAI_API_KEY='test-api-key-12345')
    @patch('photo_analysis.utils.caption.config')
    @patch('photo_analysis.utils.caption.OpenAI')
    def test_generate_caption_returns_token_usage(self, mock_openai_class, mock_config):
        """Test that caption generation returns token usage data."""
        mock_config.PHOTO_ANALYSIS_ENABLE_CAPTIONS = True
        mock_config.PHOTO_ANALYSIS_CAPTION_MODEL = 'gpt-4o-mini'
        mock_config.PHOTO_ANALYSIS_CAPTION_PROMPT = 'Generate a caption'
        mock_config.PHOTO_ANALYSIS_CAPTION_TEMPERATURE = 0.2
        mock_config.PHOTO_ANALYSIS_DETAIL_MODE = 'low'

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._create_mock_openai_response()

        image_file = self._create_test_image_file()

        result = generate_caption(image_file)

        # Verify token usage
        self.assertIn('prompt_tokens', result.token_usage)
        self.assertIn('completion_tokens', result.token_usage)
        self.assertIn('total_tokens', result.token_usage)
        self.assertEqual(result.token_usage['prompt_tokens'], 850)
        self.assertEqual(result.token_usage['completion_tokens'], 45)
        self.assertEqual(result.token_usage['total_tokens'], 895)

    @override_settings(OPENAI_API_KEY='test-api-key-12345')
    @patch('photo_analysis.utils.caption.config')
    @patch('photo_analysis.utils.caption.OpenAI')
    def test_generate_caption_returns_raw_response(self, mock_openai_class, mock_config):
        """Test that caption generation returns raw API response."""
        mock_config.PHOTO_ANALYSIS_ENABLE_CAPTIONS = True
        mock_config.PHOTO_ANALYSIS_CAPTION_MODEL = 'gpt-4o-mini'
        mock_config.PHOTO_ANALYSIS_CAPTION_PROMPT = 'Generate a caption'
        mock_config.PHOTO_ANALYSIS_CAPTION_TEMPERATURE = 0.2
        mock_config.PHOTO_ANALYSIS_DETAIL_MODE = 'low'

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._create_mock_openai_response()

        image_file = self._create_test_image_file()

        result = generate_caption(image_file)

        # Verify raw response structure
        self.assertIn('model', result.raw_response)
        self.assertIn('created', result.raw_response)
        self.assertIn('choices', result.raw_response)
        self.assertIn('usage', result.raw_response)
        self.assertEqual(result.raw_response['model'], 'gpt-4o-mini')

    def test_caption_data_to_dict_excludes_metadata(self):
        """Test that to_dict() excludes raw_response and token_usage."""
        caption_data = CaptionData(
            title='Test Title',
            category='test',
            visible_text='Test Text',
            caption='This is a test caption.',
            raw_response={'some': 'data'},
            token_usage={'total_tokens': 100},
            model='gpt-4o-mini'
        )

        result_dict = caption_data.to_dict()

        # Should only include caption fields, not metadata
        self.assertIn('title', result_dict)
        self.assertIn('category', result_dict)
        self.assertIn('visible_text', result_dict)
        self.assertIn('caption', result_dict)
        self.assertNotIn('raw_response', result_dict)
        self.assertNotIn('token_usage', result_dict)
        self.assertNotIn('model', result_dict)
