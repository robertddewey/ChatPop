"""
Tests for OpenAI Vision API integration (mocked).

All OpenAI API calls are mocked to avoid costs and rate limits.
Tests focus on our code logic, response parsing, and error handling.
"""
import io
import json
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from PIL import Image

from photo_analysis.utils.vision.base import AnalysisResult, ChatSuggestion, VisionProvider
from photo_analysis.utils.vision.openai_vision import OpenAIVisionProvider, get_vision_provider


class OpenAIVisionAPITests(TestCase):
    """Test suite for OpenAI Vision API integration (all mocked)."""

    def setUp(self):
        """Set up test fixtures."""
        # Generate a test image programmatically (10x10 red image)
        test_image = Image.new('RGB', (10, 10), color='red')
        test_image_bytes_io = io.BytesIO()
        test_image.save(test_image_bytes_io, format='JPEG', quality=95)
        test_image_bytes_io.seek(0)
        self.test_image_bytes = test_image_bytes_io.read()
        self.test_image_file = io.BytesIO(self.test_image_bytes)

    def _create_mock_openai_response(self, suggestions_count=10):
        """Create a mock OpenAI API response."""
        suggestions = [
            {
                "name": f"Chat Room {i}",
                "key": f"chat-room-{i}",
                "description": f"Description for chat room {i}"
            }
            for i in range(1, suggestions_count + 1)
        ]

        mock_response = MagicMock()
        mock_response.model = 'gpt-4o'
        mock_response.created = 1234567890
        mock_response.choices = [
            MagicMock(
                index=0,
                message=MagicMock(
                    role='assistant',
                    content=f'```json\n{json.dumps({"suggestions": suggestions})}\n```'
                ),
                finish_reason='stop'
            )
        ]
        mock_response.usage = MagicMock(
            prompt_tokens=1250,
            completion_tokens=180,
            total_tokens=1430
        )
        return mock_response

    @patch('photo_analysis.utils.vision.openai_vision.OpenAI')
    def test_vision_provider_analyzes_image_successfully(self, mock_openai_class):
        """Test successful image analysis with OpenAI Vision API."""
        # Configure mock
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._create_mock_openai_response()

        # Create provider and analyze image
        provider = OpenAIVisionProvider(api_key='test-key', model='gpt-4o')
        result = provider.analyze_image(
            image_file=self.test_image_file,
            prompt='Analyze this image',
            max_suggestions=10
        )

        # Verify result
        self.assertIsInstance(result, AnalysisResult)
        self.assertEqual(len(result.suggestions), 10)
        self.assertEqual(result.model, 'gpt-4o')
        self.assertIsNotNone(result.token_usage)
        self.assertGreater(result.token_usage['total_tokens'], 0)

    @patch('photo_analysis.utils.vision.openai_vision.OpenAI')
    def test_vision_provider_parses_json_response(self, mock_openai_class):
        """Test parsing of plain JSON response (without markdown)."""
        # Create response without markdown wrapper
        suggestions = [{"name": "Test Chat", "key": "test-chat", "description": "Test"}]

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.model = 'gpt-4o'
        mock_response.choices = [
            MagicMock(
                message=MagicMock(content=json.dumps({"suggestions": suggestions})),
                finish_reason='stop',
                index=0
            )
        ]
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        mock_response.created = 1234567890
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIVisionProvider(api_key='test-key')
        result = provider.analyze_image(self.test_image_file, 'Test', 10)

        self.assertEqual(len(result.suggestions), 1)
        self.assertEqual(result.suggestions[0].name, 'Test Chat')

    @patch('photo_analysis.utils.vision.openai_vision.OpenAI')
    def test_vision_provider_parses_markdown_wrapped_json(self, mock_openai_class):
        """Test parsing of JSON wrapped in markdown code blocks."""
        suggestions = [{"name": "Markdown Chat", "key": "markdown-chat", "description": "Test"}]

        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.model = 'gpt-4o'
        mock_response.choices = [
            MagicMock(
                message=MagicMock(content=f'```json\n{json.dumps({"suggestions": suggestions})}\n```'),
                finish_reason='stop',
                index=0
            )
        ]
        mock_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50, total_tokens=150)
        mock_response.created = 1234567890
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIVisionProvider(api_key='test-key')
        result = provider.analyze_image(self.test_image_file, 'Test', 10)

        self.assertEqual(len(result.suggestions), 1)
        self.assertEqual(result.suggestions[0].name, 'Markdown Chat')

    @patch('photo_analysis.utils.vision.openai_vision.settings')
    def test_vision_provider_handles_api_error(self, mock_settings):
        """Test graceful error handling when API is not configured."""
        # Ensure settings has no API key
        mock_settings.OPENAI_API_KEY = ''

        provider = OpenAIVisionProvider(api_key='')

        with self.assertRaises(RuntimeError) as context:
            provider.analyze_image(self.test_image_file, 'Test', 10)

        self.assertIn('API key not configured', str(context.exception))

    @patch('photo_analysis.utils.vision.openai_vision.OpenAI')
    def test_vision_provider_returns_correct_suggestion_format(self, mock_openai_class):
        """Test that suggestions have correct ChatSuggestion format."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._create_mock_openai_response(3)

        provider = OpenAIVisionProvider(api_key='test-key')
        result = provider.analyze_image(self.test_image_file, 'Test', 10)

        for suggestion in result.suggestions:
            self.assertIsInstance(suggestion, ChatSuggestion)
            self.assertIsInstance(suggestion.name, str)
            self.assertIsInstance(suggestion.key, str)
            self.assertIsInstance(suggestion.description, str)
            self.assertGreater(len(suggestion.name), 0)
            self.assertGreater(len(suggestion.key), 0)

    @patch('photo_analysis.utils.vision.openai_vision.OpenAI')
    def test_vision_provider_respects_max_suggestions_limit(self, mock_openai_class):
        """Test that max_suggestions parameter limits returned suggestions."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        # API returns 15 suggestions
        mock_client.chat.completions.create.return_value = self._create_mock_openai_response(15)

        provider = OpenAIVisionProvider(api_key='test-key')
        # Request only 10
        result = provider.analyze_image(self.test_image_file, 'Test', max_suggestions=10)

        # Should only return 10
        self.assertEqual(len(result.suggestions), 10)

    @patch('photo_analysis.utils.vision.openai_vision.OpenAI')
    def test_vision_provider_includes_token_usage(self, mock_openai_class):
        """Test that token usage is tracked in response."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._create_mock_openai_response()

        provider = OpenAIVisionProvider(api_key='test-key')
        result = provider.analyze_image(self.test_image_file, 'Test', 10)

        self.assertIn('prompt_tokens', result.token_usage)
        self.assertIn('completion_tokens', result.token_usage)
        self.assertIn('total_tokens', result.token_usage)
        self.assertEqual(result.token_usage['prompt_tokens'], 1250)
        self.assertEqual(result.token_usage['completion_tokens'], 180)
        self.assertEqual(result.token_usage['total_tokens'], 1430)

    @patch('photo_analysis.utils.vision.openai_vision.settings')
    def test_get_vision_provider_returns_openai_instance(self, mock_settings):
        """Test factory function returns OpenAI provider instance."""
        mock_settings.OPENAI_API_KEY = 'test-key'

        provider = get_vision_provider(model='gpt-4o')

        self.assertIsInstance(provider, OpenAIVisionProvider)
        self.assertIsInstance(provider, VisionProvider)
        self.assertEqual(provider.get_model_name(), 'gpt-4o')

    @patch('photo_analysis.utils.vision.openai_vision.settings')
    def test_vision_provider_is_available_check(self, mock_settings):
        """Test is_available() returns correct status."""
        # Ensure settings has no API key to prevent fallback
        mock_settings.OPENAI_API_KEY = ''

        # With API key
        provider_with_key = OpenAIVisionProvider(api_key='test-key')
        self.assertTrue(provider_with_key.is_available())

        # Without API key (empty string)
        provider_without_key = OpenAIVisionProvider(api_key='')
        self.assertFalse(provider_without_key.is_available())

        # Empty string (explicit)
        provider_empty_key = OpenAIVisionProvider(api_key='')
        self.assertFalse(provider_empty_key.is_available())
