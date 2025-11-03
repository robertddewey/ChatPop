"""
Management command to generate name embeddings for existing AI-generated chat rooms.

This enables existing rooms to participate in suggestion normalization during photo uploads.
Only processes rooms where source='ai' (collaborative discovery rooms), not manual user rooms.

Usage:
    ./venv/bin/python manage.py generate_room_embeddings
    ./venv/bin/python manage.py generate_room_embeddings --limit 100
    ./venv/bin/python manage.py generate_room_embeddings --force-refresh
    ./venv/bin/python manage.py generate_room_embeddings --dry-run
"""

import logging
from django.core.management.base import BaseCommand
from django.db.models import Q
from chats.models import ChatRoom
from photo_analysis.utils.room_matching import generate_room_embedding

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Generate name embeddings for existing AI-generated chat rooms. "
        "Only processes rooms where source='ai' (collaborative discovery rooms)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Maximum number of rooms to process (default: all)'
        )
        parser.add_argument(
            '--force-refresh',
            action='store_true',
            help='Regenerate embeddings for rooms that already have them'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be done without making changes'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of API calls to make in each batch (default: 10)'
        )

    def handle(self, *args, **options):
        limit = options['limit']
        force_refresh = options['force_refresh']
        dry_run = options['dry_run']
        batch_size = options['batch_size']

        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('ROOM EMBEDDING GENERATION'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write('')

        # Build query: Only AI-generated rooms, active only
        query = ChatRoom.objects.filter(
            source=ChatRoom.SOURCE_AI,  # CRITICAL: Only AI rooms, not manual
            is_active=True
        )

        # Filter by embedding status
        if force_refresh:
            self.stdout.write('Mode: Force refresh (regenerate all embeddings)')
        else:
            query = query.filter(name_embedding__isnull=True)
            self.stdout.write('Mode: Generate missing embeddings only')

        # Apply limit
        if limit:
            query = query[:limit]
            self.stdout.write(f'Limit: {limit} rooms')
        else:
            self.stdout.write('Limit: All rooms')

        # Count rooms
        total_rooms = query.count()

        if total_rooms == 0:
            self.stdout.write(self.style.WARNING('No rooms need embeddings.'))
            self.stdout.write('')
            self.stdout.write('Reasons this might happen:')
            self.stdout.write('  - All AI rooms already have embeddings')
            self.stdout.write('  - No AI-generated rooms exist yet')
            self.stdout.write('  - Use --force-refresh to regenerate existing embeddings')
            return

        self.stdout.write('')
        self.stdout.write(f'Found {total_rooms} AI-generated rooms needing embeddings')
        self.stdout.write('')

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
            self.stdout.write('')
            self.stdout.write('Rooms that would be processed:')
            for room in query[:10]:
                status = '✓ has embedding' if room.name_embedding else '○ no embedding'
                self.stdout.write(f'  {status} - {room.name} ({room.code})')
            if total_rooms > 10:
                self.stdout.write(f'  ... and {total_rooms - 10} more')
            self.stdout.write('')
            self.stdout.write('Run without --dry-run to process these rooms.')
            return

        # Process rooms in batches
        self.stdout.write(f'Processing {total_rooms} rooms in batches of {batch_size}...')
        self.stdout.write('')

        success_count = 0
        error_count = 0

        for i, room in enumerate(query, start=1):
            try:
                # Generate embedding (name + description for better semantic matching)
                self.stdout.write(f'[{i}/{total_rooms}] Processing: {room.name} ({room.code})', ending='')

                embedding = generate_room_embedding(room.name, room.description)

                # Save to database
                room.name_embedding = embedding
                room.save(update_fields=['name_embedding'])

                self.stdout.write(self.style.SUCCESS(' ✓'))
                success_count += 1

                # Pause every batch_size to avoid rate limits
                if i % batch_size == 0 and i < total_rooms:
                    import time
                    self.stdout.write('  (Pausing 1s to avoid rate limits...)')
                    time.sleep(1)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f' ✗ Error: {str(e)}'))
                logger.error(f'Failed to generate embedding for room {room.id}: {str(e)}', exc_info=True)
                error_count += 1
                continue

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(f'Total rooms processed: {total_rooms}')
        self.stdout.write(self.style.SUCCESS(f'✓ Success: {success_count}'))
        if error_count > 0:
            self.stdout.write(self.style.ERROR(f'✗ Errors: {error_count}'))
        else:
            self.stdout.write('✗ Errors: 0')
        self.stdout.write('')

        # Cost estimate
        # text-embedding-3-small: $0.00002 per 1K tokens
        # Average room name ~5 tokens
        estimated_tokens = success_count * 5
        estimated_cost = (estimated_tokens / 1000) * 0.00002
        self.stdout.write(f'Estimated cost: ~${estimated_cost:.6f} (≈{estimated_tokens} tokens)')
        self.stdout.write('')

        if success_count > 0:
            self.stdout.write(self.style.SUCCESS('✓ Room embeddings generated successfully!'))
            self.stdout.write('')
            self.stdout.write('These rooms can now participate in suggestion normalization.')
        else:
            self.stdout.write(self.style.WARNING('No embeddings were generated.'))
