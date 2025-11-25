"""
Django management command to batch process multiple photos from fixtures in a specified order.

Usage:
    ./venv/bin/python manage.py batch_photo_upload photo_sequence.json
    ./venv/bin/python manage.py batch_photo_upload photo_sequence.json --no-cache
    ./venv/bin/python manage.py batch_photo_upload photo_sequence.json --fingerprint=batch-test-fp
    ./venv/bin/python manage.py batch_photo_upload photo_sequence.json --delay=2

JSON file format:
    {
      "photos": [
        "test_coffee_mug.jpeg",
        "test_budweiser_can.jpeg",
        "test_glass_of_beer.png"
      ]
    }
"""
import json
import time
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.core.management import call_command
from io import StringIO


class Command(BaseCommand):
    help = 'Batch process multiple photos from fixtures directory in specified order using a JSON config file'

    def add_arguments(self, parser):
        parser.add_argument(
            'json_file',
            type=str,
            help='Path to JSON file with ordered list of photo filenames'
        )
        parser.add_argument(
            '--fingerprint',
            type=str,
            default='batch-test-fp',
            help='Client fingerprint for all uploads (default: batch-test-fp)'
        )
        parser.add_argument(
            '--no-cache',
            action='store_true',
            help='Clear cache for all photos before processing (forces fresh API calls)'
        )
        parser.add_argument(
            '--delay',
            type=float,
            default=0,
            help='Delay in seconds between each upload (default: 0)'
        )

    def handle(self, *args, **options):
        json_file = options['json_file']
        fingerprint = options['fingerprint']
        no_cache = options.get('no_cache', False)
        delay = options.get('delay', 0)

        # Check if JSON file exists
        json_path = Path(json_file)
        if not json_path.exists():
            raise CommandError(f'JSON file "{json_file}" not found')

        # Read and parse JSON
        try:
            with open(json_path, 'r') as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            raise CommandError(f'Invalid JSON in {json_file}: {str(e)}')

        # Validate JSON structure
        if 'photos' not in config:
            raise CommandError(
                f'JSON file must contain a "photos" array. '
                f'Format: {{"photos": ["photo1.jpg", "photo2.png"]}}'
            )

        photos = config['photos']
        if not isinstance(photos, list):
            raise CommandError('"photos" must be an array of filenames')

        if len(photos) == 0:
            raise CommandError('No photos specified in JSON file')

        # Display batch configuration
        self.stdout.write(self.style.WARNING('\n' + '=' * 80))
        self.stdout.write(self.style.WARNING('BATCH PHOTO UPLOAD'))
        self.stdout.write(self.style.WARNING('=' * 80 + '\n'))

        self.stdout.write(f'Config File: {json_file}')
        self.stdout.write(f'Photos to Process: {len(photos)}')
        self.stdout.write(f'Fingerprint: {fingerprint}')
        self.stdout.write(f'Clear Cache: {no_cache}')
        self.stdout.write(f'Delay Between Uploads: {delay}s')

        self.stdout.write('\nPhoto Sequence:')
        for i, photo in enumerate(photos, 1):
            self.stdout.write(f'  {i}. {photo}')

        self.stdout.write('\n' + '=' * 80 + '\n')

        # Process each photo
        successful = 0
        failed = 0
        failed_photos = []

        for i, photo in enumerate(photos, 1):
            self.stdout.write(self.style.SUCCESS(f'\n[{i}/{len(photos)}] Processing: {photo}'))
            self.stdout.write('-' * 80 + '\n')

            try:
                # Call test_photo_upload for this photo
                # Capture its output to avoid cluttering the batch summary
                call_command(
                    'test_photo_upload',
                    photo,
                    fingerprint=fingerprint,
                    no_cache=no_cache,
                    stdout=self.stdout,  # Pass through stdout so we see the output
                    stderr=self.stderr,
                )

                successful += 1
                self.stdout.write(self.style.SUCCESS(f'\n✓ [{i}/{len(photos)}] {photo} - SUCCESS\n'))

            except Exception as e:
                failed += 1
                failed_photos.append((photo, str(e)))
                self.stdout.write(self.style.ERROR(f'\n✗ [{i}/{len(photos)}] {photo} - FAILED: {str(e)}\n'))

            # Delay before next upload (except after the last one)
            if delay > 0 and i < len(photos):
                self.stdout.write(f'\nWaiting {delay}s before next upload...\n')
                time.sleep(delay)

        # Display final summary
        self.stdout.write(self.style.WARNING('\n' + '=' * 80))
        self.stdout.write(self.style.WARNING('BATCH UPLOAD SUMMARY'))
        self.stdout.write(self.style.WARNING('=' * 80 + '\n'))

        self.stdout.write(f'Total Photos: {len(photos)}')
        self.stdout.write(self.style.SUCCESS(f'Successful: {successful}'))

        if failed > 0:
            self.stdout.write(self.style.ERROR(f'Failed: {failed}'))
            self.stdout.write('\nFailed Photos:')
            for photo, error in failed_photos:
                self.stdout.write(self.style.ERROR(f'  - {photo}: {error}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'Failed: 0'))

        self.stdout.write('\n' + '=' * 80 + '\n')

        if failed > 0:
            self.stdout.write(self.style.WARNING(f'✓ Batch completed with {failed} failure(s)\n'))
        else:
            self.stdout.write(self.style.SUCCESS('✓ Batch completed successfully!\n'))
