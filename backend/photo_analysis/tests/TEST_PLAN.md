# Photo Analysis Test Plan

## Overview

This document outlines the comprehensive test plan for the `photo_analysis` Django app, which provides AI-powered photo analysis using OpenAI GPT-4o Vision API to generate contextual chat room name suggestions.

---

## Testing Strategy: Unit Tests vs Integration Tests

### Why Two Layers of Tests?

**Unit Tests (Mocked)** - Run automatically on every commit
- ✅ Fast execution (milliseconds)
- ✅ Free (no API costs)
- ✅ Reliable (no network dependencies)
- ✅ Test our code logic
- ❌ Don't verify real OpenAI API works
- ❌ Won't catch API format changes

**Integration Tests (Real API)** - Run manually or on a schedule
- ✅ Verify real OpenAI API integration
- ✅ Catch API format changes
- ✅ Test actual response quality
- ❌ Slow (2-5 seconds per test)
- ❌ Cost money (~$0.01-0.05 per image)
- ❌ Can fail due to network/API issues

### Recommended Approach

1. **Run mocked unit tests** in CI/CD pipeline (fast feedback loop)
2. **Run integration tests** manually before releases or weekly
3. Mark integration tests with `@pytest.mark.integration` decorator
4. Skip integration tests by default unless explicitly requested

---

## Phase 1: Core Functionality Tests (with test_coffee_mug.jpeg)

### 1. Image Fingerprinting Tests (`test_fingerprinting.py`)

Tests for perceptual hashing (pHash) and MD5 hashing functionality.

- `test_calculate_phash_returns_consistent_hash` - Same image always produces same pHash
- `test_calculate_md5_returns_consistent_hash` - Same image always produces same MD5
- `test_calculate_phash_different_for_rotated_image` - Rotated image has different pHash
- `test_get_file_size_returns_correct_bytes` - File size calculation is accurate
- `test_phash_handles_different_image_formats` - Works with JPEG, PNG, WebP
- `test_md5_handles_binary_and_file_objects` - Works with both file types

**Coverage Target**: 100% (critical path)

---

### 2. OpenAI Vision API Tests (Mocked) (`test_vision_api.py`)

Tests for OpenAI GPT-4o Vision API integration (all API calls mocked).

- `test_vision_provider_analyzes_image_successfully` - Successful API call returns suggestions
- `test_vision_provider_parses_json_response` - Parse plain JSON response
- `test_vision_provider_parses_markdown_wrapped_json` - Parse JSON in markdown code blocks
- `test_vision_provider_handles_api_error` - Graceful error handling
- `test_vision_provider_returns_correct_suggestion_format` - Validates ChatSuggestion format
- `test_vision_provider_respects_max_suggestions_limit` - Returns exactly 10 suggestions
- `test_vision_provider_includes_token_usage` - Token tracking in response
- `test_get_vision_provider_returns_openai_instance` - Factory function works

**Coverage Target**: 95%

---

### 3. Rate Limiting Tests (`test_rate_limiting.py`)

Tests for Redis-based rate limiting functionality.

- `test_rate_limit_allows_first_request` - Initial request passes
- `test_rate_limit_blocks_after_limit_exceeded` - 21st request blocked (authenticated)
- `test_rate_limit_blocks_anonymous_after_5_requests` - 6th request blocked (anonymous)
- `test_rate_limit_key_prioritizes_user_id` - User ID takes precedence
- `test_rate_limit_key_falls_back_to_fingerprint` - Fingerprint used when no user
- `test_rate_limit_key_falls_back_to_ip` - IP used when no fingerprint
- `test_rate_limit_resets_after_ttl` - Counter resets after 1 hour
- `test_rate_limit_isolated_per_user` - Different users have separate limits
- `test_rate_limit_decorator_returns_429_when_exceeded` - Correct HTTP status

**Coverage Target**: 100% (critical path)

---

### 4. Deduplication Tests (`test_deduplication.py`)

Tests for dual-hash deduplication strategy (pHash + MD5).

- `test_duplicate_image_returns_cached_analysis` - Same MD5 returns existing result
- `test_duplicate_image_does_not_call_api_again` - No second API call for duplicate
- `test_duplicate_image_response_has_cached_flag` - Response includes `"cached": true`
- `test_different_image_creates_new_analysis` - Different MD5 creates new record
- `test_duplicate_increments_times_used_counter` - Usage counter incremented (future feature)

