# Image Description & Embedding Pipeline

## Overview

This document outlines the architecture for generating semantic embeddings from uploaded images to enable intelligent, overlapping chat room suggestions for visually or semantically similar photos.

---

## Core Goal

**Enable semantic similarity between uploaded images** so that when two users upload related images (e.g., beer bottles, bar scenes, movie posters), they receive overlapping chat room name suggestions because their image embeddings are close in vector space.

**Example Scenario:**
- User A uploads: Photo of Budweiser bottle → Suggestions: "Beer Chat", "Brew Talk", "Hoppy Hour"
- User B uploads: Photo of Heineken bottle → Suggestions: "Beer Chat", "Brew Talk", "Craft Corner"
- **Overlap**: "Beer Chat", "Brew Talk" (because embeddings recognize both as beer-related)

---

## Architecture Pipeline

### Step 1: Image Upload & Storage
**Current State:** ✅ Already implemented in `photo_analysis` app
- Image stored via `MediaStorage` (S3 or local)
- MD5 + pHash deduplication prevents duplicate API calls
- Image resized to 2.0 MP max for cost optimization

### Step 2: Caption Generation (NEW)
**Goal:** Generate structured semantic description of the image

**LLM:** GPT-4o-mini (temperature=0.2)

**Prompt:**
```
You are an expert visual captioner for a multimodal search system.
Your goal is to produce one or two compact, factual sentences that capture the full meaning of the image
for use in a text embedding model. The first sentence should describe what is visually present.
The second, if helpful, should add semantic or contextual meaning (e.g., what it represents, its purpose, or its genre).
Include any visible text, titles, brand names, or labels.
Avoid speculation, humor, or opinions. Do not include camera details.
Return a JSON object:
{
  "title": "string",
  "category": "string",
  "visible_text": "string",
  "caption": "string"  // one or two concise sentences optimized for semantic embeddings
}
```

**Example Output:**
```json
{
  "title": "Budweiser",
  "category": "beer bottle",
  "visible_text": "Budweiser, King of Beers",
  "caption": "Budweiser beer bottle labeled 'King of Beers' with red and white logo on a wooden table. A classic American lager brand known for mainstream beer culture."
}
```

**Cost Estimate:**
- GPT-4o-mini: $0.150/1M input tokens, $0.600/1M output tokens
- Typical image (resized to 2.0 MP, low detail): ~85 tokens
- Prompt: ~100 tokens
- Response: ~50 tokens
- **Cost per image:** ~$0.0001 (very cheap)

### Step 3: Embedding Generation (NEW)
**Goal:** Convert caption text into a dense vector for semantic search

**Model Options:**

| Model | Dimensions | Cost | Pros | Cons |
|-------|-----------|------|------|------|
| **OpenAI text-embedding-3-small** | 1536 | $0.02/1M tokens | Fast, high quality, OpenAI ecosystem | Requires API call |
| **OpenAI text-embedding-3-large** | 3072 | $0.13/1M tokens | Best quality | More expensive, larger vectors |
| **Amazon Titan Text Embeddings** | 1024 | $0.0001/1K tokens | AWS ecosystem, cheap | Requires AWS Bedrock |
| **Open-source (sentence-transformers)** | 384-768 | Free (self-hosted) | No API cost | Requires GPU, maintenance |

**Recommended:** **OpenAI text-embedding-3-small**
- Best balance of quality, cost, and simplicity
- 1536 dimensions fits well in pgvector
- ~$0.00001 per embedding (extremely cheap)

**Input:** Only the `caption` field (optimized for semantic meaning)

**Example:**
```python
import openai

caption = "Budweiser beer bottle labeled 'King of Beers' with red and white logo on a wooden table."
response = openai.embeddings.create(
    model="text-embedding-3-small",
    input=caption
)
embedding = response.data[0].embedding  # 1536-dimensional vector
```

### Step 4: Vector Storage (NEW)
**Goal:** Store embeddings in a queryable vector database

