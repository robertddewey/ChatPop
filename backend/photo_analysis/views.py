"""
DRF Views for Photo Analysis API.
"""
import logging
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
)
from .utils.rate_limit import photo_analysis_rate_limit, get_client_identifier
from .utils.fingerprinting.image_hash import calculate_phash
from .utils.fingerprinting.file_hash import calculate_md5, get_file_size
from .utils.vision.openai_vision import get_vision_provider
from .utils.image_processing import resize_image_if_needed
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
                serializer = PhotoAnalysisDetailSerializer(
                    existing_analysis,
                    context={'request': request}
                )
                return Response({
                    'cached': True,
                    'analysis': serializer.data
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

            # Analyze image with OpenAI Vision
            # Use resized image (or original if no resize was needed)
            logger.info(f"Analyzing image with {vision_provider.get_model_name()}")
            resized_image.seek(0)
            analysis_result = vision_provider.analyze_image(
                image_file=resized_image,
                prompt=config.PHOTO_ANALYSIS_PROMPT,
                max_suggestions=10
            )

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
                ip_address=ip_address
            )

            # Return analysis result
            serializer = PhotoAnalysisDetailSerializer(
                photo_analysis,
                context={'request': request}
            )

            return Response({
                'cached': False,
                'analysis': serializer.data
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