**Coverage Target**: 100% (critical path)

---

### 5. Storage Tests (Mocked S3/Local) (`test_storage.py`)

Tests for hybrid S3/local storage functionality (S3 calls mocked).

- `test_save_image_to_local_storage` - Local storage works
- `test_save_image_to_s3_storage` - S3 storage works (mocked)
- `test_retrieve_image_from_local_storage` - Can read back local file
- `test_retrieve_image_from_s3_storage` - Can read back S3 file (mocked)
- `test_storage_type_recorded_correctly` - storage_type field set correctly
- `test_expired_image_returns_410_gone` - Expired images handled

**Coverage Target**: 90%

---

### 6. API Endpoint Tests (`test_api_endpoints.py`)

Tests for DRF ViewSet endpoints (upload, recent, retrieve, image proxy).

- `test_upload_endpoint_accepts_valid_image` - Valid upload succeeds (200/201)
- `test_upload_endpoint_rejects_oversized_image` - File too large returns 400
- `test_upload_endpoint_rejects_invalid_file_type` - Non-image returns 400
- `test_upload_endpoint_requires_image_field` - Missing image returns 400
- `test_upload_endpoint_respects_rate_limit` - Rate limit enforced (429)
- `test_upload_endpoint_returns_suggestions` - Response includes suggestions array
- `test_recent_endpoint_lists_user_analyses` - Recent analyses returned
- `test_recent_endpoint_filters_by_user` - Only shows user's analyses
- `test_recent_endpoint_filters_by_fingerprint` - Anonymous filtering works
- `test_recent_endpoint_respects_limit_parameter` - Pagination works
- `test_image_proxy_endpoint_serves_image` - Image proxy returns file (200)
- `test_image_proxy_endpoint_returns_404_for_missing` - Missing analysis returns 404
- `test_image_proxy_endpoint_returns_410_for_expired` - Expired returns 410

**Coverage Target**: 100% (critical path)

---

### 7. Model Tests (`test_models.py`)

Tests for PhotoAnalysis Django model.

- `test_photo_analysis_creation` - Model creates successfully
- `test_photo_analysis_uuid_primary_key` - UUID auto-generated
- `test_photo_analysis_is_expired_returns_true_when_expired` - Expiration check works
- `test_photo_analysis_is_expired_returns_false_when_active` - Active images not expired
- `test_photo_analysis_is_expired_returns_false_when_no_expiry` - Null expiry never expires
- `test_photo_analysis_increment_usage` - Usage counter increments
- `test_photo_analysis_stores_suggestions_as_json` - JSON field works
- `test_photo_analysis_stores_user_tracking` - User/fingerprint/IP stored

**Coverage Target**: 100%

---

### 8. Serializer Tests (`test_serializers.py`)

Tests for DRF serializers (upload validation, response formatting).

- `test_photo_upload_serializer_validates_image` - Image validation works
- `test_photo_upload_serializer_rejects_large_file` - File size limit enforced
- `test_photo_upload_serializer_rejects_invalid_type` - Content type validation
- `test_chat_suggestion_serializer_format` - Suggestion structure validated
- `test_photo_analysis_detail_serializer_includes_image_url` - URL generated
- `test_photo_analysis_list_serializer_includes_count` - Suggestion count included

**Coverage Target**: 95%

---

## Phase 2: Multi-Image Tests (Future - requires multiple test images)

### 9. Perceptual Hash Comparison Tests (`test_phash_comparison.py`)

Tests for perceptual hash similarity detection.

**Requires**:
- `test_coffee_mug.jpeg` (original)
- `test_coffee_mug_resized.jpeg` (scaled version)
- `test_coffee_mug_compressed.jpeg` (lower quality)
- `test_cat.jpeg` (completely different image)

**Tests**:
- `test_similar_images_have_similar_phash` - Resized/compressed have low Hamming distance
- `test_different_images_have_different_phash` - Coffee mug vs cat have high distance
- `test_are_images_similar_returns_true_for_threshold` - Similarity threshold works
- `test_are_images_similar_returns_false_for_different` - Different images not similar
- `test_compare_phash_calculates_hamming_distance` - Distance calculation correct

**Coverage Target**: 100%

---

## Phase 3: Integration Tests (Optional - Real OpenAI API)

