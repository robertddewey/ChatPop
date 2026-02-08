# Constance Settings & Dead Code Cleanup

## Overview

This document summarizes stale constance settings in the fixture and associated dead code that should be removed.

- **Settings.py CONSTANCE_CONFIG:** 53 keys (source of truth)
- **Fixture constance keys:** 73 keys
- **Stale keys to remove:** 20 keys

---

## Stale Constance Keys to Remove from Fixture (20 total)

### Caption Generation Feature - Dead Code (5 keys)

| Key | Description |
|-----|-------------|
| `PHOTO_ANALYSIS_CAPTION_MODEL` | OpenAI model for caption generation |
| `PHOTO_ANALYSIS_CAPTION_PROMPT` | Prompt for caption generation |
| `PHOTO_ANALYSIS_CAPTION_TEMPERATURE` | Temperature for caption generation |
| `PHOTO_ANALYSIS_ENABLE_CAPTIONS` | Toggle for caption feature |
| `PHOTO_ANALYSIS_ENABLE_CAPTION_EMBEDDING` | Toggle for caption embeddings |

### Photo Similarity Feature - Removed (3 keys)

| Key | Description |
|-----|-------------|
| `PHOTO_SIMILARITY_MAX_DISTANCE` | Max distance for similarity matching |
| `PHOTO_SIMILARITY_MAX_RESULTS` | Max results for similarity search |
| `PHOTO_SIMILARITY_MIN_USERS` | Min users for similarity feature |

### Photo Suggestion Refinement Feature - Removed (9 keys)

| Key | Description |
|-----|-------------|
| `PHOTO_SUGGESTION_BLEND_MIN_POPULAR` | Min popular for blending |
| `PHOTO_SUGGESTION_CLUSTERING_DISTANCE` | Clustering distance threshold |
| `PHOTO_SUGGESTION_CLUSTERING_LIMIT` | Max clustering results |
| `PHOTO_SUGGESTION_ENABLE_REFINEMENT` | Toggle for refinement |
| `PHOTO_SUGGESTION_REFINEMENT_MAX` | Max refinement results |
| `PHOTO_SUGGESTION_REFINEMENT_MIN` | Min refinement results |
| `PHOTO_SUGGESTION_REFINEMENT_MODEL` | Model for refinement |
| `PHOTO_SUGGESTION_REFINEMENT_POPULAR_LIMIT` | Popular limit for refinement |
| `PHOTO_SUGGESTION_REFINEMENT_PROMPT` | Prompt for refinement |
| `PHOTO_SUGGESTION_REFINEMENT_TEMPERATURE` | Temperature for refinement |

### Old Pin System - Removed/Renamed (2 keys)

| Key | Description |
|-----|-------------|
| `PIN_DURATION_MINUTES` | Old pin duration (replaced by `PIN_NEW_PIN_DURATION_MINUTES`) |
| `PIN_MINIMUM_CENTS` | Old minimum pin cost (removed) |

---

## Dead Code Files

### Files with Dead Code

| File | Status | Reason |
|------|--------|--------|
| `media_analysis/utils/caption.py` | **Entire file is dead** | Not imported anywhere except tests |
| `media_analysis/tests/test_caption_generation.py` | **Entire file is dead** | Tests for dead caption feature |
| `media_analysis/management/commands/regenerate_embeddings.py` | **Partially dead** | References `PHOTO_ANALYSIS_ENABLE_CAPTION_EMBEDDING` (dead), but also does suggestions embedding (may be used) |

### 1. `media_analysis/utils/caption.py` (DEAD - ~250 lines)

**Functions:**
- `CaptionData` class
- `generate_caption()`
- `_encode_image_to_base64()`
- `_parse_caption_response()`

**Uses these dead keys:**
- `PHOTO_ANALYSIS_ENABLE_CAPTIONS` (line 195)
- `PHOTO_ANALYSIS_CAPTION_MODEL` (line 204)
- `PHOTO_ANALYSIS_CAPTION_PROMPT` (line 205)
- `PHOTO_ANALYSIS_CAPTION_TEMPERATURE` (line 206)

**Status:** Not imported anywhere in production code

### 2. `media_analysis/tests/test_caption_generation.py` (DEAD - ~350 lines)

**Purpose:** Tests for the dead caption generation feature

**Status:** Tests dead code - should be removed with caption.py

### 3. `media_analysis/management/commands/regenerate_embeddings.py` (PARTIAL)

**Uses dead key:** `PHOTO_ANALYSIS_ENABLE_CAPTION_EMBEDDING` (lines 70, 121, 123, 142)

**Status:** Caption embedding logic is dead, but suggestion embedding logic may still be used

**Action:** Remove caption embedding references, keep suggestion embedding functionality

---

## Keys with Zero Code References

These 14 keys have **no code references** - the features were completely removed:

- `PHOTO_SIMILARITY_MAX_DISTANCE`
- `PHOTO_SIMILARITY_MAX_RESULTS`
- `PHOTO_SIMILARITY_MIN_USERS`
- `PHOTO_SUGGESTION_BLEND_MIN_POPULAR`
- `PHOTO_SUGGESTION_CLUSTERING_DISTANCE`
- `PHOTO_SUGGESTION_CLUSTERING_LIMIT`
- `PHOTO_SUGGESTION_ENABLE_REFINEMENT`
- `PHOTO_SUGGESTION_REFINEMENT_MAX`
- `PHOTO_SUGGESTION_REFINEMENT_MIN`
- `PHOTO_SUGGESTION_REFINEMENT_MODEL`
- `PHOTO_SUGGESTION_REFINEMENT_POPULAR_LIMIT`
- `PHOTO_SUGGESTION_REFINEMENT_PROMPT`
- `PHOTO_SUGGESTION_REFINEMENT_TEMPERATURE`
- `PIN_MINIMUM_CENTS`

---

## Comments Referencing Old Key Names

`PIN_DURATION_MINUTES` appears only in **comments/docstrings** referencing the renamed key `PIN_NEW_PIN_DURATION_MINUTES`:

- `chats/models.py:336` - comment
- `chats/serializers.py:438` - docstring
- `chats/views.py:1047` - docstring

These comments should be updated to reference `PIN_NEW_PIN_DURATION_MINUTES`.

---

## Recommended Actions

### 1. Remove from fixture (20 keys)
**File:** `backend/fixtures/seed_data.json`

Remove all 20 stale constance entries listed above.

### 2. Delete dead files (2 files)
- `media_analysis/utils/caption.py`
- `media_analysis/tests/test_caption_generation.py`

### 3. Clean up regenerate_embeddings.py
Remove caption embedding references from `media_analysis/management/commands/regenerate_embeddings.py`:
- Line 70: `caption_embedding_enabled = config.PHOTO_ANALYSIS_ENABLE_CAPTION_EMBEDDING`
- Line 121-142: Caption embedding logic block

### 4. Update comments (3 locations)
Fix references to `PIN_DURATION_MINUTES` → `PIN_NEW_PIN_DURATION_MINUTES`:
- `chats/models.py:336`
- `chats/serializers.py:438`
- `chats/views.py:1047`

---

## Summary of Changes

| Action | Before | After |
|--------|--------|-------|
| Fixture constance entries | 73 | 53 |
| Dead code files | 2 | 0 |
| Stale key references | 20 | 0 |
| Outdated comments | 3 | 0 |
