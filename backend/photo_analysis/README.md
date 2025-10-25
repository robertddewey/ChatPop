# Photo Analysis API

AI-powered photo analysis for generating contextual chat room name suggestions. Uses OpenAI GPT-4o Vision API to analyze uploaded images and suggest 10 relevant chat room names with descriptions. Features collaborative discovery via pgvector similarity search to find existing active chat rooms with similar content.

## Features

- **AI Vision Analysis**: OpenAI GPT-4o analyzes photos to generate contextual suggestions
- **Collaborative Discovery**: pgvector-powered similarity search finds existing active chat rooms from similar photos
- **Dual Embedding System**: Two specialized embeddings for semantic clustering and conversation matching
- **Caption Generation**: Parallel AI caption generation for richer semantic understanding
- **Dual-Hash Deduplication**: Perceptual hashing (pHash) and MD5 to prevent duplicate processing
- **Hybrid Storage**: S3 or local filesystem storage with automatic management
- **Rate Limiting**: Redis-based rate limiting (20/hour authenticated, 5/hour anonymous)
- **Image Expiration**: Automatic cleanup of expired images (default: 7 days TTL)
- **RESTful API**: Django REST Framework endpoints with comprehensive serializers
- **Admin Interface**: Read-only Django admin with image previews and detailed inspection

## API Endpoints

### Upload and Analyze Photo

**POST** `/api/photo-analysis/upload/`

Uploads a photo and returns AI-generated chat room name suggestions plus similar existing rooms.

**Request** (multipart/form-data):
```
image: [Image file - required] (JPEG, PNG, WebP, GIF, HEIC)
fingerprint: [Browser fingerprint - optional]
```

**Response** (200 OK or 201 Created):
```json
{
  "cached": false,
  "analysis": {
    "id": "uuid",
    "suggestions": [
      {
        "name": "Curious Cat",
        "key": "curious-cat",
        "description": "A cozy space for inquisitive minds"
      },
      ...
    ],
    "ai_vision_model": "gpt-4o",
    "token_usage": {
      "prompt_tokens": 1250,
      "completion_tokens": 180,
      "total_tokens": 1430
    },
    "caption_title": "Coffee Break",
    "caption_category": "Food & Drink",
    "caption_visible_text": "COFFEE TIME",
    "caption_full": "A warm cup of coffee on a wooden table with steam rising",
    "caption_model": "gpt-4o",
    "caption_token_usage": {
      "prompt_tokens": 150,
      "completion_tokens": 25,
      "total_tokens": 175
    },
    "caption_embedding_generated_at": "2025-10-22T12:00:05Z",
    "suggestions_embedding_generated_at": "2025-10-22T12:00:06Z",
    "image_url": "https://localhost:9000/api/photo-analysis/{id}/image/",
    "expires_at": "2025-10-29T12:00:00Z",
    "is_expired": false,
    "file_size": 245632,
    "storage_type": "s3",
    "created_at": "2025-10-22T12:00:00Z"
  },
  "similar_rooms": [
    {
      "room_id": "uuid-456",
      "room_code": "coffee-lovers",
      "room_name": "Coffee Lovers",
      "room_url": "/chat/discover/coffee-lovers",
      "active_users": 5,
      "similarity_distance": 0.12,
      "source_photo_id": "uuid-789"
    },
    ...
  ]
}
```

**Rate Limiting**: Returns `429 Too Many Requests` if rate limit exceeded.

**Error Responses**:
- `400 Bad Request`: Invalid image or validation error
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: OpenAI API failure or storage error
- `503 Service Unavailable`: OpenAI API not configured

### Get Specific Analysis

**GET** `/api/photo-analysis/{id}/`

Retrieves details for a specific photo analysis.

