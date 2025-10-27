"""
Django management command to test photo analysis upload end-to-end.

Usage:
    ./venv/bin/python manage.py test_photo_upload <image_filename>
    ./venv/bin/python manage.py test_photo_upload test_coffee_mug.jpeg
    ./venv/bin/python manage.py test_photo_upload test_coffee_mug.jpeg --no-cache
    ./venv/bin/python manage.py test_photo_upload --list
"""
import os
import json
import io
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from constance import config

from photo_analysis.models import PhotoAnalysis
from photo_analysis.utils.fingerprinting.file_hash import calculate_md5
from photo_analysis.utils.suggestion_blending import MAX_COSINE_DISTANCE
from pgvector.django import CosineDistance


class Command(BaseCommand):
    help = 'Test photo analysis upload with real images from fixtures directory'

    def add_arguments(self, parser):
        parser.add_argument(
            'filename',
            nargs='?',
            type=str,
            help='Image filename from photo_analysis/tests/fixtures/ directory'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all available test images'
        )
        parser.add_argument(
            '--fingerprint',
            type=str,
            default='cli-test-fp',
            help='Client fingerprint for rate limiting (default: cli-test-fp)'
        )
        parser.add_argument(
            '--no-cache',
            action='store_true',
            help='Delete any cached analysis for this image before uploading (forces fresh API calls)'
        )

    def handle(self, *args, **options):
        fixtures_dir = Path(__file__).parent.parent.parent / 'tests' / 'fixtures'
        
        # List available images
        if options['list']:
            self.stdout.write(self.style.SUCCESS('\nAvailable test images:'))
            for file in sorted(fixtures_dir.glob('*')):
                if file.is_file() and file.name != '.keep':
                    size_mb = file.stat().st_size / (1024 * 1024)
                    self.stdout.write(f"  - {file.name} ({size_mb:.2f} MB)")
            self.stdout.write('')
            return

        # Validate filename provided
        filename = options.get('filename')
        if not filename:
            raise CommandError(
                'Please provide an image filename or use --list to see available images.\n'
                'Example: ./venv/bin/python manage.py test_photo_upload test_coffee_mug.jpeg'
            )

        # Check if file exists
        image_path = fixtures_dir / filename
        if not image_path.exists():
            raise CommandError(
                f'Image "{filename}" not found in {fixtures_dir}\n'
                f'Use --list to see available images.'
            )

        # Read image file
        with open(image_path, 'rb') as f:
            image_bytes = f.read()

        # If --no-cache is set, delete any cached analyses for this image
        if options.get('no_cache'):
            # Calculate file hash to find cached entries
            image_file_for_hash = io.BytesIO(image_bytes)
            file_hash = calculate_md5(image_file_for_hash)

            # Delete cached analyses
            cached_analyses = PhotoAnalysis.objects.filter(file_hash=file_hash)
            count = cached_analyses.count()

            if count > 0:
                self.stdout.write(self.style.WARNING(f'\n--no-cache: Deleting {count} cached analysis record(s) for file_hash={file_hash}'))
                cached_analyses.delete()
                self.stdout.write(self.style.SUCCESS('Cache cleared. Fresh API calls will be made.\n'))
            else:
                self.stdout.write(self.style.SUCCESS('\n--no-cache: No cached records found for this image.\n'))

        # Determine content type
        ext = image_path.suffix.lower()
        content_type = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
        }.get(ext, 'image/jpeg')

        # Create multipart file upload
        uploaded_file = SimpleUploadedFile(
            name=filename,
            content=image_bytes,
            content_type=content_type
        )

        # POST to photo analysis API
        client = Client()
        fingerprint = options['fingerprint']
        
        self.stdout.write(self.style.WARNING(f'\n{"=" * 80}'))
        self.stdout.write(self.style.WARNING('PHOTO ANALYSIS END-TO-END TEST'))
        self.stdout.write(self.style.WARNING(f'{"=" * 80}\n'))
        
        self.stdout.write(f'Image: {filename}')
        self.stdout.write(f'Size: {len(image_bytes) / 1024:.2f} KB')
        self.stdout.write(f'Content-Type: {content_type}')
        self.stdout.write(f'Fingerprint: {fingerprint}')
        self.stdout.write(f'\nPOSTing to /api/photo-analysis/upload/...\n')

        response = client.post(
            '/api/photo-analysis/upload/',
            data={
                'image': uploaded_file,
                'fingerprint': fingerprint,
            },
            format='multipart'
        )

        # Display response
        self.stdout.write(self.style.WARNING(f'\n{"=" * 80}'))
        self.stdout.write(self.style.WARNING('RESPONSE'))
        self.stdout.write(self.style.WARNING(f'{"=" * 80}\n'))
        
        status_style = self.style.SUCCESS if response.status_code < 400 else self.style.ERROR
        self.stdout.write(status_style(f'Status Code: {response.status_code}'))
        
        try:
            data = response.json()

            # Pretty print JSON response
            self.stdout.write(f'\n{json.dumps(data, indent=2)}\n')

            # Highlight key information
            if response.status_code < 400:
                # Query database directly for internal fields (removed from API for security)
                analysis_id = data.get('analysis', {}).get('id')
                db_record = None
                if analysis_id:
                    try:
                        db_record = PhotoAnalysis.objects.get(id=analysis_id)
                    except PhotoAnalysis.DoesNotExist:
                        pass
                self.stdout.write(self.style.WARNING(f'\n{"=" * 80}'))
                self.stdout.write(self.style.WARNING('KEY INFORMATION'))
                self.stdout.write(self.style.WARNING(f'{"=" * 80}\n'))
                
                # Cached status
                cached = data.get('cached', False)
                cached_style = self.style.WARNING if cached else self.style.SUCCESS
                self.stdout.write(cached_style(f'Cached: {cached}'))
                
                # Analysis info
                analysis = data.get('analysis', {})
                if analysis:
                    self.stdout.write(f'\nAnalysis ID: {analysis.get("id")}')

                    # Internal fields (from database, not in API)
                    if db_record:
                        self.stdout.write(f'Model: {db_record.ai_vision_model} (DB)')
                        self.stdout.write(f'Storage: {db_record.storage_type} (DB)')
                        self.stdout.write(f'Times Used: {db_record.times_used} (DB)')

                    # Public fields (from API)
                    self.stdout.write(f'Image pHash: {analysis.get("image_phash")}')
                    self.stdout.write(f'File MD5: {analysis.get("file_hash")}')
                    self.stdout.write(f'File Size: {analysis.get("file_size")} bytes')
                    
                    # Token usage (from database)
                    if db_record and db_record.token_usage:
                        self.stdout.write(f'\nToken Usage: (DB)')
                        self.stdout.write(f'  Prompt: {db_record.token_usage.get("prompt_tokens")}')
                        self.stdout.write(f'  Completion: {db_record.token_usage.get("completion_tokens")}')
                        self.stdout.write(f'  Total: {db_record.token_usage.get("total_tokens")}')
                    
                    # Suggestions (with blended metadata)
                    suggestions = analysis.get('suggestions', [])
                    count = len(suggestions)
                    self.stdout.write(f'\nSuggestions Count: {count}')
                    if suggestions:
                        self.stdout.write(self.style.SUCCESS('\nChat Name Suggestions (Blended):'))

                        # Count by source type for summary
                        existing_rooms_count = sum(1 for s in suggestions if s.get('source') == 'existing_room')
                        popular_count = sum(1 for s in suggestions if s.get('source') == 'popular')
                        ai_count = sum(1 for s in suggestions if s.get('source') == 'ai')

                        self.stdout.write(f'  Sources: {existing_rooms_count} existing rooms, {popular_count} popular, {ai_count} fresh AI\n')

                        for i, suggestion in enumerate(suggestions, 1):
                            # Determine source styling
                            source = suggestion.get('source', 'unknown')
                            if source == 'existing_room':
                                source_label = self.style.SUCCESS('[EXISTING ROOM]')
                            elif source == 'popular':
                                source_label = self.style.WARNING('[POPULAR]')
                            else:
                                source_label = '[AI]'

                            # Main line: name, key, source
                            self.stdout.write(
                                f'  {i}. {self.style.SUCCESS(suggestion.get("name"))} '
                                f'(key: {suggestion.get("key")}) {source_label}'
                            )

                            # Description
                            if suggestion.get('description'):
                                self.stdout.write(f'     {suggestion.get("description")}')

                            # Additional metadata based on source
                            metadata_parts = []

                            # Existing room: show active users and room URL
                            if suggestion.get('has_room'):
                                active_users = suggestion.get('active_users', 0)
                                metadata_parts.append(f'{active_users} active user{"s" if active_users != 1 else ""}')
                                if suggestion.get('room_url'):
                                    metadata_parts.append(f'URL: {suggestion.get("room_url")}')

                            # Popular: show occurrence count
                            popularity_score = suggestion.get('popularity_score', 0)
                            if popularity_score > 0:
                                metadata_parts.append(f'seen in {popularity_score} similar photo{"s" if popularity_score != 1 else ""}')

                            if metadata_parts:
                                self.stdout.write(f'     {" | ".join(metadata_parts)}')

                    # Similar Rooms (collaborative discovery)
                    similar_rooms = data.get('similar_rooms', [])
                    if similar_rooms:
                        self.stdout.write(self.style.SUCCESS(f'\nSimilar Existing Rooms (Collaborative Discovery): {len(similar_rooms)} found'))
                        for i, room in enumerate(similar_rooms, 1):
                            self.stdout.write(
                                f'  {i}. {self.style.SUCCESS(room.get("room_name"))} '
                                f'({room.get("active_users")} active user{"s" if room.get("active_users") != 1 else ""})'
                            )
                            self.stdout.write(f'     Code: {room.get("room_code")}')
                            self.stdout.write(f'     URL: {room.get("room_url")}')
                            self.stdout.write(f'     Similarity: {room.get("similarity_distance"):.4f} (cosine distance)')
                            self.stdout.write(f'     Source Photo ID: {room.get("source_photo_id")}')
                    else:
                        self.stdout.write(self.style.WARNING('\nNo similar existing rooms found'))

                    # Caption Data (generated in parallel with suggestions)
                    caption_title = analysis.get('caption_title', '')
                    caption_category = analysis.get('caption_category', '')
                    caption_visible_text = analysis.get('caption_visible_text', '')
                    caption_full = analysis.get('caption_full', '')
                    caption_generated_at = analysis.get('caption_generated_at')

                    if caption_title or caption_full:
                        self.stdout.write(self.style.SUCCESS('\nCaption Data (for embeddings):'))
                        if caption_title:
                            self.stdout.write(f'  Title: {self.style.SUCCESS(caption_title)}')
                        if caption_category:
                            self.stdout.write(f'  Category: {caption_category}')
                        if caption_visible_text:
                            self.stdout.write(f'  Visible Text: "{caption_visible_text}"')
                        if caption_full:
                            self.stdout.write(f'  Full Caption: {caption_full}')
                        if caption_generated_at:
                            self.stdout.write(f'  Generated At: {caption_generated_at}')

                        # Caption Model and Token Usage (from database)
                        if db_record:
                            if db_record.caption_model:
                                self.stdout.write(f'  Model: {db_record.caption_model} (DB)')
                            if db_record.caption_token_usage:
                                self.stdout.write(f'\nCaption Token Usage: (DB)')
                                self.stdout.write(f'  Prompt: {db_record.caption_token_usage.get("prompt_tokens")}')
                                self.stdout.write(f'  Completion: {db_record.caption_token_usage.get("completion_tokens")}')
                                self.stdout.write(f'  Total: {db_record.caption_token_usage.get("total_tokens")}')
                    else:
                        self.stdout.write(self.style.WARNING('\nCaption Data: Not generated (disabled or failed)'))

                    # Embedding Data (two types generated from captions) - from database
                    if db_record:
                        # Embedding 1: Caption/Semantic (broad clustering)
                        if db_record.caption_embedding_generated_at:
                            self.stdout.write(self.style.SUCCESS('\n✓ Embedding 1 (Caption/Semantic): Generated (DB)'))
                            self.stdout.write(f'  Dimensions: 1536 (text-embedding-3-small)')
                            self.stdout.write(f'  Generated At: {db_record.caption_embedding_generated_at}')
                            self.stdout.write(f'  Source: caption fields (title, category, visible_text, full)')
                            self.stdout.write(f'  Purpose: Broad categorization by visual content')
                        else:
                            if caption_title or caption_full:
                                self.stdout.write(self.style.WARNING('\n✗ Embedding 1 (Caption/Semantic): Not generated (failed or disabled)'))
                            else:
                                self.stdout.write(self.style.WARNING('\n✗ Embedding 1 (Caption/Semantic): Not generated (no captions available)'))

                        # Embedding 2: Suggestions/Topic (PRIMARY for collaborative discovery)
                        if db_record.suggestions_embedding_generated_at:
                            self.stdout.write(self.style.SUCCESS('\n✓ Embedding 2 (Suggestions/Topic - PRIMARY): Generated (DB)'))
                            self.stdout.write(f'  Dimensions: 1536 (text-embedding-3-small)')
                            self.stdout.write(f'  Generated At: {db_record.suggestions_embedding_generated_at}')
                            self.stdout.write(f'  Source: captions + all 10 suggestion names + descriptions')
                            self.stdout.write(f'  Purpose: Collaborative discovery - finding similar chat rooms')
                            self.stdout.write(f'  How: "bar-room", "happy-hour", "brew-talk" cluster together')
                        else:
                            if caption_title or caption_full:
                                self.stdout.write(self.style.WARNING('\n✗ Embedding 2 (Suggestions/Topic - PRIMARY): Not generated (failed or disabled)'))
                            else:
                                self.stdout.write(self.style.WARNING('\n✗ Embedding 2 (Suggestions/Topic - PRIMARY): Not generated (no captions available)'))

                        # EMBEDDING SIMILARITY ANALYSIS
                        # Show top 10 most similar photos for each embedding type
                        self.stdout.write(self.style.WARNING(f'\n{"=" * 80}'))
                        self.stdout.write(self.style.WARNING('EMBEDDING SIMILARITY ANALYSIS'))
                        self.stdout.write(self.style.WARNING(f'{"=" * 80}\n'))

                        # Embedding 1: Caption/Semantic Similarity
                        if db_record.caption_embedding is not None:
                            self.stdout.write(self.style.SUCCESS('Top 10 Similar Photos (Embedding 1: Caption/Semantic)'))
                            self.stdout.write('Purpose: Visual content similarity - "what\'s in the image"\n')

                            similar_caption = PhotoAnalysis.objects.annotate(
                                distance=CosineDistance('caption_embedding', db_record.caption_embedding)
                            ).filter(
                                caption_embedding__isnull=False
                            ).exclude(
                                id=db_record.id  # Exclude the uploaded photo itself
                            ).order_by('distance')[:10]

                            if similar_caption.exists():
                                for i, photo in enumerate(similar_caption, 1):
                                    self.stdout.write(
                                        f'  {i}. Distance: {photo.distance:.4f} | '
                                        f'Title: {self.style.SUCCESS(photo.caption_title or "N/A")} | '
                                        f'Category: {photo.caption_category or "N/A"}'
                                    )
                                    self.stdout.write(f'     ID: {photo.id} | pHash: {photo.image_phash}')
                                    if photo.caption_full:
                                        # Truncate long captions
                                        caption_preview = photo.caption_full[:100] + '...' if len(photo.caption_full) > 100 else photo.caption_full
                                        self.stdout.write(f'     Caption: {caption_preview}')
                            else:
                                self.stdout.write('  No other photos with caption embeddings found in database')
                        else:
                            self.stdout.write(self.style.WARNING('Embedding 1 (Caption/Semantic): Not available - cannot show similarity'))

                        # Embedding 2: Suggestions/Topic Similarity (PRIMARY)
                        if db_record.suggestions_embedding is not None:
                            # Use hardcoded distance cutoff from suggestion_blending module (matches production K-NN query)
                            max_distance = MAX_COSINE_DISTANCE  # 0.4 (from suggestion_blending.py)

                            self.stdout.write(self.style.SUCCESS('\nTop 10 Similar Photos (Embedding 2: Suggestions/Topic - PRIMARY)'))
                            self.stdout.write(f'Purpose: Conversation similarity - "what people might chat about"')
                            self.stdout.write(f'Distance cutoff: {max_distance} (photos farther than this are NOT used for popular suggestions)\n')

                            similar_suggestions = PhotoAnalysis.objects.annotate(
                                distance=CosineDistance('suggestions_embedding', db_record.suggestions_embedding)
                            ).filter(
                                suggestions_embedding__isnull=False,
                                distance__lt=max_distance  # Only show photos within clustering distance
                            ).exclude(
                                id=db_record.id  # Exclude the uploaded photo itself
                            ).order_by('distance')[:10]

                            if similar_suggestions.exists():
                                for i, photo in enumerate(similar_suggestions, 1):
                                    # Get first 3 suggestion names for preview
                                    suggestion_names = []
                                    if photo.suggestions and 'suggestions' in photo.suggestions:
                                        for sug in photo.suggestions['suggestions'][:3]:
                                            suggestion_names.append(sug.get('name', ''))
                                    suggestions_preview = ', '.join(suggestion_names) if suggestion_names else 'N/A'

                                    self.stdout.write(
                                        f'  {i}. Distance: {photo.distance:.4f} | '
                                        f'Title: {self.style.SUCCESS(photo.caption_title or "N/A")} | '
                                        f'Category: {photo.caption_category or "N/A"}'
                                    )
                                    self.stdout.write(f'     ID: {photo.id} | pHash: {photo.image_phash}')
                                    self.stdout.write(f'     Top Suggestions: {suggestions_preview}')
                            else:
                                self.stdout.write('  No other photos with suggestion embeddings found in database')
                        else:
                            self.stdout.write(self.style.WARNING('\nEmbedding 2 (Suggestions/Topic): Not available - cannot show similarity'))

                # Rate limit info
                rate_limit = data.get('rate_limit', {})
                if rate_limit:
                    self.stdout.write(f'\nRate Limit:')
                    self.stdout.write(f'  Used: {rate_limit.get("used")} / {rate_limit.get("limit")}')
                    self.stdout.write(f'  Remaining: {rate_limit.get("remaining")}')
                
                self.stdout.write(self.style.SUCCESS(f'\n{"=" * 80}'))
                self.stdout.write(self.style.SUCCESS('✓ Upload successful!'))
                self.stdout.write(self.style.SUCCESS(f'{"=" * 80}\n'))
            else:
                # Error response
                self.stdout.write(self.style.ERROR(f'\n{"=" * 80}'))
                self.stdout.write(self.style.ERROR('✗ Upload failed!'))
                self.stdout.write(self.style.ERROR(f'{"=" * 80}\n'))
                
                if 'error' in data:
                    self.stdout.write(self.style.ERROR(f'Error: {data["error"]}'))
                if 'detail' in data:
                    self.stdout.write(self.style.ERROR(f'Detail: {data["detail"]}'))
                    
        except json.JSONDecodeError:
            self.stdout.write(self.style.ERROR('Response is not JSON:'))
            self.stdout.write(response.content.decode('utf-8'))
