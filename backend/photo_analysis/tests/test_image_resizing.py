"""
Tests for image resizing functionality in photo analysis.

Tests the resize_image_if_needed() function which automatically resizes
images that exceed the maximum megapixel limit to reduce token usage.
"""
import io
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from PIL import Image

from photo_analysis.utils.image_processing import resize_image_if_needed, get_image_dimensions


class ImageResizingTests(TestCase):
    """Test suite for image resizing functionality."""

    def _create_test_image(self, width, height, color='RGB', bg_color=(255, 0, 0)):
        """
        Helper to create a test image with specified dimensions.

        Args:
            width: Image width in pixels
            height: Image height in pixels
            color: Color mode (RGB, RGBA, L)
            bg_color: Background color tuple

        Returns:
            BytesIO containing the image data
        """
        img = Image.new(color, (width, height), bg_color)
        img_bytes = io.BytesIO()

        # Save as JPEG for RGB/L, PNG for RGBA
        if color == 'RGBA':
            img.save(img_bytes, format='PNG')
        else:
            img.save(img_bytes, format='JPEG', quality=95)

        img_bytes.seek(0)
        return img_bytes

    def test_small_image_is_not_resized(self):
        """Test that images below max megapixels are returned unchanged."""
        # Create 1000x1000 image = 1.0 MP (below 2.0 MP default limit)
        image_file = self._create_test_image(1000, 1000)
        original_size = len(image_file.read())
        image_file.seek(0)

        # Resize with 2.0 MP limit
        result, was_resized = resize_image_if_needed(image_file, max_megapixels=2.0)

        self.assertFalse(was_resized, "Small image should not be resized")

        # Verify dimensions unchanged
        result.seek(0)
        img = Image.open(result)
        self.assertEqual(img.size, (1000, 1000))

    def test_large_image_is_resized(self):
        """Test that images exceeding max megapixels are resized."""
        # Create 3000x2000 image = 6.0 MP (exceeds 2.0 MP limit)
        image_file = self._create_test_image(3000, 2000)

        # Resize with 2.0 MP limit
        result, was_resized = resize_image_if_needed(image_file, max_megapixels=2.0)

        self.assertTrue(was_resized, "Large image should be resized")

        # Verify image was actually resized to ~2.0 MP
        result.seek(0)
        img = Image.open(result)
        width, height = img.size
        megapixels = (width * height) / 1_000_000

        # Should be close to 2.0 MP (allow 5% tolerance)
        self.assertLess(megapixels, 2.1, "Resized image should be at or below max megapixels")
        self.assertGreater(megapixels, 1.9, "Resized image should be close to target")

    def test_resize_preserves_aspect_ratio(self):
        """Test that resizing preserves the original aspect ratio."""
        # Create 4000x2000 image (2:1 aspect ratio) = 8.0 MP
        image_file = self._create_test_image(4000, 2000)

        # Resize to 2.0 MP
        result, was_resized = resize_image_if_needed(image_file, max_megapixels=2.0)

        self.assertTrue(was_resized)

        # Check aspect ratio preserved
        result.seek(0)
        img = Image.open(result)
        width, height = img.size
        aspect_ratio = width / height

        # Original aspect ratio is 2.0, allow small rounding error
        self.assertAlmostEqual(aspect_ratio, 2.0, places=2)

    def test_resize_handles_rgba_to_rgb_conversion(self):
        """Test that RGBA images are converted to RGB for JPEG output."""
        # Create RGBA image but save as JPEG (which forces RGBA→RGB conversion)
        img = Image.new('RGBA', (2000, 2000), (255, 0, 0, 128))
        img_bytes = io.BytesIO()

        # Convert to RGB and save as JPEG (simulates what would happen with RGBA JPEG)
        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
        rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        rgb_img.save(img_bytes, format='JPEG', quality=95)
        img_bytes.seek(0)

        # Resize to 1.0 MP (forces resize)
        result, was_resized = resize_image_if_needed(img_bytes, max_megapixels=1.0)

        self.assertTrue(was_resized)

        # Verify output is RGB (no transparency) and format is JPEG
        result.seek(0)
        img_result = Image.open(result)
        self.assertEqual(img_result.mode, 'RGB', "Output should be RGB for JPEG")
        self.assertEqual(img_result.format, 'JPEG', "Output format should be JPEG")

    def test_resize_quality_setting(self):
        """Test that resized JPEG uses quality=85 setting."""
        # Create large image
        image_file = self._create_test_image(3000, 2000)

        # Resize
        result, was_resized = resize_image_if_needed(image_file, max_megapixels=2.0)

        self.assertTrue(was_resized)

        # Verify it's a valid JPEG
        result.seek(0)
        img = Image.open(result)
        self.assertEqual(img.format, 'JPEG')

    def test_different_max_megapixel_limits(self):
        """Test resizing with different megapixel limits."""
        # Create 2000x2000 image = 4.0 MP
        image_file = self._create_test_image(2000, 2000)

        # Test with 1.0 MP limit
        result, was_resized = resize_image_if_needed(image_file, max_megapixels=1.0)
        self.assertTrue(was_resized)

        result.seek(0)
        img = Image.open(result)
        megapixels = (img.size[0] * img.size[1]) / 1_000_000
        self.assertLess(megapixels, 1.1)

        # Test with 5.0 MP limit (should not resize)
        image_file.seek(0)
        result2, was_resized2 = resize_image_if_needed(image_file, max_megapixels=5.0)
        self.assertFalse(was_resized2)

    def test_square_image_resize(self):
        """Test resizing of square images."""
        # Create 3000x3000 square image = 9.0 MP
        image_file = self._create_test_image(3000, 3000)

        # Resize to 2.0 MP
        result, was_resized = resize_image_if_needed(image_file, max_megapixels=2.0)

        self.assertTrue(was_resized)

        # Verify still square
        result.seek(0)
        img = Image.open(result)
        width, height = img.size
        self.assertEqual(width, height, "Square image should remain square")

    def test_portrait_orientation_preserved(self):
        """Test that portrait orientation is preserved after resize."""
        # Create 1000x2000 portrait image (width < height)
        image_file = self._create_test_image(1000, 2000)

        # Resize to 1.0 MP
        result, was_resized = resize_image_if_needed(image_file, max_megapixels=1.0)

        self.assertTrue(was_resized)

        # Verify still portrait
        result.seek(0)
        img = Image.open(result)
        width, height = img.size
        self.assertLess(width, height, "Portrait orientation should be preserved")

    def test_landscape_orientation_preserved(self):
        """Test that landscape orientation is preserved after resize."""
        # Create 2000x1000 landscape image (width > height)
        image_file = self._create_test_image(2000, 1000)

        # Resize to 1.0 MP
        result, was_resized = resize_image_if_needed(image_file, max_megapixels=1.0)

        self.assertTrue(was_resized)

        # Verify still landscape
        result.seek(0)
        img = Image.open(result)
        width, height = img.size
        self.assertGreater(width, height, "Landscape orientation should be preserved")

    def test_invalid_image_raises_value_error(self):
        """Test that invalid image data raises ValueError."""
        # Create invalid image data
        invalid_data = io.BytesIO(b"not an image")

        # Should raise ValueError
        with self.assertRaises(ValueError) as context:
            resize_image_if_needed(invalid_data, max_megapixels=2.0)

        self.assertIn("Failed to process image", str(context.exception))

    def test_get_image_dimensions(self):
        """Test get_image_dimensions utility function."""
        # Create test image
        image_file = self._create_test_image(1920, 1080)

        # Get dimensions
        width, height = get_image_dimensions(image_file)

        self.assertEqual(width, 1920)
        self.assertEqual(height, 1080)

        # Verify file pointer is reset
        current_pos = image_file.tell()
        self.assertEqual(current_pos, 0, "File pointer should be reset after reading dimensions")

    def test_get_image_dimensions_invalid_image(self):
        """Test get_image_dimensions with invalid image data."""
        invalid_data = io.BytesIO(b"not an image")

        with self.assertRaises(ValueError) as context:
            get_image_dimensions(invalid_data)

        self.assertIn("Failed to read image dimensions", str(context.exception))

    def test_resize_returns_bytesio_object(self):
        """Test that resize returns a BytesIO object."""
        image_file = self._create_test_image(2000, 2000)

        result, was_resized = resize_image_if_needed(image_file, max_megapixels=1.0)

        self.assertIsInstance(result, io.BytesIO, "Result should be BytesIO object")
        self.assertTrue(was_resized)

    def test_resize_exact_limit_not_resized(self):
        """Test that image exactly at max megapixels is not resized."""
        # Create image at exactly 2.0 MP
        # sqrt(2_000_000) ≈ 1414.21, so 1414x1414 ≈ 1.999 MP
        image_file = self._create_test_image(1414, 1414)

        result, was_resized = resize_image_if_needed(image_file, max_megapixels=2.0)

        self.assertFalse(was_resized, "Image at exact limit should not be resized")

    def test_resize_very_small_image(self):
        """Test resizing very small images (e.g., thumbnails)."""
        # Create tiny 100x100 image
        image_file = self._create_test_image(100, 100)

        result, was_resized = resize_image_if_needed(image_file, max_megapixels=2.0)

        self.assertFalse(was_resized, "Very small image should not be resized")

        # Verify dimensions unchanged
        result.seek(0)
        img = Image.open(result)
        self.assertEqual(img.size, (100, 100))

    def test_resize_extreme_aspect_ratio(self):
        """Test resizing image with extreme aspect ratio (panorama)."""
        # Create 5000x500 panorama = 2.5 MP
        image_file = self._create_test_image(5000, 500)

        result, was_resized = resize_image_if_needed(image_file, max_megapixels=2.0)

        self.assertTrue(was_resized)

        # Verify aspect ratio preserved (10:1)
        result.seek(0)
        img = Image.open(result)
        width, height = img.size
        aspect_ratio = width / height
        self.assertAlmostEqual(aspect_ratio, 10.0, places=1)