**Response** (200 OK):
```json
{
  "id": "uuid",
  "suggestions": [...],
  "ai_vision_model": "gpt-4o",
  "token_usage": {...},
  "caption_title": "Coffee Break",
  "caption_category": "Food & Drink",
  "caption_visible_text": "COFFEE TIME",
  "caption_full": "A warm cup of coffee on a wooden table with steam rising",
  "caption_generated_at": "2025-10-22T12:00:05Z",
  "caption_model": "gpt-4o",
  "caption_token_usage": {...},
  "caption_embedding_generated_at": "2025-10-22T12:00:05Z",
  "suggestions_embedding_generated_at": "2025-10-22T12:00:06Z",
  "image_url": "...",
  "expires_at": "...",
  "is_expired": false,
  "file_size": 245632,
  "storage_type": "s3",
  "times_used": 3,
  "username": "user123",
  "created_at": "..."
}
```

### List Recent Analyses

**GET** `/api/photo-analysis/recent/`

Lists recent analyses for the current user/fingerprint.

**Query Parameters**:
- `fingerprint`: Browser fingerprint (required for anonymous users)
- `limit`: Number of results (default: 10, max: 50)

**Response** (200 OK):
```json
[
  {
    "id": "uuid",
    "suggestion_count": 10,
    "ai_vision_model": "gpt-4o",
    "times_used": 3,
    "username": "user123",
    "created_at": "..."
  },
  ...
]
```

### Get Image via Proxy

**GET** `/api/photo-analysis/{id}/image/`

Serves the image file via Django proxy (secure, no direct S3/local path exposure).

**Response**:
- `200 OK`: Image file (Content-Type: image/jpeg, image/png, etc.)
- `404 Not Found`: Analysis or image not found
- `410 Gone`: Image has expired

## Configuration

All settings are configurable via Django admin (Constance):

### OpenAI Settings
- `PHOTO_ANALYSIS_OPENAI_MODEL`: Default: `"gpt-4o"`
- `PHOTO_ANALYSIS_PROMPT`: AI prompt for generating suggestions (see settings.py for default)
- `PHOTO_ANALYSIS_TEMPERATURE`: Temperature for suggestions (0.0-2.0), Default: `0.7`
- `PHOTO_ANALYSIS_MAX_MEGAPIXELS`: Max image resolution before resize, Default: `2.0` (reduces token costs)

### Caption Generation
- `PHOTO_ANALYSIS_ENABLE_CAPTIONS`: Enable caption generation for embeddings, Default: `True`
- `PHOTO_ANALYSIS_CAPTION_MODEL`: AI model for captions, Default: `"gpt-4o"`
- `PHOTO_ANALYSIS_CAPTION_TEMPERATURE`: Temperature for captions (0.0-2.0), Default: `0.2` (more factual for embeddings)

### Similarity Search (Collaborative Discovery)
- `PHOTO_SIMILARITY_MAX_DISTANCE`: Maximum cosine distance for similar rooms (0.0-1.0), Default: `0.3`
  - Lower = stricter matching
  - `<0.2` very similar, `<0.3` similar (recommended), `<0.4` somewhat similar, `<0.5` loosely related
- `PHOTO_SIMILARITY_MAX_RESULTS`: Maximum similar rooms to return, Default: `5`
- `PHOTO_SIMILARITY_MIN_USERS`: Minimum active users required to recommend a room, Default: `1`

### Rate Limiting
- `PHOTO_ANALYSIS_RATE_LIMIT_AUTHENTICATED`: Default: `20` requests/hour
- `PHOTO_ANALYSIS_RATE_LIMIT_ANONYMOUS`: Default: `5` requests/hour
- `PHOTO_ANALYSIS_ENABLE_RATE_LIMITING`: Default: `True`

### File Storage
- `PHOTO_ANALYSIS_MAX_FILE_SIZE_MB`: Default: `10` MB
- `PHOTO_ANALYSIS_IMAGE_TTL_HOURS`: Default: `168` (7 days)
- `PHOTO_ANALYSIS_USE_S3`: Default: `True` (uses local storage if S3 not configured)

## Database Schema

### PhotoAnalysis Model

**Primary Fields**:
- `id`: UUID (primary key)
- `image_phash`: Perceptual hash (64 chars, indexed)
- `file_hash`: MD5 hash (64 chars, indexed)
- `file_size`: Size in bytes
- `image_path`: Storage path (S3 key or local path)
- `storage_type`: `'s3'` or `'local'`
- `expires_at`: Expiration timestamp (nullable)