**Option 1: pgvector (PostgreSQL Extension)** ✅ **RECOMMENDED**
- **Pros:**
  - Already using PostgreSQL
  - No additional infrastructure
  - ACID transactions
  - Simple setup: `CREATE EXTENSION vector;`
  - Supports cosine similarity, L2 distance, inner product
  - Good for <1M vectors
- **Cons:**
  - Slower than specialized vector DBs at massive scale (>10M vectors)
  - Limited indexing strategies (IVFFlat, HNSW)

**Option 2: OpenSearch Serverless (AWS)**
- **Pros:** Fully managed, scales to billions of vectors, built-in k-NN
- **Cons:** Additional AWS cost (~$700/month minimum), extra infrastructure

**Option 3: Pinecone / Weaviate / Qdrant**
- **Pros:** Purpose-built for vectors, excellent performance
- **Cons:** Additional SaaS cost, vendor lock-in

**Decision:** Start with **pgvector** for simplicity and cost. Migrate to OpenSearch/Pinecone later if scale demands it.

**Database Schema Addition:**
```sql
-- Install pgvector extension (run once)
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding column to PhotoAnalysis model
ALTER TABLE photo_analysis_photoanalysis
ADD COLUMN embedding vector(1536);  -- 1536 dimensions for text-embedding-3-small

-- Create index for fast similarity search
CREATE INDEX ON photo_analysis_photoanalysis
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);  -- Tune based on dataset size
```

**Django Model Update:**
```python
from pgvector.django import VectorField

class PhotoAnalysis(models.Model):
    # ... existing fields ...

    # NEW: Caption and embedding fields
    caption_title = models.CharField(max_length=255, blank=True)
    caption_category = models.CharField(max_length=100, blank=True)
    caption_visible_text = models.TextField(blank=True)
    caption_full = models.TextField(blank=True)  # The full caption used for embedding

    embedding = VectorField(dimensions=1536, null=True, blank=True)
    embedding_model = models.CharField(max_length=100, default='text-embedding-3-small')

    # Metadata
    caption_generated_at = models.DateTimeField(null=True, blank=True)
    embedding_generated_at = models.DateTimeField(null=True, blank=True)
```

### Step 5: Similarity Search (NEW)
**Goal:** Find k-nearest neighbors for new images

**Query Process:**
1. New image uploaded → Generate caption → Create embedding
2. Search for similar embeddings in database
3. Retrieve top-k matches (e.g., top 10) with similarity > threshold

**PostgreSQL Query (using pgvector):**
```sql
-- Find 10 most similar images
SELECT
    id,
    caption_full,
    suggestions,
    1 - (embedding <=> $1::vector) AS similarity
FROM photo_analysis_photoanalysis
WHERE embedding IS NOT NULL
ORDER BY embedding <=> $1::vector  -- Cosine distance
LIMIT 10;
```

**Django ORM:**
```python
from pgvector.django import CosineDistance

# Find similar images
similar_images = PhotoAnalysis.objects.filter(
    embedding__isnull=False
).annotate(
    distance=CosineDistance('embedding', new_embedding)
).order_by('distance')[:10]

# Filter by similarity threshold (e.g., 0.7+)
similar_images = [img for img in similar_images if (1 - img.distance) > 0.7]
```

### Step 6: Chat Room Suggestion Synthesis (NEW)
**Goal:** Merge suggestions from similar images to create overlapping recommendations

**Strategy Options:**

**Option A: Weighted Frequency Scoring**
```python
from collections import Counter

def synthesize_suggestions(new_suggestions, similar_images, threshold=0.7):
    """
    Merge suggestions from similar images using weighted frequency.

    Args:
        new_suggestions: List of suggestions from current image
        similar_images: List of similar PhotoAnalysis objects with .distance
        threshold: Minimum similarity to consider (0.0-1.0)

    Returns:
        List of suggested room names, sorted by relevance
    """
    suggestion_scores = Counter()

    # Add new suggestions (highest weight)
    for suggestion in new_suggestions:
        suggestion_scores[suggestion['key']] += 10.0

    # Add suggestions from similar images (weighted by similarity)
    for similar_img in similar_images:
        similarity = 1 - similar_img.distance
        if similarity < threshold:
            continue

        for suggestion in similar_img.suggestions.get('suggestions', []):
            # Weight by similarity score
            suggestion_scores[suggestion['key']] += similarity * 5.0

    # Sort by score and return top suggestions
    sorted_suggestions = sorted(
        suggestion_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )

    return [key for key, score in sorted_suggestions[:10]]
```

