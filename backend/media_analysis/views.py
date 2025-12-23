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

from .models import PhotoAnalysis, MusicAnalysis, Suggestion, LocationAnalysis, LocationSuggestionsCache
from .serializers import (
    PhotoAnalysisSerializer,
    PhotoAnalysisDetailSerializer,
    PhotoAnalysisListSerializer,
    PhotoUploadSerializer,
    PhotoUploadResponseSerializer,
)
from .utils.rate_limit import (
    media_analysis_rate_limit,
    location_rate_limit_check,
    get_client_identifier,
)
from .utils.location import get_or_fetch_location_suggestions, encode_location
from .utils.fingerprinting.image_hash import calculate_phash
from .utils.fingerprinting.file_hash import calculate_sha256, get_file_size
from .utils.vision.openai_vision import get_vision_provider
from .utils.image_processing import resize_image_if_needed
from .utils.suggestion_blending import blend_suggestions
from .utils.suggestion_matching import match_suggestions_to_existing, discover_related_suggestions
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

            # STEP 3: Discover related suggestions via K-NN (if enabled)
            # This finds existing suggestions semantically similar to the LLM's suggestions
            discovery_count = config.SUGGESTION_DISCOVERY_EXTRA_COUNT
            discovery_threshold = config.SUGGESTION_DISCOVERY_THRESHOLD

            discovered_suggestions = []
            if discovery_count > 0:
                logger.info("\n" + "="*80)
                logger.info("STEP 3: Discovering related suggestions via K-NN")
                logger.info("="*80)

                discovered_suggestions = discover_related_suggestions(
                    matched_suggestions=final_suggestions_list,
                    max_count=discovery_count,
                    threshold=discovery_threshold
                )

                if discovered_suggestions:
                    logger.info(f"Added {len(discovered_suggestions)} discovered suggestions")
                    final_suggestions_list = final_suggestions_list + discovered_suggestions
                else:
                    logger.info("No related suggestions discovered")

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


def _get_or_create_suggestion(name: str, key: str, description: str = '', is_proper_noun: bool = True) -> Suggestion:
    """
    Get or create a Suggestion by key.
    If it exists, increment usage_count. If not, create it.

    Args:
        name: Display name (e.g., "Taylor Swift")
        key: URL-safe slug (e.g., "taylor-swift")
        description: Optional description
        is_proper_noun: Whether this is a proper noun (default True for music)

    Returns:
        Suggestion instance
    """
    from django.utils.text import slugify

    # Ensure key is a valid slug
    if not key:
        key = slugify(name)

    # Truncate key if too long (max 100 chars)
    key = key[:100]

    suggestion, created = Suggestion.objects.get_or_create(
        key=key,
        defaults={
            'name': name,
            'description': description,
            'is_proper_noun': is_proper_noun,
            'embedding': None,  # Proper nouns don't need embeddings
        }
    )

    if not created:
        # Increment usage count for existing suggestion
        suggestion.increment_usage()

    return suggestion