**Analysis Results**:
- `suggestions`: JSONField with array of suggestion objects
- `raw_response`: Complete API response (JSONField)
- `ai_vision_model`: Model identifier (e.g., "gpt-4o")
- `token_usage`: API cost tracking (JSONField)

**Caption Fields** (for embeddings):
- `caption_title`: Short title extracted from image
- `caption_category`: Category classification (e.g., "Food & Drink")
- `caption_visible_text`: Any text visible in the image (OCR-like)
- `caption_full`: Full descriptive caption
- `caption_generated_at`: Timestamp when captions were generated
- `caption_model`: AI model used for caption generation
- `caption_token_usage`: Token usage for caption generation (JSONField)
- `caption_raw_response`: Complete caption API response (JSONField)

**Embedding Fields** (dual system):
- `caption_embedding`: VectorField(1536) - Embedding 1: Semantic/Content clustering
- `caption_embedding_generated_at`: Timestamp for caption embedding
- `suggestions_embedding`: VectorField(1536) - Embedding 2: Conversational/Topic clustering (PRIMARY for collaborative discovery)
- `suggestions_embedding_generated_at`: Timestamp for suggestions embedding

**Room Selection Tracking**:
- `selected_suggestion_code`: Room code selected by user (e.g., 'coffee-chat')
- `selected_at`: Timestamp when user selected a room
- `times_used`: Counter for how many times suggestions were used

**User Tracking**:
- `user`: ForeignKey to User (nullable)
- `fingerprint`: Browser fingerprint (nullable, indexed)
- `ip_address`: IP address (GenericIPAddressField, indexed)

**Timestamps**:
- `created_at`: Auto-added timestamp
- `updated_at`: Auto-updated timestamp

**Indexes**:
- Composite: `(image_phash, created_at)`
- Composite: `(file_hash, created_at)`
- Composite: `(fingerprint, ip_address)`
- Single: `expires_at`
- pgvector HNSW: `caption_embedding` (for fast similarity search)
- pgvector HNSW: `suggestions_embedding` (for fast similarity search)

## Dual Embedding System

### Overview

Two specialized embeddings are generated in parallel for different clustering purposes:

### Embedding 1: Caption/Semantic (Broad Categorization)

**Purpose**: Groups photos by visual content and semantics

**Source Data**: Caption fields (title + category + visible_text + full caption)

**Use Cases**:
- Grouping photos of similar objects (all coffee photos together)
- Semantic search by visual content
- Broad topic categorization

**Model**: `text-embedding-3-small` (1536 dimensions)

**Storage**: `caption_embedding` field

### Embedding 2: Suggestions/Topic (PRIMARY for Collaborative Discovery)

**Purpose**: Groups photos by conversation potential and chat topic similarity

**Source Data**: Caption fields + all 10 suggestion names + all 10 descriptions

**Use Cases**:
- Finding existing chat rooms with similar topics
- Collaborative discovery (e.g., "bar-room", "happy-hour", "brew-talk" cluster together)
- Topic-based recommendations

**Model**: `text-embedding-3-small` (1536 dimensions)

**Storage**: `suggestions_embedding` field

**Why It's PRIMARY**: This embedding captures the intended *conversation topics* rather than just visual similarity, making it ideal for matching users to existing active discussions.

### Parallel Generation

Both embeddings are generated simultaneously using `ThreadPoolExecutor` to minimize latency:

```python
with ThreadPoolExecutor(max_workers=2) as executor:
    future_caption_embedding = executor.submit(generate_embedding, caption_data)
    future_suggestions_embedding = executor.submit(generate_suggestions_embedding, caption_data, suggestions)
    # Wait for both to complete
```

## Collaborative Discovery (Similarity Search)

### How It Works

1. **Generate Suggestions Embedding**: When a photo is uploaded, the suggestions_embedding is created from captions + all 10 chat name suggestions
2. **Query Similar Photos**: Use pgvector's cosine distance to find photos with similar embeddings
3. **Find Active Rooms**: Look up chat rooms created from those similar photos
4. **Filter by Activity**: Only return rooms with active users (last_seen_at within 24h)
5. **Rank by Similarity**: Order results by cosine distance (closest first)