**Option B: Cluster-Based Suggestions**
- Pre-compute clusters of similar images
- Assign each cluster a set of "canonical" room suggestions
- New images inherit suggestions from their cluster

**Option C: Hybrid (Recommended)**
- Use GPT-4o to generate initial suggestions (as currently implemented)
- Boost/promote suggestions that appear in similar images
- This creates organic overlap while still allowing unique suggestions

**Example Flow:**
```python
# 1. Generate base suggestions with GPT-4o (existing logic)
base_suggestions = vision_provider.analyze_image(...)

# 2. Find similar images
similar_images = PhotoAnalysis.objects.filter(
    embedding__isnull=False
).annotate(
    distance=CosineDistance('embedding', new_embedding)
).order_by('distance')[:10]

# 3. Extract suggestions from similar images
similar_suggestions = []
for img in similar_images:
    similarity = 1 - img.distance
    if similarity > 0.7:  # Only high-similarity matches
        similar_suggestions.extend(img.suggestions['suggestions'])

# 4. Boost overlapping suggestions
suggestion_scores = {s['key']: 1.0 for s in base_suggestions}
for s in similar_suggestions:
    if s['key'] in suggestion_scores:
        suggestion_scores[s['key']] += 0.5  # Boost overlap

# 5. Re-rank and return
final_suggestions = sorted(
    base_suggestions,
    key=lambda s: suggestion_scores[s['key']],
    reverse=True
)[:10]
```

---

## Implementation Phases

### Phase 1: Caption Generation ✅ (Week 1)
**Goal:** Generate structured captions for all uploaded images

**Tasks:**
- [ ] Add caption fields to `PhotoAnalysis` model
- [ ] Create migration to add new fields
- [ ] Implement `generate_caption()` function using GPT-4o-mini
- [ ] Update `PhotoAnalysisViewSet.upload()` to generate captions
- [ ] Add Constance settings:
  - `PHOTO_ANALYSIS_ENABLE_CAPTIONS` (default: True)
  - `PHOTO_ANALYSIS_CAPTION_MODEL` (default: "gpt-4o-mini")
  - `PHOTO_ANALYSIS_CAPTION_TEMPERATURE` (default: 0.2)
- [ ] Write tests for caption generation
- [ ] Update documentation

**Deliverables:**
- Caption generation working end-to-end
- Database stores: title, category, visible_text, caption
- Tests passing

### Phase 2: Embedding Generation & Storage ✅ (Week 2)
**Goal:** Generate and store vector embeddings

**Tasks:**
- [ ] Install pgvector: `pip install pgvector`
- [ ] Create migration to add `vector` extension and `embedding` column
- [ ] Implement `generate_embedding()` function using OpenAI API
- [ ] Update `PhotoAnalysisViewSet.upload()` to generate embeddings
- [ ] Create vector index for fast similarity search
- [ ] Add Constance settings:
  - `PHOTO_ANALYSIS_EMBEDDING_MODEL` (default: "text-embedding-3-small")
  - `PHOTO_ANALYSIS_ENABLE_EMBEDDINGS` (default: True)
- [ ] Write tests for embedding generation
- [ ] Update documentation

**Deliverables:**
- Embeddings stored in PostgreSQL
- Vector index created for fast queries
- Tests passing

### Phase 3: Similarity Search ✅ (Week 3)
**Goal:** Query similar images using vector search

