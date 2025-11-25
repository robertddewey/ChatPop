"""
Django management command to regenerate embeddings for existing PhotoAnalysis records.

Usage:
    # Regenerate all embeddings
    ./venv/bin/python manage.py regenerate_embeddings

    # Dry run (preview only, no changes)
    ./venv/bin/python manage.py regenerate_embeddings --dry-run

    # Regenerate specific photo by ID
    ./venv/bin/python manage.py regenerate_embeddings --photo-id UUID

    # Process in smaller batches
    ./venv/bin/python manage.py regenerate_embeddings --batch-size 10

Why this is needed:
    When you modify the embedding generation logic (e.g., changing text construction
    in _combine_suggestions_with_captions), all existing embeddings become incompatible
    with new embeddings because they're based on different input text.

    This command regenerates ALL embeddings using the CURRENT embedding functions,
    ensuring all vectors are comparable in semantic space.
"""
import logging
from constance import config
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from media_analysis.models import PhotoAnalysis
from media_analysis.utils.embedding import generate_embedding, generate_suggestions_embedding

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Regenerate caption and suggestions embeddings for existing PhotoAnalysis records'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be updated without making changes',
        )
        parser.add_argument(
            '--photo-id',
            type=str,
            help='Regenerate embeddings for a specific photo ID (UUID)',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Number of photos to process in each batch (default: 50)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        photo_id = options['photo_id']
        batch_size = options['batch_size']

        # Header
        self.stdout.write(self.style.SUCCESS('=' * 70))
        self.stdout.write(self.style.SUCCESS('Photo Embeddings Regeneration Tool'))
        self.stdout.write(self.style.SUCCESS('=' * 70))

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN MODE - No changes will be made\n'))

        # Display constance settings status
        caption_embedding_enabled = config.PHOTO_ANALYSIS_ENABLE_CAPTION_EMBEDDING
        self.stdout.write(f'Caption embedding generation: {"ENABLED" if caption_embedding_enabled else "DISABLED (config setting)"}\n')

        # Build queryset
        if photo_id:
            # Single photo regeneration
            queryset = PhotoAnalysis.objects.filter(id=photo_id)
            if not queryset.exists():
                raise CommandError(f'Photo with ID {photo_id} not found')
            self.stdout.write(f'Target: Single photo (ID: {photo_id})\n')
        else:
            # All photos with caption data (required for embeddings)
            queryset = PhotoAnalysis.objects.filter(
                caption_full__isnull=False
            ).exclude(caption_full='')
            self.stdout.write(f'Target: All photos with caption data\n')

        total_count = queryset.count()

        if total_count == 0:
            self.stdout.write(self.style.WARNING('No photos found to process.'))
            return

        self.stdout.write(f'Total photos to process: {total_count}\n')

        # Statistics
        stats = {
            'total': total_count,
            'caption_updated': 0,
            'suggestions_updated': 0,
            'skipped': 0,
            'failed': 0,
        }

        # Process in batches
        self.stdout.write(self.style.SUCCESS('\nProcessing photos...\n'))

        for i in range(0, total_count, batch_size):
            batch = queryset[i:i + batch_size]

            for photo in batch:
                self.stdout.write(f'[{stats["caption_updated"] + stats["suggestions_updated"] + stats["skipped"] + stats["failed"] + 1}/{total_count}] Processing {photo.id}...')

                try:
                    # Check if photo has required caption data
                    if not photo.caption_full:
                        self.stdout.write(self.style.WARNING(f'  ⊘ Skipped (no caption data)'))
                        stats['skipped'] += 1
                        continue

                    # Regenerate caption embedding (Embedding 1: Semantic/Content)
                    # Only if PHOTO_ANALYSIS_ENABLE_CAPTION_EMBEDDING is enabled
                    caption_updated = False
                    if photo.caption_full and config.PHOTO_ANALYSIS_ENABLE_CAPTION_EMBEDDING:
                        try:
                            if not dry_run:
                                caption_embedding_data = generate_embedding(
                                    caption_full=photo.caption_full or '',
                                    caption_visible_text=photo.caption_visible_text or '',
                                    caption_title=photo.caption_title or '',
                                    caption_category=photo.caption_category or '',
                                    model="text-embedding-3-small"
                                )
                                photo.caption_embedding = caption_embedding_data.embedding
                                photo.caption_embedding_generated_at = timezone.now()
                                caption_updated = True
                                self.stdout.write(f'  ✓ Caption embedding regenerated')
                            else:
                                self.stdout.write(f'  ✓ Caption embedding (DRY RUN)')
                                caption_updated = True
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f'  ✗ Caption embedding failed: {str(e)}'))
                    elif photo.caption_full and not config.PHOTO_ANALYSIS_ENABLE_CAPTION_EMBEDDING:
                        self.stdout.write(f'  ⊘ Caption embedding skipped (disabled in config)')

                    # Regenerate suggestions embedding (Embedding 2: Conversational/Topic - PRIMARY)
                    suggestions_updated = False
                    if photo.caption_full and photo.suggestions:
                        try:
                            # Extract suggestions list from JSON field
                            suggestions_data = photo.suggestions
                            if isinstance(suggestions_data, dict):
                                suggestions_list = suggestions_data.get('suggestions', [])
                            elif isinstance(suggestions_data, list):
                                suggestions_list = suggestions_data
                            else:
                                suggestions_list = []

                            if suggestions_list and not dry_run:
                                suggestions_embedding_data = generate_suggestions_embedding(
                                    caption_full=photo.caption_full or '',
                                    caption_visible_text=photo.caption_visible_text or '',
                                    caption_title=photo.caption_title or '',
                                    caption_category=photo.caption_category or '',
                                    suggestions=suggestions_list,
                                    model="text-embedding-3-small"
                                )
                                photo.suggestions_embedding = suggestions_embedding_data.embedding
                                photo.suggestions_embedding_generated_at = timezone.now()
                                suggestions_updated = True
                                self.stdout.write(f'  ✓ Suggestions embedding regenerated')
                            elif suggestions_list:
                                self.stdout.write(f'  ✓ Suggestions embedding (DRY RUN)')
                                suggestions_updated = True
                            else:
                                self.stdout.write(self.style.WARNING(f'  ⊘ No suggestions found'))
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f'  ✗ Suggestions embedding failed: {str(e)}'))

                    # Save changes
                    if not dry_run and (caption_updated or suggestions_updated):
                        photo.save()

                    # Update stats
                    if caption_updated:
                        stats['caption_updated'] += 1
                    if suggestions_updated:
                        stats['suggestions_updated'] += 1

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  ✗ Failed: {str(e)}'))
                    stats['failed'] += 1
                    logger.error(f'Failed to regenerate embeddings for photo {photo.id}: {str(e)}', exc_info=True)

        # Summary
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('Summary'))
        self.stdout.write('=' * 70)
        self.stdout.write(f'Total processed:           {stats["total"]}')
        self.stdout.write(f'Caption embeddings:        {stats["caption_updated"]} updated')
        self.stdout.write(f'Suggestions embeddings:    {stats["suggestions_updated"]} updated')
        self.stdout.write(f'Skipped (no data):         {stats["skipped"]}')
        self.stdout.write(f'Failed:                    {stats["failed"]}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No changes were saved to database'))
        else:
            self.stdout.write(self.style.SUCCESS('\nAll changes saved to database'))

        self.stdout.write('=' * 70 + '\n')
