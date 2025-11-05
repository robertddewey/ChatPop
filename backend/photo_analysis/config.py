"""
Photo Analysis Configuration Settings

Centralized configuration for suggestion matching, photo similarity,
and collaborative discovery algorithms.

Usage:
    from photo_analysis.config import (
        SUGGESTION_MATCHING_SIMILARITY_THRESHOLD,
        K_NEAREST_NEIGHBORS,
        MAX_COSINE_DISTANCE
    )
"""

# ==============================================================================
# SUGGESTION-LEVEL MATCHING (K-NN for suggestions)
# ==============================================================================
# Controls how similar two suggestions must be to match during photo upload

# Cosine distance threshold for suggestion matching (GENERIC suggestions only)
# Lower = stricter matching (require more similarity)
# Higher = looser matching (allow more variation)
# Range: 0.0 (identical) to 1.0 (completely different)
# Examples:
#   0.30 = 70%+ similarity required (strict)
#   0.35 = 65%+ similarity required (moderate)
#   0.40 = 60%+ similarity required (loose - current default)
SUGGESTION_MATCHING_SIMILARITY_THRESHOLD = 0.4

# Cosine distance threshold for PROPER NOUN matching
# Proper nouns need stricter matching to avoid false positives
# (e.g., "Open Season" book vs "Open Season" movie should NOT match)
# Lower = stricter (require more similarity to match)
# Examples:
#   0.15 = 85%+ similarity required (strict - prevents title collisions)
#   0.20 = 80%+ similarity required (moderate)
#   0.25 = 75%+ similarity required (loose)
PROPER_NOUN_MATCHING_THRESHOLD = 0.15

# Number of parallel threads for suggestion K-NN searches
# Higher = faster parallel processing but more CPU/memory usage
SUGGESTION_MATCHING_MAX_WORKERS = 10

# Number of nearest neighbor candidates to retrieve and log
# This controls how many similar suggestions are examined and displayed in logs
# Higher = more diagnostic info but slower queries
SUGGESTION_MATCHING_CANDIDATES_COUNT = 5

# Diversity filter threshold
# After matching, filter out suggestions that are too similar to each other
# This prevents returning multiple variations of the same concept
# Lower = stricter diversity (require more difference)
# Higher = looser diversity (allow more similarity)
# Range: 0.0 (must be completely different) to 1.0 (can be identical)
# Examples:
#   0.20 = 80%+ different required (very strict)
#   0.25 = 75%+ different required (strict - current default)
#   0.30 = 70%+ different required (moderate)
DIVERSITY_FILTER_THRESHOLD = 0.2


# ==============================================================================
# PHOTO-LEVEL SIMILARITY (K-NN for photos) - DEPRECATED / NOT USED
# ==============================================================================
# Photo-level similarity was removed after testing showed no impact on suggestion quality.
# All collaborative discovery now happens at the suggestion level via Suggestion.usage_count.
# The code below is kept for reference but is not imported or used anywhere.
#
# # Number of similar photos to consider when finding popular suggestions
# # Higher = more photos examined, broader collaborative discovery
# # Lower = fewer photos, more focused recommendations
# K_NEAREST_NEIGHBORS = 10
#
# # Maximum cosine distance for photo similarity
# # Photos farther than this distance are not considered "similar"
# # Range: 0.0 (identical) to 1.0 (completely different)
# # Examples:
# #   0.30 = 70%+ similarity required (strict)
# #   0.40 = 60%+ similarity required (moderate - current default)
# #   0.50 = 50%+ similarity required (loose)
# MAX_COSINE_DISTANCE = 0.40
#
# # Minimum number of times a suggestion must appear in similar photos
# # to be considered "popular" and recommended
# # Examples:
# #   1.0 = appear at least once (very inclusive)
# #   2.0 = appear at least twice (moderate filtering)
# #   3.0 = appear at least 3 times (strict filtering)
# MIN_POPULARITY_SCORE = 1.0


# ==============================================================================
# PERFORMANCE TUNING
# ==============================================================================

# Batch size for embedding generation
# Higher = fewer API calls but more memory usage
# Lower = more API calls but less memory usage
EMBEDDING_BATCH_SIZE = 10

# Timeout for OpenAI API calls (seconds)
OPENAI_API_TIMEOUT = 30


# ==============================================================================
# FEATURE FLAGS
# ==============================================================================

# Enable/disable suggestion matching (if False, all suggestions are created new)
ENABLE_SUGGESTION_MATCHING = True

# Enable/disable popular suggestions from similar photos
ENABLE_COLLABORATIVE_DISCOVERY = True

# Enable/disable proper noun preservation (brands, titles, etc.)
ENABLE_PROPER_NOUN_PRESERVATION = True