### 10. OpenAI Vision API Integration Tests (`test_vision_api_integration.py`)

**Purpose**: Verify real OpenAI API integration works correctly

**⚠️ Requirements**:
- Valid `OPENAI_API_KEY` in environment variables
- Costs money (~$0.01-0.05 per test run)
- Requires internet connection
- Marked with `@pytest.mark.integration` decorator

**Tests**:
- `test_integration_real_api_analyzes_image_successfully` - Real API call with test_coffee_mug.jpeg
- `test_integration_real_api_returns_10_suggestions` - Verify we get exactly 10 suggestions
- `test_integration_real_api_suggestions_have_valid_format` - Name, key, description present
- `test_integration_real_api_includes_token_usage` - Token tracking works with real API
- `test_integration_real_api_handles_rate_limit` - Graceful handling of rate limits (optional)

**How to Run**:
```bash
# Skip by default
./venv/bin/python manage.py test photo_analysis  # integration tests NOT run

# Run ONLY integration tests
pytest -m integration photo_analysis/tests/test_vision_api_integration.py

# Run ALL tests including integration
pytest photo_analysis
```

**When to Run**:
- Before major releases
- After updating OpenAI library
- Weekly/monthly (scheduled)
- When debugging OpenAI-specific issues

**Coverage Target**: N/A (integration tests don't count toward coverage)

---

## Test Utilities & Fixtures

### `tests/conftest.py` (pytest fixtures)

Shared fixtures for all test modules:

```python
import pytest
from django.contrib.auth import get_user_model
from PIL import Image
import io
import os

User = get_user_model()

@pytest.fixture
def test_image_path():
    """Returns path to test_coffee_mug.jpeg"""
    return os.path.join(os.path.dirname(__file__), 'fixtures', 'test_coffee_mug.jpeg')

@pytest.fixture
def test_image(test_image_path):
    """Returns test_coffee_mug.jpeg as file object"""
    with open(test_image_path, 'rb') as f:
        return io.BytesIO(f.read())

@pytest.fixture
def mock_openai_response():
    """Returns mock OpenAI API response with 10 suggestions"""
    return {
        "id": "chatcmpl-123",
        "choices": [{
            "message": {
                "content": '```json\n{"suggestions": [{"name": "Coffee Chat", "key": "coffee-chat", "description": "A cozy chat about coffee"}]}\n```'
            }
        }],
        "usage": {
            "prompt_tokens": 1250,
            "completion_tokens": 180,
            "total_tokens": 1430
        },
        "model": "gpt-4o"
    }

@pytest.fixture
def authenticated_user(db):
    """Creates test user"""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123'
    )

@pytest.fixture
def mock_redis(mocker):
    """Mocks Redis for rate limiting"""
    return mocker.patch('photo_analysis.utils.rate_limit.redis_client')

@pytest.fixture
def mock_s3_storage(mocker):
    """Mocks S3 storage operations"""
    return mocker.patch('chatpop.utils.media.MediaStorage.save_to_s3')
```

---

## Priority Order for Implementation

### HIGH PRIORITY (Core functionality)
Implement first to validate basic functionality:

1. ✅ **Image Fingerprinting Tests** (`test_fingerprinting.py`)
2. ✅ **Model Tests** (`test_models.py`)
3. ✅ **Serializer Tests** (`test_serializers.py`)
4. ✅ **API Endpoint Tests** (`test_api_endpoints.py` - basic upload/retrieve)

### MEDIUM PRIORITY (Business logic)
Implement after core tests pass:

5. ✅ **Deduplication Tests** (`test_deduplication.py`)
6. ✅ **Rate Limiting Tests** (`test_rate_limiting.py`)
7. ✅ **OpenAI Vision API Tests** (`test_vision_api.py` - mocked)

### LOW PRIORITY (Advanced features)
Implement last:

8. ✅ **Storage Tests** (`test_storage.py` - mocked S3)
9. ✅ **Perceptual Hash Comparison Tests** (`test_phash_comparison.py` - requires multiple images)

---

## Test Coverage Goals

### Overall Target
- **Target**: 85%+ code coverage
- **Critical paths**: 100% coverage
  - Upload endpoint
  - Deduplication logic
  - Rate limiting
  - Hash calculation

### Per-Module Targets

| Module | Target Coverage | Priority |
|--------|----------------|----------|
| `models.py` | 100% | HIGH |
| `views.py` | 100% | HIGH |
| `serializers.py` | 95% | HIGH |
| `utils/fingerprinting/` | 100% | HIGH |
| `utils/rate_limit.py` | 100% | MEDIUM |
| `utils/vision/` | 95% | MEDIUM |
| `admin.py` | 70% | LOW |

---

## Running Tests

### Run All Photo Analysis Unit Tests (Skip Integration)
```bash
cd backend
./venv/bin/python manage.py test photo_analysis
# Integration tests are automatically skipped
```

### Run Specific Test Module
```bash
./venv/bin/python manage.py test photo_analysis.tests.test_fingerprinting
```

### Run ONLY Integration Tests (Requires OPENAI_API_KEY)
```bash
# Using pytest (recommended for integration tests)
pytest -m integration photo_analysis/tests/test_vision_api_integration.py

# Single integration test
pytest -m integration photo_analysis/tests/test_vision_api_integration.py::test_integration_real_api_analyzes_image_successfully
```

### Run ALL Tests Including Integration
```bash
# WARNING: Costs money, requires API key
pytest photo_analysis
```

### Run With Coverage Report (Unit Tests Only)
```bash
coverage run --source='photo_analysis' manage.py test photo_analysis
coverage report
coverage html  # Generates HTML report in htmlcov/
```

### Run With Verbose Output
```bash
./venv/bin/python manage.py test photo_analysis -v 2
```

---

## Test Data Requirements

### Phase 1 (Current)
- ✅ `test_coffee_mug.jpeg` - Single test image

### Phase 2 (Future)
- ⏳ `test_coffee_mug_resized.jpeg` - Scaled version of original
- ⏳ `test_coffee_mug_compressed.jpeg` - Lower quality JPEG
- ⏳ `test_cat.jpeg` - Completely different subject
- ⏳ `test_landscape.png` - PNG format test
- ⏳ `test_portrait.webp` - WebP format test

---

## CI/CD Integration

### GitHub Actions Workflow (Recommended)

```yaml
name: Photo Analysis Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: test_chatpop
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432

      redis:
        image: redis:7
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt

      - name: Run migrations
        run: |
          cd backend
          python manage.py migrate

      - name: Run photo_analysis tests
        run: |
          cd backend
          python manage.py test photo_analysis
```

---

## Known Limitations & Assumptions

### Current Limitations
1. **OpenAI API calls mocked** - Real API not tested (cost/rate limits)
2. **S3 storage mocked** - AWS credentials not required for tests
3. **Single test image** - Limited perceptual hash testing

### Assumptions
1. Test database is PostgreSQL (same as production)
2. Redis is available for rate limiting tests
3. Test images are small (<1MB) for fast test execution
4. OpenAI API response format remains stable

---

## Future Enhancements

### Additional Test Scenarios
- **Load testing** - 100+ concurrent uploads
- **Stress testing** - Rate limit boundary conditions
- **Integration testing** - Full end-to-end with real OpenAI API (optional)
- **Performance testing** - Hash calculation speed benchmarks
- **Security testing** - SQL injection, XSS, CSRF in admin

### Test Infrastructure
- **Dockerized tests** - Consistent environment across machines
- **Parallel test execution** - Faster CI/CD pipeline
- **Mutation testing** - Verify test quality with mutmut
- **Property-based testing** - Hypothesis for edge cases

---

## Maintenance

### Updating Tests
When modifying code, update corresponding tests:
1. Add new test for new feature
2. Update existing tests for changed behavior
3. Run full test suite before committing
4. Ensure coverage doesn't decrease

### Test Review Checklist
- [ ] All tests pass locally
- [ ] Coverage target met (85%+)
- [ ] No skipped tests without explanation
- [ ] Mocks properly isolated
- [ ] Test names clearly describe intent
- [ ] Fixtures reused where appropriate

---

## References

- [Django Testing Documentation](https://docs.djangoproject.com/en/5.0/topics/testing/)
- [DRF Testing Guide](https://www.django-rest-framework.org/api-guide/testing/)
- [pytest-django Documentation](https://pytest-django.readthedocs.io/)
- [Coverage.py Documentation](https://coverage.readthedocs.io/)

---

**Last Updated**: 2025-10-22
**Status**: Phase 1 & 2 completed (all unit tests implemented)