### Implementation

Located in `backend/photo_analysis/utils/similarity.py`:

```python
from photo_analysis.utils.similarity import find_similar_rooms

# Find up to 5 similar active rooms
similar_rooms = find_similar_rooms(
    embedding_vector=photo_analysis.suggestions_embedding,
    exclude_photo_id=str(photo_analysis.id)
)

# Returns list of SimilarRoom objects with:
# - room_id, room_code, room_name, room_url
# - active_users (count with last_seen_at within 24h)
# - similarity_distance (0.0 = identical, 1.0 = opposite)
# - source_photo_id (which photo matched this room)
```

### Response Format

Similar rooms are included in the upload response:

```json
{
  "analysis": { /* PhotoAnalysis data */ },
  "similar_rooms": [
    {
      "room_id": "uuid-456",
      "room_code": "coffee-lovers",
      "room_name": "Coffee Lovers",
      "room_url": "/chat/discover/coffee-lovers",
      "active_users": 5,
      "similarity_distance": 0.12,
      "source_photo_id": "uuid-789"
    }
  ]
}
```

## Deduplication Strategy

### 1. Exact Duplicate Detection (MD5)
```python
# Check if exact same file was already analyzed
existing = PhotoAnalysis.objects.filter(file_hash=md5_hash).first()
if existing:
    return cached_response(existing)
```

### 2. Perceptual Hash (pHash)
Used for detecting visually similar images:
```python
from photo_analysis.utils.fingerprinting.image_hash import are_images_similar

# Find visually similar images (threshold = hamming distance)
similar = PhotoAnalysis.objects.filter(
    image_phash__in=get_similar_hashes(current_phash, threshold=5)
)
```

## Image Storage

Uses the project-level `MediaStorage` utility (`chatpop.utils.media`):

### S3 Storage (Default)
```python
from chatpop.utils.media import MediaStorage

storage_path, storage_type = MediaStorage.save_file(
    file_obj=image_file,
    directory='photo_analysis',
    filename=f"{uuid}.jpg"
)
# Returns: ('photo_analysis/uuid.jpg', 's3')
```

### Local Storage (Fallback)
Automatically used if S3 is not configured or fails.

## Rate Limiting

Redis-based rate limiting with priority-based client identification:

**Priority**: `user_id` > `fingerprint` > `ip_address`

```python
from photo_analysis.utils.rate_limit import check_rate_limit

allowed, current, limit = check_rate_limit(user_id, fingerprint, ip_address)
if not allowed:
    return Response(
        {"error": f"Rate limit exceeded: {current}/{limit} requests per hour"},
        status=429
    )
```

## Management Commands

### Cleanup Expired Images

Deletes expired photo analysis records and their associated image files:

```bash
# Preview what would be deleted without actually deleting
./venv/bin/python manage.py cleanup_expired_photos --dry-run

# Actually delete expired photos
./venv/bin/python manage.py cleanup_expired_photos

# Process in smaller batches (default is 100)
./venv/bin/python manage.py cleanup_expired_photos --batch-size=50
```

**What it does**:
1. Queries all expired photos (`expires_at < now()`)
2. Deletes files from S3 or local storage
3. Deletes database records
4. Provides detailed summary with counts

**Best Practice**: Run with `--dry-run` first to preview what will be deleted.

### Test Photo Upload (End-to-End Testing)

Tests the complete photo analysis pipeline with real images from test fixtures:

```bash
# List available test images
./venv/bin/python manage.py test_photo_upload --list

# Upload a test image (creates real database record and API calls)
./venv/bin/python manage.py test_photo_upload test_coffee_mug.jpeg

# Force fresh API calls (skip cache, delete existing analysis for this image)
./venv/bin/python manage.py test_photo_upload test_coffee_mug.jpeg --no-cache

# Test with custom fingerprint (useful for rate limiting tests)
./venv/bin/python manage.py test_photo_upload test_coffee_mug.jpeg --fingerprint my-test-fp
```

