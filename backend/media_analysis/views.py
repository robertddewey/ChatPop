"""
DRF Views for Photo Analysis API.
"""
import io
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from constance import config

from .models import PhotoAnalysis
from .serializers import (
    PhotoAnalysisSerializer,
    PhotoAnalysisDetailSerializer,
    PhotoAnalysisListSerializer,
    PhotoUploadSerializer,
    PhotoUploadResponseSerializer,
)
from .utils.rate_limit import (
    media_analysis_rate_limit,
    get_client_identifier,
)
from .utils.fingerprinting.image_hash import calculate_phash
from .utils.fingerprinting.file_hash import calculate_sha256, get_file_size
from .utils.vision.openai_vision import get_vision_provider
from .utils.image_processing import resize_image_if_needed
from .utils.suggestion_blending import blend_suggestions
from .utils.suggestion_matching import match_suggestions_to_existing
from .utils.performance import PerformanceTracker
from chatpop.utils.media import MediaStorage

logger = logging.getLogger(__name__)


class PhotoAnalysisViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for photo analysis operations.

    Endpoints:
    - POST /api/photo-analysis/upload/ - Upload and analyze photo
    - GET /api/photo-analysis/{id}/ - Get existing analysis
    - GET /api/photo-analysis/recent/ - List recent analyses for current user
    """

    queryset = PhotoAnalysis.objects.all()
    serializer_class = PhotoAnalysisSerializer
    permission_classes = [AllowAny]  # Allow anonymous photo uploads (rate limited by fingerprint/IP)

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'retrieve':
            return PhotoAnalysisDetailSerializer
        elif self.action == 'list' or self.action == 'recent':
            return PhotoAnalysisListSerializer
        return PhotoAnalysisSerializer

    def get_queryset(self):
        """Filter queryset based on user/fingerprint."""
        queryset = PhotoAnalysis.objects.all()

        # Filter by user if authenticated
        if self.request.user.is_authenticated:
            queryset = queryset.filter(user=self.request.user)
        else:
            # Filter by fingerprint for anonymous users
            fingerprint = self.request.query_params.get('fingerprint')
            if fingerprint:
                queryset = queryset.filter(fingerprint=fingerprint)
            else:
                # No user or fingerprint - return empty queryset
                return PhotoAnalysis.objects.none()

        # Order by most recent
        return queryset.order_by('-created_at')

    @action(
        detail=False,
        methods=['post'],
        parser_classes=[MultiPartParser, FormParser],
        serializer_class=PhotoUploadResponseSerializer  # Response schema for API docs
    )
    @media_analysis_rate_limit
    def upload(self, request):
        """
        Upload and analyze a photo using OpenAI Vision API.

        Request (multipart/form-data):
            - image: Image file (required)
            - fingerprint: Browser fingerprint (optional)

        Response (PhotoUploadResponseSerializer):
            {
                "cached": boolean,  // Whether this is a cached result
                "analysis": PhotoAnalysisDetailSerializer,  // Complete analysis with blended suggestions
            }

        The analysis.suggestions field contains blended suggestions with metadata:
            - source: 'existing_room', 'popular', or 'ai'
            - has_room: boolean indicating if a room already exists
            - active_users: number of active users (for existing rooms)
            - popularity_score: frequency count (for popular suggestions)

        Status Codes:
            - 200/201: Analysis successful (200 = cached, 201 = new)
            - 400: Invalid image or validation error
            - 429: Rate limit exceeded
            - 500: Server error (OpenAI API failure, storage error, etc.)
        """
        # Validate upload data
        upload_serializer = PhotoUploadSerializer(data=request.data)
        if not upload_serializer.is_valid():
            return Response(
                upload_serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        image_file = upload_serializer.validated_data['image']
        fingerprint = upload_serializer.validated_data.get('fingerprint')

        # Get client identifiers
        user_id, fingerprint, ip_address = get_client_identifier(request)

        # Initialize performance tracker
        tracker = PerformanceTracker()

        try:
            # Calculate file hashes for deduplication (SHA-256 for collision resistance)
            image_file.seek(0)
            file_hash = calculate_sha256(image_file)

            image_file.seek(0)
            image_phash = calculate_phash(image_file)

            image_file.seek(0)
            file_size = get_file_size(image_file)

            # Check for existing analysis (exact match)
            existing_analysis = PhotoAnalysis.objects.filter(
                file_hash=file_hash
            ).first()

            if existing_analysis:
                # Dual-hash validation: verify both file_hash and phash match
                # This detects SHA-256 collision attacks (file_hash matches but content differs)
                if existing_analysis.image_phash != image_phash:
                    logger.error(
                        f"🚨 SECURITY WARNING: SHA-256 collision detected! "
                        f"file_hash={file_hash[:16]}... matches but phash differs "
                        f"(cached: {existing_analysis.image_phash[:16]}... vs current: {image_phash[:16]}...). "
                        f"Rejecting cached result and processing as new upload."
                    )
                    # Don't use cached result - process as new upload
                    existing_analysis = None
                else:
                    # Both hashes match - safe to return cached analysis
                    logger.info(f"Returning cached analysis for file_hash={file_hash[:16]}... (phash validated)")

            if existing_analysis:
                # Blend suggestions for cached analysis (add room metadata)
                blended = None  # Track if blending succeeded
                if existing_analysis.suggestions:
                    try:
                        logger.info("Enriching refined suggestions with room metadata (cached analysis)")

                        # Extract refined suggestions from stored data
                        suggestions_data = existing_analysis.suggestions
                        if isinstance(suggestions_data, dict):
                            refined_suggestions = suggestions_data.get('suggestions', [])
                        elif isinstance(suggestions_data, list):
                            refined_suggestions = suggestions_data
                        else:
                            refined_suggestions = []

                        # Enrich refined suggestions with room metadata (metadata-only layer)
                        blended = blend_suggestions(
                            refined_suggestions=refined_suggestions,
                            exclude_photo_id=str(existing_analysis.id)
                        )

                        logger.info(f"Enriched {len(blended)} refined suggestions with room metadata")
                    except Exception as e:
                        logger.warning(f"Suggestion blending failed (non-fatal): {str(e)}", exc_info=True)
                        blended = None  # Reset on error

                serializer = PhotoAnalysisDetailSerializer(
                    existing_analysis,
                    context={'request': request}
                )

                # Override suggestions field with blended data (includes metadata)
                response_data = {
                    'cached': True,
                    'analysis': serializer.data,
                }
                # Replace suggestions with blended versions if blending succeeded
                if blended is not None:
                    response_data['analysis']['suggestions'] = [s.to_dict() for s in blended]

                return Response(response_data, status=status.HTTP_200_OK)

            # Resize image if needed to reduce token usage
            # This happens AFTER cache check to avoid unnecessary processing
            max_megapixels = config.PHOTO_ANALYSIS_MAX_MEGAPIXELS
            image_file.seek(0)
            resized_image, was_resized = resize_image_if_needed(
                image_file,
                max_megapixels
            )

            if was_resized:
                logger.info(f"Resized image to {max_megapixels}MP to reduce token usage")

            # Get vision provider
            vision_provider = get_vision_provider(
                model=config.PHOTO_ANALYSIS_OPENAI_MODEL
            )

            if not vision_provider.is_available():
                return Response(
                    {"error": "OpenAI API not configured"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            # Analyze image for chat name suggestions
            logger.info(f"Analyzing image for suggestions with {vision_provider.get_model_name()}")
            resized_image.seek(0)
            analysis_result = vision_provider.analyze_image(
                image_file=resized_image,
                prompt=config.PHOTO_ANALYSIS_PROMPT,
                max_suggestions=10,  # Request 10 seed suggestions
                temperature=config.PHOTO_ANALYSIS_TEMPERATURE
            )
            logger.info("Vision analysis completed")

            # TODO: Track API cost for circuit breaker (not implemented yet)
            # estimated_cost = estimate_request_cost(
            #     model=config.PHOTO_ANALYSIS_OPENAI_MODEL,
            #     detail_mode=config.PHOTO_ANALYSIS_DETAIL_MODE,
            #     megapixels=max_megapixels
            # )
            # increment_cost(estimated_cost)

            # Store image file using unified MediaStorage API
            import uuid
            file_extension = image_file.name.split('.')[-1] if '.' in image_file.name else 'jpg'
            filename = f"{uuid.uuid4()}.{file_extension}"

            # Save file (MediaStorage automatically handles S3 vs local based on settings)
            image_file.seek(0)
            storage_path, storage_type = MediaStorage.save_file(
                file_obj=image_file,
                directory='media_analysis',
                filename=filename
            )

            logger.info(f"Stored image ({storage_type}): {storage_path}")

            # Calculate expiration time
            ttl_hours = config.PHOTO_ANALYSIS_IMAGE_TTL_HOURS
            expires_at = None
            if ttl_hours > 0:
                expires_at = timezone.now() + timedelta(hours=ttl_hours)

            # Format seed suggestions (initial 10 AI suggestions from Vision API)
            seed_suggestions_list = [
                {
                    'name': s.name,
                    'key': s.key,
                    'description': s.description,
                    'is_proper_noun': s.is_proper_noun,
                    'source': 'seed'
                }
                for s in analysis_result.suggestions
            ]

            seed_suggestions_data = {
                'suggestions': seed_suggestions_list,
                'count': len(seed_suggestions_list)
            }

            logger.info(f"Received {len(seed_suggestions_list)} seed suggestions from Vision API")

            # =========================================================================
            # SUGGESTION-TO-SUGGESTION MATCHING WORKFLOW
            # Replaces photo-level similarity with granular suggestion-level matching
            # =========================================================================

            # STEP 1: Match seed suggestions to existing Suggestion records
            # - Proper nouns: preserved without matching (unique entities)
            # - Generic suggestions: K-NN search in Suggestion table (threshold: 0.15)
            # - Match found: use existing suggestion, increment usage_count
            # - No match: create new Suggestion record
            # This eliminates cross-domain contamination (whiskey photos won't match beer photos)
            logger.info("\n" + "="*80)
            logger.info("STEP 1: Matching seed suggestions to existing Suggestion records")
            logger.info("="*80)

            matched_suggestions = match_suggestions_to_existing(seed_suggestions_list)

            logger.info(f"\nMatching complete: {len(matched_suggestions)} suggestions processed")

            # STEP 2: Sort by proper noun + popularity, take top 5
            # - Priority 1: Proper nouns (always included first)
            # - Priority 2: Most popular suggestions (highest usage_count)
            logger.info("\n" + "="*80)
            logger.info("STEP 2: Sorting by proper noun priority + popularity")
            logger.info("="*80)

            proper_nouns = [s for s in matched_suggestions if s.get('is_proper_noun', False)]
            non_proper_nouns = [s for s in matched_suggestions if not s.get('is_proper_noun', False)]

            # Sort non-proper nouns by usage_count (descending)
            non_proper_nouns_sorted = sorted(
                non_proper_nouns,
                key=lambda s: s.get('usage_count', 0),
                reverse=True
            )

            logger.info(f"\nProper nouns: {len(proper_nouns)}")
            for pn in proper_nouns:
                logger.info(f"  ✓ '{pn['name']}' (usage: {pn.get('usage_count', 0)}x)")

            logger.info(f"\nNon-proper nouns (sorted by popularity): {len(non_proper_nouns_sorted)}")
            for npn in non_proper_nouns_sorted[:5]:  # Show top 5
                logger.info(f"  → '{npn['name']}' (usage: {npn.get('usage_count', 0)}x, source: {npn.get('source', 'unknown')})")

            # Combine: proper nouns first, then most popular
            final_suggestions_list = (proper_nouns + non_proper_nouns_sorted)[:5]

            logger.info(
                f"\nFinal selection: {len(final_suggestions_list)} suggestions "
                f"({len([s for s in final_suggestions_list if s.get('is_proper_noun', False)])} proper nouns, "
                f"{len([s for s in final_suggestions_list if not s.get('is_proper_noun', False)])} generics)"
            )
            logger.info("="*80 + "\n")

            # Format final suggestions for database storage
            suggestions_data = {
                'suggestions': final_suggestions_list,
                'count': len(final_suggestions_list)
            }

            # Enrich final suggestions with room metadata (metadata-only layer)
            # Adds has_room, room_id, room_code, room_url, active_users for existing rooms
            blended = None
            try:
                logger.info("Enriching final suggestions with room metadata")
                blended = blend_suggestions(
                    refined_suggestions=final_suggestions_list,
                    exclude_photo_id=None  # Will exclude after PhotoAnalysis is created
                )
                logger.info(f"Enriched {len(blended)} suggestions with room metadata")
            except Exception as e:
                # Metadata enrichment is non-fatal - log warning and continue
                logger.warning(f"Metadata enrichment failed (non-fatal): {str(e)}", exc_info=True)
                blended = None

            # Create PhotoAnalysis record
            media_analysis = PhotoAnalysis.objects.create(
                image_phash=image_phash,
                file_hash=file_hash,
                file_size=file_size,
                image_path=storage_path,
                storage_type=storage_type,
                expires_at=expires_at,
                seed_suggestions=seed_suggestions_data,  # Store original 10 AI suggestions for audit trail
                suggestions=suggestions_data,  # Store final merged suggestions (popular + normalized)
                raw_response=analysis_result.raw_response,
                ai_vision_model=analysis_result.model,
                token_usage=analysis_result.token_usage,
                user=request.user if request.user.is_authenticated else None,
                fingerprint=fingerprint,
                ip_address=ip_address,
                suggestions_embedding=None,  # Not using photo-level similarity
                suggestions_embedding_generated_at=None
            )

            # Return analysis result
            serializer = PhotoAnalysisDetailSerializer(
                media_analysis,
                context={'request': request}
            )

            # Override suggestions field with blended data (includes metadata)
            response_data = {
                'cached': False,
                'analysis': serializer.data,
            }
            # Replace suggestions with blended versions if blending was performed
            if blended is not None:
                response_data['analysis']['suggestions'] = [s.to_dict() for s in blended]

            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"Photo analysis failed: {str(e)}", exc_info=True)
            return Response(
                {"error": "Photo analysis failed", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def recent(self, request):
        """
        List recent photo analyses for the current user.

        Query params:
            - fingerprint: Browser fingerprint (required for anonymous users)
            - limit: Number of results (default: 10)

        Response:
            - 200: List of recent analyses
            - 400: Missing fingerprint for anonymous user
        """
        # Get limit from query params
        limit = int(request.query_params.get('limit', 10))
        limit = min(limit, 50)  # Cap at 50

        # Get queryset (filtered by user/fingerprint)
        queryset = self.get_queryset()[:limit]

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=['post'],
        parser_classes=[MultiPartParser, FormParser],
        url_path='recognize-audio'
    )
    @media_analysis_rate_limit
    def recognize_audio(self, request):
        """
        Recognize a song from audio recording using ACRCloud API.

        Request (multipart/form-data):
            - audio: Audio file (required) - WebM, MP3, WAV, etc.
            - fingerprint: Browser fingerprint (optional)
            - username: Username (optional)

        Response:
            {
                "success": true,
                "song": "Song Title",
                "artist": "Artist Name",
                "album": "Album Name",
                "release_date": "2023",
                "duration_ms": 180000,
                "score": 95,
                "external_ids": {
                    "spotify": "track_id",
                    "youtube": "video_id"
                }
            }
        """
        try:
            # Validate audio file
            audio_file = request.FILES.get('audio')
            if not audio_file:
                return Response(
                    {"error": "No audio file provided"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Read audio data
            audio_data = audio_file.read()

            # Determine audio format from content type or filename
            content_type = audio_file.content_type
            audio_format = "webm"  # Default
            if content_type:
                if "webm" in content_type:
                    audio_format = "webm"
                elif "mp3" in content_type or "mpeg" in content_type:
                    audio_format = "mp3"
                elif "wav" in content_type:
                    audio_format = "wav"
            elif audio_file.name:
                if audio_file.name.endswith('.mp3'):
                    audio_format = "mp3"
                elif audio_file.name.endswith('.wav'):
                    audio_format = "wav"

            logger.info(f"Processing audio recognition request (size: {len(audio_data)} bytes, format: {audio_format})")

            # Recognize audio using ACRCloud
            from .utils.audio_recognition import recognize_audio
            result = recognize_audio(audio_data, audio_format)

            if not result.get("success"):
                return Response(
                    {"error": result.get("error", "Recognition failed")},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Return recognition results (without raw_response for cleaner API)
            response_data = {
                "success": result["success"],
                "song": result["song"],
                "artist": result["artist"],
                "album": result.get("album", ""),
                "release_date": result.get("release_date", ""),
                "duration_ms": result.get("duration_ms", 0),
                "score": result.get("score", 0),
                "external_ids": result.get("external_ids", {})
            }

            logger.info(f"Audio recognition successful: {response_data['song']} by {response_data['artist']}")
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Audio recognition failed: {str(e)}", exc_info=True)
            return Response(
                {"error": "Audio recognition failed", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