**Tasks:**
- [ ] Implement similarity search query
- [ ] Create `find_similar_images()` utility function
- [ ] Add similarity threshold configuration
- [ ] Add API endpoint: `GET /api/photo-analysis/{id}/similar/`
- [ ] Write tests for similarity search
- [ ] Update documentation

**Deliverables:**
- Can query top-k similar images
- API endpoint returns similar images with similarity scores
- Tests passing

### Phase 4: Suggestion Synthesis ✅ (Week 4)
**Goal:** Merge suggestions from similar images

**Tasks:**
- [ ] Implement suggestion synthesis algorithm (weighted frequency)
- [ ] Update `PhotoAnalysisViewSet.upload()` to use synthesis
- [ ] Add configuration for similarity threshold and weights
- [ ] Test with real images to validate overlap
- [ ] Write tests for suggestion synthesis
- [ ] Update documentation

**Deliverables:**
- Similar images produce overlapping suggestions
- Configurable via Constance
- Tests passing

### Phase 5: Backfill & Optimization (Week 5)
**Goal:** Generate embeddings for existing images and optimize performance

**Tasks:**
- [ ] Create management command: `python manage.py generate_embeddings`
- [ ] Backfill captions and embeddings for existing PhotoAnalysis records
- [ ] Optimize vector index parameters based on dataset size
- [ ] Add monitoring/logging for embedding generation
- [ ] Performance testing with large datasets
- [ ] Cost analysis and optimization

**Deliverables:**
- All existing images have embeddings
- Performance benchmarks documented
- Cost analysis completed

---

## Technical Stack

### Dependencies
```txt
# Add to requirements.txt
pgvector==0.2.5          # PostgreSQL vector extension
openai>=1.0.0            # For embeddings API (already installed)
```

### PostgreSQL Extensions
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### Django Apps
- `photo_analysis` (existing) - Enhanced with caption and embedding functionality

---

## Database Schema

### Updated PhotoAnalysis Model
```python
class PhotoAnalysis(models.Model):
    # Existing fields
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    image_phash = models.CharField(max_length=64, db_index=True)
    file_hash = models.CharField(max_length=64, db_index=True)
    file_size = models.IntegerField()
    image_path = models.CharField(max_length=500)
    storage_type = models.CharField(max_length=10)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Existing analysis fields
    suggestions = models.JSONField()
    raw_response = models.JSONField(null=True, blank=True)
    ai_vision_model = models.CharField(max_length=100)
    token_usage = models.JSONField(null=True, blank=True)

    # NEW: Caption fields
    caption_title = models.CharField(max_length=255, blank=True)
    caption_category = models.CharField(max_length=100, blank=True)
    caption_visible_text = models.TextField(blank=True)
    caption_full = models.TextField(blank=True)
    caption_generated_at = models.DateTimeField(null=True, blank=True)

    # NEW: Embedding fields
    embedding = VectorField(dimensions=1536, null=True, blank=True)
    embedding_model = models.CharField(max_length=100, default='text-embedding-3-small')
    embedding_generated_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    fingerprint = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    times_used = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['file_hash']),
            models.Index(fields=['image_phash']),
            models.Index(fields=['created_at']),
            # Vector index created via raw SQL migration
        ]
```

---

## Cost Analysis

### Per-Image Cost Breakdown

| Component | Model | Cost |
|-----------|-------|------|
| **Caption Generation** | GPT-4o-mini | ~$0.0001 |
| **Embedding Generation** | text-embedding-3-small | ~$0.00001 |
| **Chat Suggestions** | GPT-4o (existing) | ~$0.002 |
| **Image Resizing** | CPU (negligible) | ~$0.00001 |
| **Storage (S3)** | 1 MB avg | ~$0.000023/month |
| **Vector Storage (PostgreSQL)** | 6 KB per vector | ~$0.000001/month |
| **Total per image** | | **~$0.0021** |

### Scaling Estimates