**What it does**:
1. Reads image from `photo_analysis/tests/fixtures/`
2. Optionally deletes cached analysis if `--no-cache` is set
3. POSTs to `/api/photo-analysis/upload/` endpoint
4. Creates actual database record and calls OpenAI API
5. Displays comprehensive results with colored output

**Output includes**:
- HTTP status code and full JSON response
- Cached status (duplicate detection)
- Analysis details (pHash, MD5, file size, storage type)
- AI model used and token usage breakdown
- All 10 chat name suggestions with descriptions
- **Similar Existing Rooms** (collaborative discovery results)
- Caption data (title, category, visible text, full caption)
- Embedding generation status (both caption and suggestions embeddings)
- Rate limit information (used/remaining)
- Database record ID

**Example output**:
```
================================================================================
PHOTO ANALYSIS END-TO-END TEST
================================================================================

Image: test_coffee_mug.jpeg
Size: 1607.25 KB
Content-Type: image/jpeg
Fingerprint: cli-test-fp

POSTing to /api/photo-analysis/upload/...

================================================================================
RESPONSE
================================================================================

Status Code: 201

{
  "cached": false,
  "analysis": {
    "id": "abc-123-uuid",
    "image_phash": "f8e4c2...",
    "suggestions": [...],
    ...
  },
  "similar_rooms": [
    {
      "room_name": "Coffee Lovers",
      "room_code": "coffee-lovers",
      "active_users": 3,
      "similarity_distance": 0.15,
      ...
    }
  ]
}

================================================================================
KEY INFORMATION
================================================================================

Cached: False
Analysis ID: abc-123-uuid
Model: gpt-4o
Image pHash: f8e4c2...
File MD5: a1b2c3...
File Size: 1645817 bytes
Storage: local
Times Used: 0

Token Usage:
  Prompt: 1250
  Completion: 180
  Total: 1430

Suggestions Count: 10

Chat Name Suggestions:
  1. Coffee Break Chat (key: coffee-break-chat)
     A cozy space for coffee lovers
  2. Brew Crew Discussions (key: brew-crew-discussions)
     Share your favorite blends
  ...

Similar Existing Rooms (Collaborative Discovery): 2 found
  1. Coffee Lovers (3 active users)
     Code: coffee-lovers
     URL: /chat/discover/coffee-lovers
     Similarity: 0.1523 (cosine distance)
     Source Photo ID: def-456-uuid
  2. Morning Brew (1 active user)
     Code: morning-brew
     URL: /chat/discover/morning-brew
     Similarity: 0.2145 (cosine distance)
     Source Photo ID: ghi-789-uuid

Caption Data (for embeddings):
  Title: Coffee Mug
  Category: Food & Drink
  Visible Text: "COFFEE TIME"
  Full Caption: A warm cup of coffee on a wooden table with steam rising
  Model: gpt-4o
  Generated At: 2025-10-22T12:00:05Z

Caption Token Usage:
  Prompt: 150
  Completion: 25
  Total: 175

✓ Embedding 1 (Caption/Semantic): Generated
  Dimensions: 1536 (text-embedding-3-small)
  Generated At: 2025-10-22T12:00:05Z
  Source: caption fields (title, category, visible_text, full)
  Purpose: Broad categorization by visual content

✓ Embedding 2 (Suggestions/Topic - PRIMARY): Generated
  Dimensions: 1536 (text-embedding-3-small)
  Generated At: 2025-10-22T12:00:06Z
  Source: captions + all 10 suggestion names + descriptions
  Purpose: Collaborative discovery - finding similar chat rooms
  How: "bar-room", "happy-hour", "brew-talk" cluster together

Rate Limit:
  Used: 1 / 20
  Remaining: 19

================================================================================
✓ Upload successful!
================================================================================
```

**Use cases**:
- End-to-end testing of the photo analysis pipeline
- Verifying OpenAI API integration
- Testing deduplication (upload same image twice to see caching)
- Testing caption generation and embedding creation
- Testing collaborative discovery (similarity search)
- Testing rate limiting with custom fingerprints
- Debugging storage configuration (S3 vs local)
- Validating database record creation
- Forcing fresh API calls with `--no-cache`

