"""
Django management command to analyze suggestion embedding distances.

This diagnostic tool helps determine if the similarity threshold is too strict
by showing actual distances between semantically similar suggestions.

Usage:
    ./venv/bin/python manage.py inspect_suggestion_distances
    ./venv/bin/python manage.py inspect_suggestion_distances --top 20
    ./venv/bin/python manage.py inspect_suggestion_distances --query "Cheers"
"""

from django.core.management.base import BaseCommand
from pgvector.django import CosineDistance

from media_analysis.models import Suggestion
from media_analysis.config import SUGGESTION_MATCHING_SIMILARITY_THRESHOLD


class Command(BaseCommand):
    help = 'Analyze suggestion embedding distances to diagnose clustering issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--top',
            type=int,
            default=15,
            help='Number of top suggestions to analyze (default: 15)'
        )
        parser.add_argument(
            '--query',
            type=str,
            help='Specific suggestion name to query (e.g., "Cheers")'
        )
        parser.add_argument(
            '--neighbors',
            type=int,
            default=10,
            help='Number of nearest neighbors to show per suggestion (default: 10)'
        )

    def handle(self, *args, **options):
        top_n = options['top']
        query_name = options.get('query')
        neighbors = options['neighbors']
        threshold = SUGGESTION_MATCHING_SIMILARITY_THRESHOLD

        self.stdout.write(self.style.WARNING(f'\n{"="*80}'))
        self.stdout.write(self.style.WARNING('SUGGESTION DISTANCE ANALYSIS'))
        self.stdout.write(self.style.WARNING(f'{"="*80}\n'))
        self.stdout.write(f'Current matching threshold: {threshold} (cosine distance)')
        self.stdout.write(f'Neighbors per suggestion: {neighbors}')
        self.stdout.write('')

        # Query mode: analyze a specific suggestion
        if query_name:
            self._analyze_specific_suggestion(query_name, neighbors, threshold)
            return

        # Overview mode: analyze top N suggestions by usage
        self._analyze_top_suggestions(top_n, neighbors, threshold)

    def _analyze_specific_suggestion(self, name: str, neighbors: int, threshold: float):
        """Analyze distances for a specific suggestion."""
        try:
            suggestion = Suggestion.objects.get(name__iexact=name, is_proper_noun=False)
        except Suggestion.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'\n✗ Suggestion "{name}" not found (or is a proper noun)'))
            return
        except Suggestion.MultipleObjectsReturned:
            suggestions = Suggestion.objects.filter(name__iexact=name)
            self.stdout.write(self.style.WARNING(f'\n⚠ Multiple suggestions found for "{name}":'))
            for s in suggestions:
                self.stdout.write(f'  - {s.name} (key={s.key}, proper_noun={s.is_proper_noun}, usage={s.usage_count}x)')
            return

        if suggestion.embedding is None:
            self.stdout.write(self.style.ERROR(f'\n✗ Suggestion "{name}" has no embedding'))
            return

        self.stdout.write(self.style.SUCCESS(f'\n{"="*80}'))
        self.stdout.write(self.style.SUCCESS(f'QUERY: {suggestion.name}'))
        self.stdout.write(self.style.SUCCESS(f'{"="*80}\n'))
        self.stdout.write(f'Key: {suggestion.key}')
        self.stdout.write(f'Usage: {suggestion.usage_count}x')
        self.stdout.write(f'Proper Noun: {suggestion.is_proper_noun}')
        self.stdout.write(f'Description: {suggestion.description or "(none)"}')
        self.stdout.write('')

        # Find nearest neighbors
        similar = Suggestion.objects.filter(
            is_proper_noun=False,
            embedding__isnull=False
        ).exclude(
            id=suggestion.id
        ).annotate(
            distance=CosineDistance('embedding', suggestion.embedding)
        ).order_by('distance')[:neighbors]

        if not similar.exists():
            self.stdout.write(self.style.WARNING('No similar suggestions found'))
            return

        self.stdout.write(self.style.SUCCESS(f'Top {neighbors} Nearest Neighbors:'))
        self.stdout.write('')

        for i, neighbor in enumerate(similar, 1):
            similarity_pct = (1 - neighbor.distance) * 100

            # Determine if this would match with current threshold
            if neighbor.distance < threshold:
                match_status = self.style.SUCCESS('✓ MATCHES')
                distance_style = self.style.SUCCESS
            else:
                match_status = self.style.WARNING('○ NO MATCH')
                distance_style = self.style.WARNING

            self.stdout.write(
                f'  {i}. {distance_style(neighbor.name)} - '
                f'{distance_style(f"distance: {neighbor.distance:.4f}")} '
                f'({similarity_pct:.1f}% similar, usage: {neighbor.usage_count}x) {match_status}'
            )
            if neighbor.description and neighbor.description != suggestion.description:
                self.stdout.write(f'     Description: {neighbor.description[:100]}...')

        self.stdout.write('')
        self._print_threshold_recommendations(suggestion, similar, threshold)

    def _analyze_top_suggestions(self, top_n: int, neighbors: int, threshold: float):
        """Analyze top N suggestions by usage."""
        # Get top suggestions (excluding proper nouns)
        top_suggestions = Suggestion.objects.filter(
            is_proper_noun=False,
            embedding__isnull=False
        ).order_by('-usage_count')[:top_n]

        if not top_suggestions.exists():
            self.stdout.write(self.style.ERROR('No suggestions found with embeddings'))
            return

        self.stdout.write(self.style.SUCCESS(f'Top {top_n} Suggestions by Usage:'))
        self.stdout.write('')

        for idx, suggestion in enumerate(top_suggestions, 1):
            self.stdout.write(self.style.WARNING(f'\n{"="*80}'))
            self.stdout.write(self.style.WARNING(f'#{idx}. {suggestion.name} (usage: {suggestion.usage_count}x, key: {suggestion.key})'))
            self.stdout.write(self.style.WARNING(f'{"="*80}'))

            # Find nearest neighbors
            similar = Suggestion.objects.filter(
                is_proper_noun=False,
                embedding__isnull=False
            ).exclude(
                id=suggestion.id
            ).annotate(
                distance=CosineDistance('embedding', suggestion.embedding)
            ).order_by('distance')[:neighbors]

            if not similar.exists():
                self.stdout.write('  No similar suggestions found')
                continue

            for i, neighbor in enumerate(similar, 1):
                similarity_pct = (1 - neighbor.distance) * 100

                # Determine if this would match with current threshold
                if neighbor.distance < threshold:
                    match_symbol = '✓'
                    distance_style = self.style.SUCCESS
                else:
                    match_symbol = '○'
                    distance_style = self.style.WARNING

                self.stdout.write(
                    f'  {i}. {match_symbol} {distance_style(neighbor.name):30s} '
                    f'distance: {distance_style(f"{neighbor.distance:.4f}")} '
                    f'({similarity_pct:5.1f}% similar, usage: {neighbor.usage_count:2d}x)'
                )

        # Summary statistics
        self._print_summary_statistics(top_suggestions, threshold)

    def _print_threshold_recommendations(self, suggestion, similar, threshold):
        """Print recommendations for threshold adjustment."""
        # Count how many neighbors are just outside threshold
        near_misses = [s for s in similar if threshold <= s.distance < threshold + 0.10]

        if near_misses:
            self.stdout.write(self.style.WARNING(f'\n⚠ {len(near_misses)} potential matches just outside threshold:'))
            for s in near_misses[:5]:
                self.stdout.write(f'  - {s.name} (distance: {s.distance:.4f}, {(1-s.distance)*100:.1f}% similar)')

            max_distance = max(s.distance for s in near_misses)
            recommended_threshold = round(max_distance + 0.01, 2)
            self.stdout.write('')
            self.stdout.write(
                f'💡 Recommended threshold: {recommended_threshold} '
                f'(would match {len(near_misses)} more suggestion{"s" if len(near_misses) != 1 else ""})'
            )

    def _print_summary_statistics(self, suggestions, threshold):
        """Print summary statistics about suggestion clustering."""
        self.stdout.write(self.style.WARNING(f'\n{"="*80}'))
        self.stdout.write(self.style.WARNING('SUMMARY STATISTICS'))
        self.stdout.write(self.style.WARNING(f'{"="*80}\n'))

        # Count suggestions with very close neighbors (< threshold)
        close_pairs = []
        for suggestion in suggestions:
            similar = Suggestion.objects.filter(
                is_proper_noun=False,
                embedding__isnull=False
            ).exclude(
                id=suggestion.id
            ).annotate(
                distance=CosineDistance('embedding', suggestion.embedding)
            ).filter(
                distance__lt=threshold
            )[:3]

            if similar.exists():
                close_pairs.append((suggestion.name, [s.name for s in similar]))

        if close_pairs:
            self.stdout.write(self.style.SUCCESS(f'✓ {len(close_pairs)} suggestions have matches within threshold:'))
            for name, matches in close_pairs[:5]:
                self.stdout.write(f'  - {name} ↔ {", ".join(matches)}')
        else:
            self.stdout.write(self.style.WARNING('⚠ No suggestions have close matches within current threshold'))

        # Count near-miss pairs (just outside threshold)
        near_miss_pairs = []
        for suggestion in suggestions:
            similar = Suggestion.objects.filter(
                is_proper_noun=False,
                embedding__isnull=False
            ).exclude(
                id=suggestion.id
            ).annotate(
                distance=CosineDistance('embedding', suggestion.embedding)
            ).filter(
                distance__gte=threshold,
                distance__lt=threshold + 0.10
            )[:3]

            if similar.exists():
                for s in similar:
                    near_miss_pairs.append((suggestion.name, s.name, s.distance))

        if near_miss_pairs:
            self.stdout.write(f'\n⚠ {len(near_miss_pairs)} potential matches just outside threshold:')
            for name1, name2, distance in sorted(near_miss_pairs, key=lambda x: x[2])[:10]:
                self.stdout.write(
                    f'  - {name1} ↔ {name2} '
                    f'(distance: {distance:.4f}, {(1-distance)*100:.1f}% similar)'
                )

        self.stdout.write('')
