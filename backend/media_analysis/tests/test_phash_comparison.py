"""
Tests for perceptual hash (pHash) comparison functionality.

Tests the image similarity detection using perceptual hashing,
which can identify similar images despite minor modifications like
resizing, compression, or slight color changes.
"""
import os
import io
from django.test import TestCase
from PIL import Image, ImageFilter, ImageEnhance

from media_analysis.utils.fingerprinting.image_hash import (
    calculate_phash,
    calculate_phash_from_path,
    compare_phash,
    are_images_similar
)


class PerceptualHashComparisonTests(TestCase):
    """Test suite for perceptual hash comparison functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Path to test image fixture
        self.test_image_path = os.path.join(
            os.path.dirname(__file__),
            'fixtures',
            'test_coffee_mug.jpeg'
        )

        # Load test image
        with open(self.test_image_path, 'rb') as f:
            self.test_image_bytes = f.read()

        # Create PIL image for transformations
        self.test_image = Image.open(io.BytesIO(self.test_image_bytes))

    def test_calculate_phash_returns_consistent_hash_for_same_image(self):
        """Test that calculating pHash twice for same image returns same hash."""
        # Calculate hash twice
        hash1 = calculate_phash(io.BytesIO(self.test_image_bytes))
        hash2 = calculate_phash(io.BytesIO(self.test_image_bytes))

        # Should be identical
        self.assertEqual(hash1, hash2)

    def test_calculate_phash_returns_hex_string(self):
        """Test that pHash is returned as a hex string."""
        phash = calculate_phash(io.BytesIO(self.test_image_bytes))

        # Should be a string
        self.assertIsInstance(phash, str)

        # Should be hex (only 0-9, a-f characters)
        self.assertTrue(all(c in '0123456789abcdef' for c in phash))

        # Should have reasonable length (64-bit hash = 16 hex chars)
        self.assertEqual(len(phash), 16)

    def test_calculate_phash_accepts_bytes_input(self):
        """Test that calculate_phash accepts bytes input."""
        # Pass bytes directly (not file object)
        phash = calculate_phash(self.test_image_bytes)

        self.assertIsInstance(phash, str)
        self.assertEqual(len(phash), 16)

    def test_calculate_phash_from_path(self):
        """Test calculating pHash directly from file path."""
        phash = calculate_phash_from_path(self.test_image_path)

        self.assertIsInstance(phash, str)
        self.assertEqual(len(phash), 16)

    def test_calculate_phash_handles_invalid_image(self):
        """Test that invalid image data raises ValueError."""
        invalid_data = b'this is not an image'

        with self.assertRaises(ValueError) as context:
            calculate_phash(invalid_data)

        self.assertIn('Failed to calculate perceptual hash', str(context.exception))

    def test_compare_phash_returns_zero_for_identical_hashes(self):
        """Test that comparing identical hashes returns distance of 0."""
        hash1 = calculate_phash(io.BytesIO(self.test_image_bytes))
        hash2 = calculate_phash(io.BytesIO(self.test_image_bytes))

        distance = compare_phash(hash1, hash2)

        self.assertEqual(distance, 0)

    def test_compare_phash_returns_small_distance_for_resized_image(self):
        """Test that resized version of image has small Hamming distance."""
        # Original hash
        original_hash = calculate_phash(io.BytesIO(self.test_image_bytes))

        # Create resized version (50% smaller)
        resized_image = self.test_image.resize(
            (self.test_image.width // 2, self.test_image.height // 2),
            Image.Resampling.LANCZOS
        )

        # Save to bytes
        resized_bytes = io.BytesIO()
        resized_image.save(resized_bytes, format='JPEG')
        resized_bytes.seek(0)

        # Calculate hash of resized image
        resized_hash = calculate_phash(resized_bytes)

        # Compare
        distance = compare_phash(original_hash, resized_hash)

        # Should be very similar (distance <= 5 typically)
        self.assertLessEqual(distance, 5, f"Resized image distance {distance} > 5")

    def test_compare_phash_returns_small_distance_for_compressed_image(self):
        """Test that heavily compressed version has small Hamming distance."""
        # Original hash
        original_hash = calculate_phash(io.BytesIO(self.test_image_bytes))

        # Create heavily compressed version (quality 30)
        compressed_bytes = io.BytesIO()
        self.test_image.save(compressed_bytes, format='JPEG', quality=30)
        compressed_bytes.seek(0)

        # Calculate hash of compressed image
        compressed_hash = calculate_phash(compressed_bytes)

        # Compare
        distance = compare_phash(original_hash, compressed_hash)

        # Should still be similar (compression doesn't change structure much)
        self.assertLessEqual(distance, 8, f"Compressed image distance {distance} > 8")

    def test_compare_phash_returns_small_distance_for_slightly_modified_image(self):
        """Test that slightly blurred image has small Hamming distance."""
        # Original hash
        original_hash = calculate_phash(io.BytesIO(self.test_image_bytes))

        # Create slightly blurred version
        blurred_image = self.test_image.filter(ImageFilter.GaussianBlur(radius=1))

        # Save to bytes
        blurred_bytes = io.BytesIO()
        blurred_image.save(blurred_bytes, format='JPEG')
        blurred_bytes.seek(0)

        # Calculate hash of blurred image
        blurred_hash = calculate_phash(blurred_bytes)

        # Compare
        distance = compare_phash(original_hash, blurred_hash)

        # Should be very similar
        self.assertLessEqual(distance, 5, f"Blurred image distance {distance} > 5")

    def test_compare_phash_returns_small_distance_for_brightness_adjusted_image(self):
        """Test that brightness-adjusted image has small Hamming distance."""
        # Original hash
        original_hash = calculate_phash(io.BytesIO(self.test_image_bytes))

        # Create brightness-adjusted version (slightly brighter)
        enhancer = ImageEnhance.Brightness(self.test_image)
        bright_image = enhancer.enhance(1.2)  # 20% brighter

        # Save to bytes
        bright_bytes = io.BytesIO()
        bright_image.save(bright_bytes, format='JPEG')
        bright_bytes.seek(0)

        # Calculate hash of brightened image
        bright_hash = calculate_phash(bright_bytes)

        # Compare
        distance = compare_phash(original_hash, bright_hash)

        # Should be similar (pHash is resistant to brightness changes)
        self.assertLessEqual(distance, 10, f"Brightness-adjusted distance {distance} > 10")

    def test_compare_phash_returns_large_distance_for_different_images(self):
        """Test that completely different images have large Hamming distance."""
        # Original hash
        original_hash = calculate_phash(io.BytesIO(self.test_image_bytes))

        # Create a completely different image (solid color)
        different_image = Image.new('RGB', (300, 300), color='blue')

        # Save to bytes
        different_bytes = io.BytesIO()
        different_image.save(different_bytes, format='JPEG')
        different_bytes.seek(0)

        # Calculate hash of different image
        different_hash = calculate_phash(different_bytes)

        # Compare
        distance = compare_phash(original_hash, different_hash)

        # Should be very different (distance > 10)
        self.assertGreater(distance, 10, f"Different image distance {distance} <= 10")

    def test_are_images_similar_returns_true_for_same_image(self):
        """Test that are_images_similar returns True for identical images."""
        hash1 = calculate_phash(io.BytesIO(self.test_image_bytes))
        hash2 = calculate_phash(io.BytesIO(self.test_image_bytes))

        similar = are_images_similar(hash1, hash2)

        self.assertTrue(similar)

    def test_are_images_similar_returns_true_for_resized_image(self):
        """Test that are_images_similar returns True for resized image."""
        # Original hash
        original_hash = calculate_phash(io.BytesIO(self.test_image_bytes))

        # Resized image
        resized_image = self.test_image.resize(
            (self.test_image.width // 2, self.test_image.height // 2)
        )
        resized_bytes = io.BytesIO()
        resized_image.save(resized_bytes, format='JPEG')
        resized_bytes.seek(0)
        resized_hash = calculate_phash(resized_bytes)

        # Check similarity
        similar = are_images_similar(original_hash, resized_hash)

        self.assertTrue(similar)

    def test_are_images_similar_returns_false_for_different_images(self):
        """Test that are_images_similar returns False for different images."""
        # Original hash
        original_hash = calculate_phash(io.BytesIO(self.test_image_bytes))

        # Completely different image
        different_image = Image.new('RGB', (300, 300), color='red')
        different_bytes = io.BytesIO()
        different_image.save(different_bytes, format='JPEG')
        different_bytes.seek(0)
        different_hash = calculate_phash(different_bytes)

        # Check similarity
        similar = are_images_similar(original_hash, different_hash)

        self.assertFalse(similar)

    def test_are_images_similar_respects_custom_threshold(self):
        """Test that are_images_similar respects custom threshold parameter."""
        # Create two hashes with known distance
        hash1 = calculate_phash(io.BytesIO(self.test_image_bytes))

        # Create slightly modified image
        blurred_image = self.test_image.filter(ImageFilter.GaussianBlur(radius=2))
        blurred_bytes = io.BytesIO()
        blurred_image.save(blurred_bytes, format='JPEG')
        blurred_bytes.seek(0)
        hash2 = calculate_phash(blurred_bytes)

        distance = compare_phash(hash1, hash2)

        # Test with threshold above and below actual distance
        similar_high_threshold = are_images_similar(hash1, hash2, threshold=distance + 1)
        similar_low_threshold = are_images_similar(hash1, hash2, threshold=max(0, distance - 1))

        self.assertTrue(similar_high_threshold)
        if distance > 0:  # Only test if distance is not zero
            self.assertFalse(similar_low_threshold)

    def test_compare_phash_handles_invalid_hash(self):
        """Test that comparing invalid hashes raises ValueError."""
        valid_hash = calculate_phash(io.BytesIO(self.test_image_bytes))
        invalid_hash = "not-a-valid-hash"

        with self.assertRaises(ValueError) as context:
            compare_phash(valid_hash, invalid_hash)

        self.assertIn('Failed to compare perceptual hashes', str(context.exception))

    def test_phash_is_consistent_across_image_modes(self):
        """Test that pHash is similar for RGB and grayscale versions."""
        # Original RGB hash
        rgb_hash = calculate_phash(io.BytesIO(self.test_image_bytes))

        # Convert to grayscale
        grayscale_image = self.test_image.convert('L')
        grayscale_bytes = io.BytesIO()
        grayscale_image.save(grayscale_bytes, format='JPEG')
        grayscale_bytes.seek(0)
        grayscale_hash = calculate_phash(grayscale_bytes)

        # Compare
        distance = compare_phash(rgb_hash, grayscale_hash)

        # Should be similar (structure is the same)
        self.assertLessEqual(distance, 10, f"RGB vs Grayscale distance {distance} > 10")

    def test_phash_length_can_be_customized(self):
        """Test that hash_size parameter changes hash length."""
        # Default hash size (8 = 64-bit hash = 16 hex chars)
        hash_default = calculate_phash(io.BytesIO(self.test_image_bytes), hash_size=8)
        self.assertEqual(len(hash_default), 16)

        # Larger hash size (16 = 256-bit hash = 64 hex chars)
        hash_large = calculate_phash(io.BytesIO(self.test_image_bytes), hash_size=16)
        self.assertEqual(len(hash_large), 64)

        # Smaller hash size (4 = 16-bit hash = 4 hex chars)
        hash_small = calculate_phash(io.BytesIO(self.test_image_bytes), hash_size=4)
        self.assertEqual(len(hash_small), 4)