class MusicAnalysisViewSet(viewsets.GenericViewSet):
    """
    ViewSet for music recognition operations.

    Endpoints:
    - POST /api/media-analysis/music/recognize/ - Recognize song from audio
    - GET /api/media-analysis/music/{id}/ - Get existing analysis
    - GET /api/media-analysis/music/recent/ - List recent analyses for current user
    """

    queryset = MusicAnalysis.objects.all()
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    @action(
        detail=False,
        methods=['post'],
        url_path='recognize'
    )
    @media_analysis_rate_limit
    def recognize(self, request):
        """
        Recognize a song from audio recording using ACRCloud API.
        Creates MusicAnalysis record and Suggestions for artist/song/album.

        Request (multipart/form-data):
            - audio: Audio file (required) - WebM, MP3, WAV, etc.
            - fingerprint: Browser fingerprint (optional)

        Response:
            {
                "success": true,
                "id": "uuid",
                "song": "Song Title",
                "artist": "Artist Name",
                "album": "Album Name",
                "release_date": "2023",
                "duration_ms": 180000,
                "score": 95,
                "external_ids": {
                    "spotify": "track_id",
                    "youtube": "video_id"
                },
                "suggestions": [
                    {"name": "Taylor Swift", "key": "taylor-swift", "type": "artist"},
                    {"name": "Shake It Off", "key": "shake-it-off", "type": "song"},
                    {"name": "1989", "key": "1989-taylor-swift", "type": "album"}
                ]
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

            # Fetch extended metadata (genres, album art, streaming links)
            # This checks cache first, then calls Metadata API if needed
            acr_id = result.get("acr_id")
            metadata = None
            genres = []
            if acr_id:
                from .utils.metadata import get_or_fetch_metadata
                metadata = get_or_fetch_metadata(
                    acr_id=acr_id,
                    song_title=result["song"],
                    artist=result["artist"]
                )
                if metadata:
                    genres = metadata.get("genres", [])

            # Get client identifiers for tracking
            user_id, fingerprint, ip_address = get_client_identifier(request)

            # Extract external IDs
            external_ids = result.get("external_ids", {})
            spotify_id = external_ids.get("spotify", "")
            youtube_id = external_ids.get("youtube", "")

            # Create MusicAnalysis record
            music_analysis = MusicAnalysis.objects.create(
                acr_id=result.get("acr_id"),
                song_title=result["song"],
                artist=result["artist"],
                album=result.get("album", ""),
                release_date=result.get("release_date", ""),
                duration_ms=result.get("duration_ms"),
                confidence_score=result.get("score", 0),
                spotify_track_id=spotify_id,
                youtube_video_id=youtube_id,
                raw_response=result.get("raw_response"),
                user_id=user_id,
                fingerprint=fingerprint,
                ip_address=ip_address,
            )

            # Create/find Suggestions for artist, song, album
            from django.utils.text import slugify
            suggestions_list = []

            # Artist suggestions - split featured artists into separate suggestions
            # "Zach Bryan, Kacey Musgraves" -> ["Zach Bryan", "Kacey Musgraves"]
            # "Daryl Hall & John Oates" -> ["Daryl Hall & John Oates"] (duo name stays together)
            artist_string = result["artist"]
            individual_artists = []
            if artist_string:
                # Split by comma to separate featured artists
                individual_artists = [a.strip() for a in artist_string.split(",") if a.strip()]

            # Create suggestion for each individual artist
            for artist_name in individual_artists:
                artist_key = slugify(artist_name)
                artist_suggestion = _get_or_create_suggestion(
                    name=artist_name,
                    key=artist_key,
                    description=f"Music by {artist_name}",
                    is_proper_noun=True
                )
                music_analysis.suggestions.add(artist_suggestion)
                suggestions_list.append({
                    "name": artist_name,
                    "key": artist_key,
                    "type": "artist"
                })

            # Song suggestion
            song_title = result["song"]
            if song_title:
                # Use primary artist (first) for song key to keep it unique but consistent
                primary_artist = individual_artists[0] if individual_artists else ""
                song_key = slugify(f"{song_title} {primary_artist}")[:100]
                song_suggestion = _get_or_create_suggestion(
                    name=song_title,
                    key=song_key,
                    description=f"'{song_title}' by {artist_string}",  # Full artist string for description
                    is_proper_noun=True
                )
                music_analysis.suggestions.add(song_suggestion)
                suggestions_list.append({
                    "name": song_title,
                    "key": song_key,
                    "type": "song"
                })

            # Note: Album is stored in MusicAnalysis record but NOT added to suggestions
            # ACRCloud returns the album of the specific recording (which may be a compilation,
            # remaster, or boxed set) rather than the original album. Artist and song are more
            # reliable and useful for chat suggestions.

            # Genre suggestions (from Metadata API)
            # Create chat suggestions for each genre (e.g., "Pop Music", "Rock Fans")
            for genre in genres:
                if genre:
                    genre_key = slugify(f"{genre}-music")[:100]
                    genre_suggestion = _get_or_create_suggestion(
                        name=f"{genre} Music",
                        key=genre_key,
                        description=f"Chat about {genre} music",
                        is_proper_noun=False  # Genres are generic categories
                    )
                    music_analysis.suggestions.add(genre_suggestion)
                    suggestions_list.append({
                        "name": f"{genre} Music",
                        "key": genre_key,
                        "type": "genre"
                    })

            # Build response
            response_data = {
                "success": True,
                "id": str(music_analysis.id),
                "song": result["song"],
                "artist": result["artist"],
                "album": result.get("album", ""),
                "release_date": result.get("release_date", ""),
                "duration_ms": result.get("duration_ms", 0),
                "score": result.get("score", 0),
                "external_ids": external_ids,
                "genres": genres,  # From Metadata API (cached)
                "suggestions": suggestions_list
            }

            logger.info(f"Audio recognition successful: {response_data['song']} by {response_data['artist']} (id={music_analysis.id})")
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Audio recognition failed: {str(e)}", exc_info=True)
            return Response(
                {"error": "Audio recognition failed", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(
        detail=False,
        methods=['get'],
        url_path='config'
    )
    def get_config(self, request):
        """
        Get frontend configuration for music recognition.

        Response:
            {
                "recording_duration_seconds": 8
            }
        """
        return Response({
            "recording_duration_seconds": config.MUSIC_RECOGNITION_DURATION_SECONDS
        })

    @action(
        detail=False,
        methods=['get'],
        url_path='recent'
    )
    def recent(self, request):
        """
        Get recent music analyses for the current user/session.
        """
        user_id, fingerprint, ip_address = get_client_identifier(request)

        # Build query based on available identifiers
        queryset = MusicAnalysis.objects.all()
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        elif fingerprint:
            queryset = queryset.filter(fingerprint=fingerprint)
        else:
            queryset = queryset.filter(ip_address=ip_address)

        # Limit results
        limit = min(int(request.query_params.get('limit', 10)), 50)
        queryset = queryset[:limit]

        # Build response
        results = []
        for analysis in queryset:
            results.append({
                "id": str(analysis.id),
                "song": analysis.song_title,
                "artist": analysis.artist,
                "album": analysis.album,
                "score": analysis.confidence_score,
                "created_at": analysis.created_at.isoformat(),
            })

        return Response(results)

    def retrieve(self, request, pk=None):
        """
        Get a specific music analysis by ID.
        """
        try:
            analysis = MusicAnalysis.objects.get(pk=pk)

            # Get linked suggestions
            suggestions_list = []
            for suggestion in analysis.suggestions.all():
                suggestions_list.append({
                    "name": suggestion.name,
                    "key": suggestion.key,
                })

            return Response({
                "id": str(analysis.id),
                "song": analysis.song_title,
                "artist": analysis.artist,
                "album": analysis.album,
                "release_date": analysis.release_date,
                "duration_ms": analysis.duration_ms,
                "score": analysis.confidence_score,
                "external_ids": {
                    "spotify": analysis.spotify_track_id,
                    "youtube": analysis.youtube_video_id,
                },
                "suggestions": suggestions_list,
                "selected_suggestion_code": analysis.selected_suggestion_code,
                "created_at": analysis.created_at.isoformat(),
            })
        except MusicAnalysis.DoesNotExist:
            return Response(
                {"error": "Music analysis not found"},
                status=status.HTTP_404_NOT_FOUND
            )


class LocationAnalysisViewSet(viewsets.GenericViewSet):
    """
    ViewSet for location-based chat suggestions.

    Endpoints:
    - POST /api/media-analysis/location/suggest/ - Get suggestions for coordinates
    - GET /api/media-analysis/location/{id}/ - Get existing analysis
    - GET /api/media-analysis/location/recent/ - List recent analyses for current user
    """

    queryset = LocationAnalysis.objects.all()
    permission_classes = [AllowAny]

    @action(
        detail=False,
        methods=['post'],
        url_path='suggest'
    )
    @location_rate_limit_check
    def suggest(self, request):
        """
        Get location-based chat suggestions from coordinates.

        Request (JSON):
            {
                "latitude": 37.7749,
                "longitude": -122.4194,
                "fingerprint": "optional-browser-fingerprint"
            }

        Response:
            {
                "success": true,
                "id": "uuid",
                "cached": true/false,
                "cache_source": "redis"|"postgresql"|"api",
                "location": {
                    "city": "San Francisco",
                    "neighborhood": "SoMa",
                    "geohash": "9q8yym"
                },
                "suggestions": [
                    {
                        "name": "San Francisco",
                        "key": "san-francisco",
                        "type": "city",
                        "description": "Chat about San Francisco"
                    },
                    {
                        "name": "Blue Bottle Coffee",
                        "key": "blue-bottle-coffee-sf",
                        "type": "venue",
                        "description": "Chat about Blue Bottle Coffee"
                    }
                ]
            }
        """
        try:
            # Validate coordinates
            latitude = request.data.get('latitude')
            longitude = request.data.get('longitude')

            if latitude is None or longitude is None:
                return Response(
                    {"error": "latitude and longitude are required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                latitude = float(latitude)
                longitude = float(longitude)
            except (TypeError, ValueError):
                return Response(
                    {"error": "latitude and longitude must be numbers"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate coordinate ranges
            if not (-90 <= latitude <= 90):
                return Response(
                    {"error": "latitude must be between -90 and 90"},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if not (-180 <= longitude <= 180):
                return Response(
                    {"error": "longitude must be between -180 and 180"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Get client identifiers for tracking
            user_id, fingerprint, ip_address = get_client_identifier(request)

            # Get location suggestions (checks cache first, then API)
            # Pass client identifiers for rate limiting (only counts API calls, not cache hits)
            result = get_or_fetch_location_suggestions(
                latitude, longitude,
                user_id=user_id,
                fingerprint=fingerprint,
                ip_address=ip_address,
            )

            if result is None:
                return Response(
                    {"error": "Location suggestions unavailable"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            # Extract location info
            location_info = result.get('location', {})
            city = location_info.get('city', '')
            neighborhood = location_info.get('neighborhood', '')
            county = location_info.get('county', '')
            metro_area = location_info.get('metro_area', '')
            geohash = location_info.get('geohash', encode_location(latitude, longitude))

            # Use suggestions directly from the cache result
            # The cache already builds a proper tiered list with venues, neighborhood, city, county, metro
            suggestions_list = result.get('suggestions', [])

            # Ensure Suggestion objects exist in database for linking
            for suggestion in suggestions_list:
                _get_or_create_suggestion(
                    name=suggestion.get('name', ''),
                    key=suggestion.get('key', ''),
                    description=suggestion.get('description', ''),
                    is_proper_noun=True
                )

            # Create LocationAnalysis record
            location_analysis = LocationAnalysis.objects.create(
                latitude=latitude,
                longitude=longitude,
                geohash=geohash,
                city_name=city or '',
                neighborhood_name=neighborhood or '',
                user_id=user_id,
                fingerprint=fingerprint,
                ip_address=ip_address,
                cache_hit=result.get('cached', False),
                cache_source=result.get('cache_source', 'api'),
            )

            # Link suggestions to the analysis
            for suggestion in suggestions_list:
                try:
                    suggestion_obj = Suggestion.objects.get(key=suggestion['key'])
                    location_analysis.suggestions.add(suggestion_obj)
                except Suggestion.DoesNotExist:
                    pass

            # Build response
            response_data = {
                "success": True,
                "id": str(location_analysis.id),
                "cached": result.get('cached', False),
                "cache_source": result.get('cache_source', 'api'),
                "location": {
                    "city": city,
                    "neighborhood": neighborhood,
                    "county": county,
                    "metro_area": metro_area,
                    "geohash": geohash,
                },
                "suggestions": suggestions_list
            }

            logger.info(
                f"Location analysis complete: {city or 'unknown'}/{neighborhood or 'unknown'} "
                f"(id={location_analysis.id}, suggestions={len(suggestions_list)}, "
                f"cached={result.get('cached', False)})"
            )

            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Location analysis failed: {str(e)}", exc_info=True)
            return Response(
                {"error": "Location analysis failed", "detail": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(
        detail=False,
        methods=['get'],
        url_path='recent'
    )
    def recent(self, request):
        """
        Get recent location analyses for the current user/session.
        """
        user_id, fingerprint, ip_address = get_client_identifier(request)

        # Build query based on available identifiers
        queryset = LocationAnalysis.objects.all()
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        elif fingerprint:
            queryset = queryset.filter(fingerprint=fingerprint)
        else:
            queryset = queryset.filter(ip_address=ip_address)

        # Limit results
        limit = min(int(request.query_params.get('limit', 10)), 50)
        queryset = queryset.order_by('-created_at')[:limit]

        # Build response
        results = []
        for analysis in queryset:
            results.append({
                "id": str(analysis.id),
                "city": analysis.city_name,
                "neighborhood": analysis.neighborhood_name,
                "geohash": analysis.geohash,
                "created_at": analysis.created_at.isoformat(),
            })

        return Response(results)

    def retrieve(self, request, pk=None):
        """
        Get a specific location analysis by ID.
        """
        try:
            analysis = LocationAnalysis.objects.get(pk=pk)

            # Get linked suggestions
            suggestions_list = []
            for suggestion in analysis.suggestions.all():
                suggestions_list.append({
                    "name": suggestion.name,
                    "key": suggestion.key,
                })

            return Response({
                "id": str(analysis.id),
                "latitude": analysis.latitude,
                "longitude": analysis.longitude,
                "geohash": analysis.geohash,
                "city": analysis.city_name,
                "neighborhood": analysis.neighborhood_name,
                "suggestions": suggestions_list,
                "selected_suggestion_code": analysis.selected_suggestion_code,
                "created_at": analysis.created_at.isoformat(),
            })
        except LocationAnalysis.DoesNotExist:
            return Response(
                {"error": "Location analysis not found"},
                status=status.HTTP_404_NOT_FOUND
            )

