"""
Django management command to test photo analysis upload end-to-end.

Usage:
    ./venv/bin/python manage.py test_photo_upload <image_filename>
    ./venv/bin/python manage.py test_photo_upload test_coffee_mug.jpeg
    ./venv/bin/python manage.py test_photo_upload --list
"""
import os
import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client


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
                    self.stdout.write(f'Model: {analysis.get("ai_vision_model")}')
                    self.stdout.write(f'Image pHash: {analysis.get("image_phash")}')
                    self.stdout.write(f'File MD5: {analysis.get("file_hash")}')
                    self.stdout.write(f'File Size: {analysis.get("file_size")} bytes')
                    self.stdout.write(f'Storage: {analysis.get("storage_type")}')
                    self.stdout.write(f'Times Used: {analysis.get("times_used")}')
                    
                    # Token usage
                    if analysis.get('ai_vision_response_metadata'):
                        metadata = analysis.get('ai_vision_response_metadata', {})
                        if 'token_usage' in metadata:
                            usage = metadata['token_usage']
                            self.stdout.write(f'\nToken Usage:')
                            self.stdout.write(f'  Prompt: {usage.get("prompt_tokens")}')
                            self.stdout.write(f'  Completion: {usage.get("completion_tokens")}')
                            self.stdout.write(f'  Total: {usage.get("total_tokens")}')
                    
                    # Suggestions
                    suggestions = analysis.get('suggestions', [])
                    count = len(suggestions)
                    self.stdout.write(f'\nSuggestions Count: {count}')
                    if suggestions:
                        self.stdout.write(self.style.SUCCESS('\nChat Name Suggestions:'))
                        for i, suggestion in enumerate(suggestions, 1):
                            self.stdout.write(
                                f'  {i}. {self.style.SUCCESS(suggestion.get("name"))} '
                                f'(key: {suggestion.get("key")})'
                            )
                            if suggestion.get('description'):
                                self.stdout.write(f'     {suggestion.get("description")}')
                
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