**Note**: This command makes real API calls to OpenAI (incurs costs) and creates actual database records. Use test fixtures from `tests/fixtures/` directory.

## Admin Interface

Access via Django admin at `/admin/photo_analysis/photoanalysis/`

**Features**:
- Read-only interface (no add/edit permissions)
- Image previews directly in admin
- Formatted suggestion display
- Caption data display
- Embedding generation status
- Token usage tracking
- Expiration status indicators
- Link to view full-size image

**List View**:
- Short ID, Created date, AI model, Suggestion count, Times used
- User display (username or anonymous fingerprint)
- Storage type, Expiration status, Image link
- Selection tracking (selected_suggestion_code, selected_at)

**Detail View**:
- Image preview (max 400x300px)
- All suggestion details with descriptions
- Caption data (title, category, visible text, full caption)
- Embedding generation timestamps
- Token usage breakdown (prompt/completion/total for both suggestions and captions)
- Raw API responses (collapsible JSON)
- File hashes and fingerprints
- Selection tracking information

## Error Handling

### Upload Endpoint Errors

**Validation Errors (400)**:
```json
{
  "image": ["Image file too large. Maximum size is 10MB."],
  "fingerprint": ["This field may not be blank."]
}
```

**Rate Limit Exceeded (429)**:
```json
{
  "error": "Rate limit exceeded",
  "detail": "You have made 21 requests in the last hour. Limit: 20/hour.",
  "retry_after": 3462
}
```

**OpenAI API Failure (500)**:
```json
{
  "error": "Photo analysis failed",
  "detail": "OpenAI API error: Rate limit exceeded"
}
```

### Image Proxy Errors

**Expired Image (410)**:
```json
{
  "error": "Image has expired"
}
```

**Not Found (404)**:
```json
{
  "detail": "Not found."
}
```

## Development

### Running Tests

```bash
cd backend
./venv/bin/python manage.py test photo_analysis
```

### Viewing Logs

```bash
# Django logs (photo analysis activity)
tail -f /path/to/django.log | grep photo_analysis

# Redis rate limiting
redis-cli -p 6381
> KEYS photo_analysis:rate_limit:*
> TTL photo_analysis:rate_limit:user:123
```

### Local Development

