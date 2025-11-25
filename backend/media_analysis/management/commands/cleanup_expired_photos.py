"""
Management command to clean up expired photo analysis records.

This command:
1. Finds all PhotoAnalysis records where expires_at < now()
2. Deletes the associated image files from S3 or local storage
3. Deletes the database records

Usage:
    ./manage.py cleanup_expired_photos [--dry-run] [--batch-size=100]

Options:
    --dry-run: Show what would be deleted without actually deleting
    --batch-size: Number of records to process at once (default: 100)
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from media_analysis.models import PhotoAnalysis
from chatpop.utils.media import MediaStorage

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Delete expired photo analysis records and their associated image files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of records to process at once (default: 100)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No files will be deleted'))

        # Get expired photos
        now = timezone.now()
        expired_photos = PhotoAnalysis.objects.filter(
            expires_at__isnull=False,
            expires_at__lt=now
        ).order_by('expires_at')

        total_count = expired_photos.count()

        if total_count == 0:
            self.stdout.write(self.style.SUCCESS('No expired photos found'))
            return

        self.stdout.write(f'Found {total_count} expired photo(s)')

        # Initialize storage handler
        storage = MediaStorage()

        # Track statistics
        deleted_count = 0
        s3_deleted = 0
        local_deleted = 0
        storage_errors = 0
        db_deleted = 0

        # Process in batches
        for i in range(0, total_count, batch_size):
            batch = expired_photos[i:i + batch_size]

            for photo in batch:
                try:
                    # Log the photo being processed
                    age_days = (now - photo.created_at).days
                    self.stdout.write(
                        f'  Processing: {photo.id} (created {age_days} days ago, '
                        f'expired {(now - photo.expires_at).days} days ago)'
                    )

                    # Delete file from storage
                    if not dry_run:
                        if photo.storage_type == 's3':
                            success = storage.delete_from_s3(photo.image_path)
                            if success:
                                s3_deleted += 1
                                self.stdout.write(
                                    self.style.SUCCESS(f'    ✓ Deleted from S3: {photo.image_path}')
                                )
                            else:
                                storage_errors += 1
                                self.stdout.write(
                                    self.style.WARNING(f'    ✗ Failed to delete from S3: {photo.image_path}')
                                )
                        else:  # local storage
                            success = storage.delete_local(photo.image_path)
                            if success:
                                local_deleted += 1
                                self.stdout.write(
                                    self.style.SUCCESS(f'    ✓ Deleted from local: {photo.image_path}')
                                )
                            else:
                                storage_errors += 1
                                self.stdout.write(
                                    self.style.WARNING(f'    ✗ Failed to delete from local: {photo.image_path}')
                                )

                        # Delete database record
                        photo.delete()
                        db_deleted += 1
                        self.stdout.write(
                            self.style.SUCCESS(f'    ✓ Deleted database record: {photo.id}')
                        )
                    else:
                        # Dry run - just show what would be deleted
                        self.stdout.write(
                            f'    [DRY RUN] Would delete {photo.storage_type}: {photo.image_path}'
                        )

                    deleted_count += 1

                except Exception as e:
                    logger.error(f'Error cleaning up photo {photo.id}: {str(e)}', exc_info=True)
                    self.stdout.write(
                        self.style.ERROR(f'    ✗ Error: {str(e)}')
                    )
                    storage_errors += 1

        # Print summary
        self.stdout.write('\n' + '='*60)
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN SUMMARY'))
            self.stdout.write(f'Would delete {total_count} expired photo(s)')
        else:
            self.stdout.write(self.style.SUCCESS('CLEANUP SUMMARY'))
            self.stdout.write(f'Total expired photos: {total_count}')
            self.stdout.write(f'Database records deleted: {db_deleted}')
            self.stdout.write(f'S3 files deleted: {s3_deleted}')
            self.stdout.write(f'Local files deleted: {local_deleted}')
            if storage_errors > 0:
                self.stdout.write(self.style.WARNING(f'Storage errors: {storage_errors}'))

        self.stdout.write('='*60)
