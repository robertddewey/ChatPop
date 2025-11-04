"""
Interactive browser for exploring suggestions and their matched photos.

Usage:
    python manage.py browse_suggestions

Features:
- List all suggestions sorted by usage count (popularity)
- Filter by proper noun status, minimum usage, search term
- Select a suggestion to see all photos that matched it
- View photo details including other suggestions from the same photo
"""

from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.conf import settings
from photo_analysis.models import Suggestion, PhotoAnalysis
import json
import os
from datetime import datetime


class Command(BaseCommand):
    help = 'Interactive browser for suggestions and their matched photos'

    def add_arguments(self, parser):
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all suggestions and exit (non-interactive)',
        )
        parser.add_argument(
            '--proper-nouns',
            action='store_true',
            help='Show only proper nouns',
        )
        parser.add_argument(
            '--generic',
            action='store_true',
            help='Show only generic suggestions (non-proper nouns)',
        )
        parser.add_argument(
            '--min-usage',
            type=int,
            default=1,
            help='Minimum usage count (default: 1)',
        )
        parser.add_argument(
            '--search',
            type=str,
            help='Search suggestions by name or key',
        )
        parser.add_argument(
            '--suggestion',
            type=str,
            help='View details for a specific suggestion by key',
        )

    def handle(self, *args, **options):
        # Build query filters
        filters = Q()

        if options['proper_nouns']:
            filters &= Q(is_proper_noun=True)
        elif options['generic']:
            filters &= Q(is_proper_noun=False)

        if options['min_usage'] > 1:
            filters &= Q(usage_count__gte=options['min_usage'])

        if options['search']:
            search_term = options['search']
            filters &= Q(name__icontains=search_term) | Q(key__icontains=search_term)

        # Get suggestions
        suggestions = Suggestion.objects.filter(filters).order_by('-usage_count', 'name')

        # Count total suggestions and photos
        total_suggestions = suggestions.count()
        total_photos = PhotoAnalysis.objects.count()

        # Non-interactive modes
        if options['list']:
            self._list_suggestions(suggestions, total_suggestions, total_photos)
            return

        if options['suggestion']:
            suggestion_key = options['suggestion']
            try:
                suggestion = Suggestion.objects.get(key=suggestion_key)
                self._show_suggestion_details(suggestion)
            except Suggestion.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'\n✗ Suggestion "{suggestion_key}" not found\n'))
            return

        # Interactive mode
        self._interactive_mode(suggestions, total_suggestions, total_photos)

    def _list_suggestions(self, suggestions, total_suggestions, total_photos):
        """Non-interactive list view."""
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('SUGGESTIONS BROWSER'))
        self.stdout.write('='*80)
        self.stdout.write(f'Total: {total_suggestions} suggestions | {total_photos} photos analyzed\n')

        if not suggestions:
            self.stdout.write(self.style.WARNING('No suggestions found matching your criteria.\n'))
            return

        # Table header
        self.stdout.write(f"{'#':<5} {'Name':<30} {'Key':<25} {'Type':<12} {'Usage':<8}")
        self.stdout.write('-'*80)

        for idx, suggestion in enumerate(suggestions, 1):
            type_label = 'PROPER NOUN' if suggestion.is_proper_noun else 'generic'
            type_style = self.style.WARNING if suggestion.is_proper_noun else self.style.SUCCESS

            self.stdout.write(
                f"{idx:<5} "
                f"{suggestion.name:<30} "
                f"{suggestion.key:<25} "
                f"{type_style(type_label):<20} "
                f"{suggestion.usage_count}x"
            )

        self.stdout.write('')

    def _interactive_mode(self, suggestions, total_suggestions, total_photos):
        """Interactive browser."""
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('INTERACTIVE SUGGESTIONS BROWSER'))
        self.stdout.write('='*80)
        self.stdout.write(f'Total: {total_suggestions} suggestions | {total_photos} photos analyzed')
        self.stdout.write('\nCommands:')
        self.stdout.write('  - Enter number to view suggestion details')
        self.stdout.write('  - "filter <term>" to search by name/key')
        self.stdout.write('  - "proper" to show only proper nouns')
        self.stdout.write('  - "generic" to show only generic suggestions')
        self.stdout.write('  - "reset" to clear filters')
        self.stdout.write('  - "quit" or "q" to exit')
        self.stdout.write('='*80 + '\n')

        current_suggestions = list(suggestions)
        current_filters = []

        while True:
            # Show current list
            if not current_suggestions:
                self.stdout.write(self.style.WARNING('No suggestions found matching your filters.\n'))
            else:
                self._show_suggestion_list(current_suggestions, current_filters)

            # Get user input
            self.stdout.write('')
            try:
                user_input = input(self.style.HTTP_INFO('> ')).strip()
            except (KeyboardInterrupt, EOFError):
                self.stdout.write('\n\nGoodbye!\n')
                return

            if not user_input:
                continue

            # Parse command
            if user_input.lower() in ['quit', 'q', 'exit']:
                self.stdout.write('\nGoodbye!\n')
                return

            elif user_input.lower() == 'reset':
                current_suggestions = list(suggestions)
                current_filters = []
                self.stdout.write(self.style.SUCCESS('\n✓ Filters cleared\n'))

            elif user_input.lower() == 'proper':
                current_suggestions = [s for s in current_suggestions if s.is_proper_noun]
                current_filters.append('proper nouns only')
                self.stdout.write(self.style.SUCCESS(f'\n✓ Showing {len(current_suggestions)} proper nouns\n'))

            elif user_input.lower() == 'generic':
                current_suggestions = [s for s in current_suggestions if not s.is_proper_noun]
                current_filters.append('generic only')
                self.stdout.write(self.style.SUCCESS(f'\n✓ Showing {len(current_suggestions)} generic suggestions\n'))

            elif user_input.lower().startswith('filter '):
                search_term = user_input[7:].strip()
                current_suggestions = [
                    s for s in current_suggestions
                    if search_term.lower() in s.name.lower() or search_term.lower() in s.key.lower()
                ]
                current_filters.append(f'search: "{search_term}"')
                self.stdout.write(self.style.SUCCESS(f'\n✓ Found {len(current_suggestions)} matches\n'))

            elif user_input.isdigit():
                idx = int(user_input)
                if 1 <= idx <= len(current_suggestions):
                    self._show_suggestion_details(current_suggestions[idx - 1])
                else:
                    self.stdout.write(self.style.ERROR(f'\n✗ Invalid number. Enter 1-{len(current_suggestions)}\n'))

            else:
                self.stdout.write(self.style.ERROR('\n✗ Unknown command. Try "help" or enter a number.\n'))

    def _show_suggestion_list(self, suggestions, filters):
        """Display paginated suggestion list."""
        if filters:
            self.stdout.write(self.style.HTTP_INFO(f'\nFilters: {", ".join(filters)}'))

        self.stdout.write(f"\n{'#':<5} {'Name':<30} {'Key':<25} {'Type':<12} {'Usage':<8}")
        self.stdout.write('-'*80)

        for idx, suggestion in enumerate(suggestions[:50], 1):  # Show max 50
            type_label = 'PROPER NOUN' if suggestion.is_proper_noun else 'generic'
            type_style = self.style.WARNING if suggestion.is_proper_noun else self.style.SUCCESS

            self.stdout.write(
                f"{idx:<5} "
                f"{suggestion.name:<30} "
                f"{suggestion.key:<25} "
                f"{type_style(type_label):<20} "
                f"{suggestion.usage_count}x"
            )

        if len(suggestions) > 50:
            self.stdout.write(self.style.HTTP_INFO(f'\n... and {len(suggestions) - 50} more'))

    def _show_suggestion_details(self, suggestion):
        """Show detailed view of a suggestion and its matched photos."""
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS(f'SUGGESTION DETAILS: {suggestion.name}'))
        self.stdout.write('='*80)

        # Basic info
        self.stdout.write(f'\nName:         {suggestion.name}')
        self.stdout.write(f'Key:          {suggestion.key}')
        self.stdout.write(f'Description:  {suggestion.description}')
        self.stdout.write(f'Type:         {"PROPER NOUN" if suggestion.is_proper_noun else "generic"}')
        self.stdout.write(f'Usage Count:  {suggestion.usage_count}x')
        self.stdout.write(f'Last Used:    {suggestion.last_used_at.strftime("%Y-%m-%d %H:%M:%S") if suggestion.last_used_at else "Never"}')
        self.stdout.write(f'Created:      {suggestion.created_at.strftime("%Y-%m-%d %H:%M:%S")}')
        self.stdout.write(f'ID:           {suggestion.id}')

        # Find all photos that contain this suggestion
        photos_with_suggestion = PhotoAnalysis.objects.filter(
            suggestions__icontains=suggestion.key
        ).order_by('-created_at')

        self.stdout.write(f'\n{"-"*80}')
        self.stdout.write(self.style.HTTP_INFO(f'MATCHED PHOTOS: {photos_with_suggestion.count()}'))
        self.stdout.write('-'*80)

        if not photos_with_suggestion:
            self.stdout.write(self.style.WARNING('\nNo photos found with this suggestion.\n'))
            return

        # Show each photo
        for idx, photo in enumerate(photos_with_suggestion, 1):
            # Construct full file path
            media_root = settings.MEDIA_ROOT
            full_path = os.path.join(media_root, photo.image_path)

            self.stdout.write(f'\n{idx}. Photo ID: {photo.id}')
            self.stdout.write(f'   Created: {photo.created_at.strftime("%Y-%m-%d %H:%M:%S")}')
            self.stdout.write(f'   User: {photo.user.username if photo.user else "Anonymous"}')
            self.stdout.write(f'   Fingerprint: {photo.fingerprint or "N/A"}')
            self.stdout.write(f'   File: {full_path}')
            self.stdout.write(f'   File Hash: {photo.file_hash}')
            self.stdout.write(f'   Times Used: {photo.times_used}x')

            # Parse suggestions JSON to find this suggestion
            try:
                suggestions_data = photo.suggestions
                if isinstance(suggestions_data, str):
                    suggestions_data = json.loads(suggestions_data)

                # Extract suggestions list from dict structure
                if isinstance(suggestions_data, dict):
                    suggestions_list = suggestions_data.get('suggestions', [])
                elif isinstance(suggestions_data, list):
                    suggestions_list = suggestions_data
                else:
                    raise TypeError(f"Unexpected type: {type(suggestions_data)}")

                # Find this suggestion in the list
                matching_suggestions = [
                    s for s in suggestions_list
                    if isinstance(s, dict) and s.get('key') == suggestion.key
                ]

                if matching_suggestions:
                    match_info = matching_suggestions[0]
                    self.stdout.write(f'   Source: {match_info.get("source", "unknown")}')
                    self.stdout.write(f'   Match Usage: {match_info.get("usage_count", "?")}x at time of analysis')

                # Show all other suggestions from this photo
                other_suggestions = [
                    s for s in suggestions_list
                    if isinstance(s, dict) and s.get('key') != suggestion.key
                ]
                if other_suggestions:
                    self.stdout.write(f'   Other suggestions from this photo:')
                    for other in other_suggestions[:5]:
                        self.stdout.write(f'     - {other.get("name")} ({other.get("key")})')

            except (json.JSONDecodeError, TypeError) as e:
                self.stdout.write(self.style.WARNING(f'   Warning: Could not parse suggestions JSON: {e}'))

        self.stdout.write(f'\n{"="*80}\n')
