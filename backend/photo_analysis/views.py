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
    SimilarRoomSerializer,
)
from .utils.rate_limit import photo_analysis_rate_limit, get_client_identifier
from .utils.fingerprinting.image_hash import calculate_phash
from .utils.fingerprinting.file_hash import calculate_md5, get_file_size
from .utils.vision.openai_vision import get_vision_provider
from .utils.image_processing import resize_image_if_needed
from .utils.caption import generate_caption
from .utils.embedding import generate_embedding, generate_suggestions_embedding
from .utils.similarity import find_similar_rooms
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

    @action(detail=False, methods=['post'], parser_classes=[MultiPartParser, FormParser])
    @photo_analysis_rate_limit
    def upload(self, request):
        """
        Upload and analyze a photo using OpenAI Vision API.

        Request (multipart/form-data):
            - image: Image file (required)
            - fingerprint: Browser fingerprint (optional)

        Response:
            - 200: Analysis successful, returns PhotoAnalysis object
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

                # Find similar rooms for cached analysis too
                similar_rooms = []
                if existing_analysis.suggestions_embedding is not None:
                    try:
                        logger.info("Searching for similar existing chat rooms (cached analysis)")
                        similar_rooms = find_similar_rooms(
                            embedding_vector=existing_analysis.suggestions_embedding,
                            exclude_photo_id=str(existing_analysis.id)
                        )
                        logger.info(f"Found {len(similar_rooms)} similar rooms")
                    except Exception as e:
                        logger.warning(f"Similarity search failed (non-fatal): {str(e)}", exc_info=True)
                        similar_rooms = []

                serializer = PhotoAnalysisDetailSerializer(
                    existing_analysis,
                    context={'request': request}
                )
                similar_rooms_serializer = SimilarRoomSerializer(similar_rooms, many=True)

                return Response({
                    'cached': True,
                    'analysis': serializer.data,
                    'similar_rooms': similar_rooms_serializer.data
                }, status=status.HTTP_200_OK)

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

            # Create separate copies of the image for parallel processing
            # This is necessary because both API calls need to read the image independently
            resized_image.seek(0)
            image_bytes = resized_image.read()

            image_for_suggestions = io.BytesIO(image_bytes)
            image_for_captions = io.BytesIO(image_bytes)

            # Define worker functions for parallel execution
            def analyze_suggestions():
                """Worker: Analyze image for chat name suggestions."""
                logger.info(f"Analyzing image for suggestions with {vision_provider.get_model_name()}")
                image_for_suggestions.seek(0)
                return vision_provider.analyze_image(
                    image_file=image_for_suggestions,
                    prompt=config.PHOTO_ANALYSIS_PROMPT,
                    max_suggestions=10,
                    temperature=config.PHOTO_ANALYSIS_TEMPERATURE
                )

            def analyze_captions():
                """Worker: Generate semantic caption for embeddings."""
                if not config.PHOTO_ANALYSIS_ENABLE_CAPTIONS:
                    logger.info("Caption generation disabled, skipping")
                    return None

                logger.info(f"Generating caption with model={config.PHOTO_ANALYSIS_CAPTION_MODEL}")
                image_for_captions.seek(0)
                return generate_caption(image_file=image_for_captions)

            # Execute both API calls in parallel using ThreadPoolExecutor
            logger.info("Starting parallel API execution (suggestions + captions)")
            analysis_result = None
            caption_data = None

            with ThreadPoolExecutor(max_workers=2) as executor:
                # Submit both tasks
                future_suggestions = executor.submit(analyze_suggestions)
                future_captions = executor.submit(analyze_captions)

                # Wait for both to complete and collect results
                for future in as_completed([future_suggestions, future_captions]):
                    try:
                        result = future.result()

                        # Identify which task completed
                        if future == future_suggestions:
                            analysis_result = result
                            logger.info("Suggestions analysis completed")
                        elif future == future_captions:
                            caption_data = result
                            logger.info("Caption generation completed")

                    except Exception as e:
                        # Log error but continue - one task can fail without breaking the other
                        if future == future_suggestions:
                            logger.error(f"Suggestions analysis failed: {str(e)}", exc_info=True)
                            raise  # Suggestions are required, so re-raise
                        elif future == future_captions:
                            logger.warning(f"Caption generation failed (non-fatal): {str(e)}", exc_info=True)
                            caption_data = None  # Captions are optional

            # Verify we got the required suggestions result
            if analysis_result is None:
                raise RuntimeError("Vision analysis failed to produce suggestions")

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

            # Format suggestions for database storage
            suggestions_data = {
                'suggestions': [
                    {
                        'name': s.name,
                        'key': s.key,
                        'description': s.description
                    }
                    for s in analysis_result.suggestions
                ],
                'count': len(analysis_result.suggestions)
            }

            # Prepare caption fields (if caption generation succeeded)
            caption_fields = {}
            if caption_data:
                caption_fields = {
                    'caption_title': caption_data.title,
                    'caption_category': caption_data.category,
                    'caption_visible_text': caption_data.visible_text,
                    'caption_full': caption_data.caption,
                    'caption_generated_at': timezone.now(),
                    'caption_model': caption_data.model,
                    'caption_token_usage': caption_data.token_usage,
                    'caption_raw_response': caption_data.raw_response
                }
                logger.info(f"Caption fields populated: title='{caption_data.title}', category='{caption_data.category}', model='{caption_data.model}'")

                # Generate Embedding 1: Semantic/Content embedding from caption fields
                try:
                    logger.info("Generating caption embedding (Embedding 1: Semantic/Content)")
                    embedding_data = generate_embedding(
                        caption_full=caption_data.caption,
                        caption_visible_text=caption_data.visible_text,
                        caption_title=caption_data.title,
                        caption_category=caption_data.category,
                        model="text-embedding-3-small"
                    )

                    # Add caption embedding fields
                    caption_fields['caption_embedding'] = embedding_data.embedding
                    caption_fields['caption_embedding_generated_at'] = timezone.now()

                    logger.info(
                        f"Caption embedding generated successfully: "
                        f"dimensions={len(embedding_data.embedding)}, "
                        f"tokens={embedding_data.token_usage['total_tokens']}, "
                        f"model={embedding_data.model}"
                    )

                except Exception as e:
                    # Caption embedding generation is non-fatal - log warning and continue
                    logger.warning(f"Caption embedding generation failed (non-fatal): {str(e)}", exc_info=True)
                    # caption_embedding and caption_embedding_generated_at will remain null in database

                # Generate Embedding 2: Conversational/Topic embedding (PRIMARY for collaborative discovery)
                # This combines caption fields + all 10 suggestion names + all 10 descriptions
                # Groups by conversation potential: "bar-room", "happy-hour", "brew-talk" cluster together
                try:
                    logger.info("Generating suggestions embedding (Embedding 2: Conversational/Topic - PRIMARY)")

                    # Convert Suggestion objects to dictionaries for embedding generation
                    suggestions_list = [
                        {
                            'name': s.name,
                            'description': s.description
                        }
                        for s in analysis_result.suggestions
                    ]

                    suggestions_embedding_data = generate_suggestions_embedding(
                        caption_full=caption_data.caption,
                        caption_visible_text=caption_data.visible_text,
                        caption_title=caption_data.title,
                        caption_category=caption_data.category,
                        suggestions=suggestions_list,  # All 10 suggestions with names + descriptions
                        model="text-embedding-3-small"
                    )

                    # Add suggestions embedding fields
                    caption_fields['suggestions_embedding'] = suggestions_embedding_data.embedding
                    caption_fields['suggestions_embedding_generated_at'] = timezone.now()

                    logger.info(
                        f"Suggestions embedding generated successfully: "
                        f"dimensions={len(suggestions_embedding_data.embedding)}, "
                        f"tokens={suggestions_embedding_data.token_usage['total_tokens']}, "
                        f"model={suggestions_embedding_data.model}"
                    )

                except Exception as e:
                    # Suggestions embedding generation is non-fatal - log warning and continue
                    logger.warning(f"Suggestions embedding generation failed (non-fatal): {str(e)}", exc_info=True)
                    # suggestions_embedding and suggestions_embedding_generated_at will remain null in database

            else:
                logger.info("No caption data available, caption fields will be empty")

            # Find similar existing chat rooms (collaborative discovery)
            # This runs after embeddings are generated (if caption data exists)
            similar_rooms = []
            if caption_fields.get('suggestions_embedding'):
                try:
                    logger.info("Searching for similar existing chat rooms")
                    similar_rooms = find_similar_rooms(
                        embedding_vector=caption_fields['suggestions_embedding'],
                        exclude_photo_id=None  # Will exclude after PhotoAnalysis is created
                    )
                    logger.info(f"Found {len(similar_rooms)} similar rooms")
                except Exception as e:
                    # Similarity search is non-fatal - log warning and continue
                    logger.warning(f"Similarity search failed (non-fatal): {str(e)}", exc_info=True)
                    similar_rooms = []
            else:
                logger.info("Skipping similarity search (no suggestions embedding available)")

            # Create PhotoAnalysis record
            photo_analysis = PhotoAnalysis.objects.create(
                image_phash=image_phash,
                file_hash=file_hash,
                file_size=file_size,
                image_path=storage_path,
                storage_type=storage_type,
                expires_at=expires_at,
                suggestions=suggestions_data,
                raw_response=analysis_result.raw_response,
                ai_vision_model=analysis_result.model,
                token_usage=analysis_result.token_usage,
                user=request.user if request.user.is_authenticated else None,
                fingerprint=fingerprint,
                ip_address=ip_address,
                **caption_fields  # Unpack caption fields (will be empty dict if no caption data)
            )

            # Serialize similar rooms for response
            similar_rooms_serializer = SimilarRoomSerializer(similar_rooms, many=True)

            # Return analysis result
            serializer = PhotoAnalysisDetailSerializer(
                photo_analysis,
                context={'request': request}
            )

            return Response({
                'cached': False,
                'analysis': serializer.data,
                'similar_rooms': similar_rooms_serializer.data
            }, status=status.HTTP_201_CREATED)

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