1. **Ensure PostgreSQL with pgvector extension**:
   ```bash
   docker-compose up -d
   # Connect to PostgreSQL
   docker exec -it chatpop-postgres psql -U chatpop -d chatpop
   # Enable pgvector
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

2. **Ensure Redis is running**:
   ```bash
   docker-compose up -d
   ```

3. **Set OpenAI API key** in `.env`:
   ```
   OPENAI_API_KEY=sk-...
   ```

4. **Run migrations**:
   ```bash
   ./venv/bin/python manage.py migrate
   ```

5. **Configure Constance** via admin at `/admin/constance/config/`

## Architecture

### File Structure

```
photo_analysis/
├── __init__.py
├── apps.py
├── models.py                # PhotoAnalysis model with vector fields
├── views.py                 # DRF ViewSet with collaborative discovery
├── serializers.py           # DRF serializers including SimilarRoomSerializer
├── urls.py                  # URL routing
├── admin.py                 # Django admin config
├── migrations/
│   └── 0001_initial.py
├── management/
│   └── commands/
│       ├── cleanup_expired_photos.py  # Cleanup expired images
│       └── test_photo_upload.py       # End-to-end testing tool
├── utils/
│   ├── fingerprinting/
│   │   ├── image_hash.py    # Perceptual hashing (pHash)
│   │   └── file_hash.py     # MD5/SHA256 hashing
│   ├── vision/
│   │   ├── base.py          # Abstract VisionProvider interface
│   │   └── openai_vision.py # OpenAI GPT-4o implementation
│   ├── caption.py           # Caption generation for embeddings
│   ├── embedding.py         # Dual embedding system (caption + suggestions)
│   ├── similarity.py        # pgvector similarity search
│   └── rate_limit.py        # Redis-based rate limiting
└── README.md                # This file
```

### Data Flow

1. **Upload Request** → `PhotoAnalysisViewSet.upload()`
2. **Calculate Hashes** → pHash + MD5
3. **Check Cache** → Query existing analysis by file_hash
4. **Rate Limit Check** → Redis lookup with TTL
5. **Parallel AI Analysis** → Two simultaneous API calls:
   - **Thread 1**: Vision API for suggestions (required)
   - **Thread 2**: Vision API for captions (optional, for embeddings)
6. **Generate Embeddings** → Two parallel embedding generations:
   - **Embedding 1**: Caption/Semantic (from caption fields)
   - **Embedding 2**: Suggestions/Topic (from captions + all suggestions)
7. **Similarity Search** → pgvector query for similar existing rooms
8. **Store Image** → S3 or local filesystem
9. **Save to DB** → Create PhotoAnalysis record with vectors
10. **Return Response** → Suggestions + similar_rooms + metadata

### Dependencies

**Python Packages**:
- `imagehash==4.3.2` - Perceptual hashing
- `openai==1.x` - OpenAI API client
- `pillow==12.0.0` - Image processing
- `numpy==2.3.4` - imagehash dependency
- `scipy==1.16.2` - imagehash dependency
- `PyWavelets==1.9.0` - imagehash dependency
- `pgvector` - PostgreSQL vector similarity extension

**Django Apps**:
- `django-rest-framework` - REST API
- `django-constance` - Dynamic settings
- `redis` - Rate limiting and caching
- `pgvector-django` - Vector field support

## Future Enhancements

1. **Batch Upload**: Analyze multiple photos in one request
2. **Custom Prompts**: Allow users to customize AI analysis prompt
3. **Image Moderation**: Content filtering before analysis
4. **Analytics Dashboard**: Track usage metrics and popular suggestions
5. **WebSocket Notifications**: Real-time progress updates for long-running analyses
6. **Image Optimization**: Automatic compression/resizing before storage (currently resizes to 2MP before API call)
7. **Multi-Provider Support**: Add Claude, Gemini, etc. via abstract interface
8. **Advanced Similarity**: Combine vector similarity with content-based filtering

## Troubleshooting

### "OpenAI API not configured" (503)

**Cause**: `OPENAI_API_KEY` not set in environment variables.

**Fix**: Add to `backend/.env`:
```
OPENAI_API_KEY=sk-...
```

### "Rate limit exceeded" (429)

**Cause**: Too many requests from the same user/fingerprint/IP.

**Fix**:
- Wait for rate limit window to reset (1 hour)
- Increase limits in Django admin (Constance settings)
- Disable rate limiting temporarily: `PHOTO_ANALYSIS_ENABLE_RATE_LIMITING = False`

### "Image has expired" (410)

**Cause**: Image TTL has passed.

**Fix**:
- Upload photo again
- Increase TTL: `PHOTO_ANALYSIS_IMAGE_TTL_HOURS = 336` (14 days)

### "Failed to retrieve image" (500)

**Cause**:
- S3 bucket not accessible
- Local file deleted
- Storage configuration mismatch

**Fix**:
- Check S3 credentials (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
- Verify `PHOTO_ANALYSIS_USE_S3` setting matches actual storage
- Check file permissions for local storage

### "Image file too large" (400)

**Cause**: File exceeds `PHOTO_ANALYSIS_MAX_FILE_SIZE_MB`.

**Fix**:
- Compress image before upload
- Increase limit in Django admin: `PHOTO_ANALYSIS_MAX_FILE_SIZE_MB = 20`

### "type vector does not exist" (Database Error)

**Cause**: pgvector extension not installed in PostgreSQL.

**Fix**:
```bash
# Connect to PostgreSQL
docker exec -it chatpop-postgres psql -U chatpop -d chatpop

# Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
```

## License

Part of the ChatPop project. See main repository for license information.

## Related Documentation

- [Main README](/README.md)
- [PHOTO_ANALYSIS.md](/docs/PHOTO_ANALYSIS.md) - Complete specification
- [REFACTOR_MEDIA_STORAGE.md](/docs/REFACTOR_MEDIA_STORAGE.md) - MediaStorage utilities
- [Backend Setup](/backend/README.md)
