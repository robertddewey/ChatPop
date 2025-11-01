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
from constance import config

from .models import PhotoAnalysis
from .serializers import (
    PhotoAnalysisSerializer,
    PhotoAnalysisDetailSerializer,
    PhotoAnalysisListSerializer,
    PhotoUploadSerializer,
    PhotoUploadResponseSerializer,
)
from .utils.rate_limit import photo_analysis_rate_limit, get_client_identifier
from .utils.fingerprinting.image_hash import calculate_phash
from .utils.fingerprinting.file_hash import calculate_md5, get_file_size
from .utils.vision.openai_vision import get_vision_provider
from .utils.image_processing import resize_image_if_needed
from .utils.embedding import generate_suggestions_embedding
from .utils.suggestion_blending import blend_suggestions, get_similar_photo_popular_suggestions
from .utils.room_matching import normalize_suggestions_to_rooms
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
    @photo_analysis_rate_limit
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
            # Calculate file hashes for deduplication
            image_file.seek(0)
            file_hash = calculate_md5(image_file)

            image_file.seek(0)
            image_phash = calculate_phash(image_file)

            image_file.seek(0)
            file_size = get_file_size(image_file)

            # Check for existing analysis (exact match)
            existing_analysis = PhotoAnalysis.objects.filter(
                file_hash=file_hash
            ).first()

            if existing_analysis:
                # Return cached analysis
                logger.info(f"Returning cached analysis for file_hash={file_hash}")

                # Blend suggestions for cached analysis (existing rooms + popular + AI)
                blended = None  # Track if blending succeeded
                if existing_analysis.suggestions_embedding is not None and existing_analysis.suggestions:
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

            # Store image file using unified MediaStorage API
            import uuid
            file_extension = image_file.name.split('.')[-1] if '.' in image_file.name else 'jpg'
            filename = f"{uuid.uuid4()}.{file_extension}"

            # Save file (MediaStorage automatically handles S3 vs local based on settings)
            image_file.seek(0)
            storage_path, storage_type = MediaStorage.save_file(
                file_obj=image_file,
                directory='photo_analysis',
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
            # NEW WORKFLOW: Suggestion normalization + photo-level popularity
            # Replaces LLM-based refinement with faster, deterministic approach
            # =========================================================================

            # STEP 1: Normalize generic suggestions to existing rooms (parallel K-NN)
            # - Proper nouns preserved (e.g., "Budweiser", "The Matrix")
            # - Generic suggestions matched to existing rooms via embedding similarity
            logger.info("Step 1: Normalizing generic suggestions to existing rooms")
            normalized_suggestions = normalize_suggestions_to_rooms(
                suggestions=seed_suggestions_list
            )

            # STEP 2: Generate combined suggestions embedding for photo-level similarity
            # - Used to find photos with similar themes
            # - Enables discovery of popular suggestions from community
            logger.info("Step 2: Generating combined suggestions embedding for photo-level K-NN")
            try:
                # Convert normalized suggestions to embedding input format
                embedding_input = [
                    {
                        'name': s['name'],
                        'description': s.get('description', '')
                    }
                    for s in normalized_suggestions
                ]

                suggestions_embedding_data = generate_suggestions_embedding(
                    suggestions=embedding_input,
                    model="text-embedding-3-small"
                )

                suggestions_embedding_vector = suggestions_embedding_data.embedding

                logger.info(
                    f"Suggestions embedding generated: "
                    f"dimensions={len(suggestions_embedding_vector)}, "
                    f"tokens={suggestions_embedding_data.token_usage['total_tokens']}"
                )

            except Exception as e:
                logger.warning(f"Suggestions embedding generation failed (non-fatal): {str(e)}", exc_info=True)
                suggestions_embedding_vector = None

            # STEP 3: Find similar photos and extract popular suggestions
            # - K-NN search on suggestions_embedding
            # - Extract frequently occurring suggestions from similar photos
            similar_photo_popular = []
            if suggestions_embedding_vector is not None:
                try:
                    logger.info("Step 3: Finding similar photos to extract popular suggestions")
                    similar_photo_popular = get_similar_photo_popular_suggestions(
                        embedding_vector=suggestions_embedding_vector,
                        exclude_photo_id=None  # We haven't created the PhotoAnalysis record yet
                    )
                    logger.info(f"Found {len(similar_photo_popular)} popular suggestions from similar photos")
                except Exception as e:
                    logger.warning(f"Failed to extract popular suggestions (non-fatal): {str(e)}", exc_info=True)
                    similar_photo_popular = []

            # STEP 4: Merge normalized + popular suggestions
            # - Priority: Popular suggestions first (community trends)
            # - Then add normalized suggestions
            # - Simple deduplication by key
            # - Limit to 5 final suggestions
            logger.info("Step 4: Merging popular + normalized suggestions")

            # Build final suggestions pool
            final_suggestions_pool = []
            seen_keys = set()

            # Add popular suggestions first (prioritize community trends)
            for popular in similar_photo_popular:
                if popular['key'] not in seen_keys:
                    final_suggestions_pool.append({
                        'name': popular['name'],
                        'key': popular['key'],
                        'description': '',  # Popular suggestions don't have descriptions
                        'source': 'popular',
                        'is_proper_noun': False
                    })
                    seen_keys.add(popular['key'])

            # Add normalized suggestions (fill remaining slots)
            for suggestion in normalized_suggestions:
                if suggestion['key'] not in seen_keys:
                    final_suggestions_pool.append(suggestion)
                    seen_keys.add(suggestion['key'])

            # Limit to 5 suggestions
            final_suggestions_list = final_suggestions_pool[:5]

            logger.info(
                f"Merge complete: {len(similar_photo_popular)} popular + "
                f"{len(normalized_suggestions)} normalized → {len(final_suggestions_list)} final "
                f"(popular={sum(1 for s in final_suggestions_list if s.get('source') == 'popular')}, "
                f"normalized={sum(1 for s in final_suggestions_list if s.get('source') == 'normalized')}, "
                f"seed={sum(1 for s in final_suggestions_list if s.get('source') == 'seed')})"
            )

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
            photo_analysis = PhotoAnalysis.objects.create(
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
                suggestions_embedding=suggestions_embedding_vector,
                suggestions_embedding_generated_at=timezone.now() if suggestions_embedding_vector is not None else None
            )

            # Return analysis result
            serializer = PhotoAnalysisDetailSerializer(
                photo_analysis,
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