| Images/Month | Caption Cost | Embedding Cost | Total New Cost | Existing Cost | Grand Total |
|--------------|--------------|----------------|----------------|---------------|-------------|
| 1,000 | $0.10 | $0.01 | $0.11 | $2.00 | $2.11 |
| 10,000 | $1.00 | $0.10 | $1.10 | $20.00 | $21.10 |
| 100,000 | $10.00 | $1.00 | $11.00 | $200.00 | $211.00 |

**Key Insight:** Adding captions and embeddings increases cost by only ~5% (very affordable).

---

## Performance Considerations

### Query Performance
- **pgvector with IVFFlat index:**
  - <10,000 vectors: <10ms query time
  - 10,000-100,000 vectors: 10-50ms query time
  - >100,000 vectors: 50-200ms query time (consider HNSW index or migration)

### Optimization Tips
1. **Index Tuning:**
   - IVFFlat `lists` parameter: `sqrt(num_vectors)` is a good starting point
   - HNSW index for better accuracy at scale (requires PostgreSQL 15+)

2. **Batch Processing:**
   - Generate embeddings in batches for backfill
   - Use connection pooling

3. **Caching:**
   - Cache embedding API responses (optional, minimal benefit given low cost)

---

## API Endpoints

### Existing
- `POST /api/photo-analysis/upload/` - Upload and analyze photo

### New
- `GET /api/photo-analysis/{id}/similar/` - Get similar images
  ```json
  {
    "similar_images": [
      {
        "id": "uuid",
        "caption": "...",
        "similarity": 0.89,
        "suggestions": [...]
      }
    ]
  }
  ```

- `POST /api/photo-analysis/{id}/regenerate-embedding/` - Regenerate embedding (admin only)

---

## Constance Settings

```python
# New settings to add
PHOTO_ANALYSIS_ENABLE_CAPTIONS = (
    True,
    "Enable automatic caption generation for uploaded images",
    bool
)

PHOTO_ANALYSIS_CAPTION_MODEL = (
    "gpt-4o-mini",
    "OpenAI model for caption generation",
    str
)

PHOTO_ANALYSIS_CAPTION_TEMPERATURE = (
    0.2,
    "Temperature for caption generation (0.0-1.0)",
    float
)

PHOTO_ANALYSIS_ENABLE_EMBEDDINGS = (
    True,
    "Enable automatic embedding generation for captions",
    bool
)

PHOTO_ANALYSIS_EMBEDDING_MODEL = (
    "text-embedding-3-small",
    "OpenAI model for text embeddings",
    str
)

PHOTO_ANALYSIS_SIMILARITY_THRESHOLD = (
    0.7,
    "Minimum similarity score (0.0-1.0) for matching images",
    float
)

PHOTO_ANALYSIS_SIMILARITY_WEIGHT = (
    0.5,
    "Weight boost for overlapping suggestions from similar images",
    float
)
```

---

## Testing Strategy

### Unit Tests
- Caption generation produces valid JSON
- Embedding generation returns 1536-dimensional vector
- Similarity search returns correct results
- Suggestion synthesis merges correctly

### Integration Tests
- End-to-end upload → caption → embedding → storage
- Similarity search with real images
- Suggestion overlap validation

### Performance Tests
- Benchmark query time for 1k, 10k, 100k vectors
- Test index performance with different configurations

---

## Future Enhancements

### Phase 6: Advanced Features
- **Multimodal Embeddings:** Use CLIP or Titan Multimodal to embed images directly (no caption needed)
- **Cluster Analysis:** Pre-compute image clusters for instant recommendations
- **Feedback Loop:** Track which suggestions users select and fine-tune model
- **Hybrid Search:** Combine vector similarity with metadata filters (category, date, etc.)

### Scalability Options
- Migrate to OpenSearch Serverless for >1M vectors
- Implement approximate nearest neighbor (ANN) for faster queries
- Use Redis for caching embeddings

---

## References

- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)
- [Vector Similarity Search Best Practices](https://www.pinecone.io/learn/vector-similarity/)

---

## Status

**Current Phase:** Planning
**Next Steps:** Begin Phase 1 - Caption Generation
**Target Completion:** 5 weeks from start
