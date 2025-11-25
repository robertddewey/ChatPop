"""
Test proper noun matching with strict threshold using existing PhotoAnalysis records.

This simulates how the new matching logic would handle the "Open Season" book vs movie.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from openai import OpenAI
from media_analysis.models import PhotoAnalysis, Suggestion
from media_analysis.config import PROPER_NOUN_MATCHING_THRESHOLD
import numpy as np


class Command(BaseCommand):
    help = 'Test proper noun matching with existing Open Season photos'

    def handle(self, *args, **options):
        # IDs from user
        photo1_id = '2ea275d8-7d5b-4f5c-b148-60fabf61fe10'
        photo2_id = 'a0aae9a5-c401-4f2a-8999-ae18f92dee58'

        self.stdout.write('\n' + '='*80)
        self.stdout.write('PROPER NOUN MATCHING TEST - Open Season Book vs Movie')
        self.stdout.write('='*80 + '\n')

        # Retrieve PhotoAnalysis records
        try:
            pa1 = PhotoAnalysis.objects.get(id=photo1_id)
            pa2 = PhotoAnalysis.objects.get(id=photo2_id)
        except PhotoAnalysis.DoesNotExist as e:
            self.stdout.write(self.style.ERROR(f'PhotoAnalysis record not found: {e}'))
            return

        # Extract Open Season suggestions
        suggestions1 = pa1.suggestions.get('suggestions', [])
        suggestions2 = pa2.suggestions.get('suggestions', [])

        open_season_1 = next((s for s in suggestions1 if 'open season' in s['name'].lower()), None)
        open_season_2 = next((s for s in suggestions2 if 'open season' in s['name'].lower()), None)

        if not open_season_1 or not open_season_2:
            self.stdout.write(self.style.ERROR('Could not find "Open Season" suggestions in both photos'))
            return

        self.stdout.write(f'Photo 1: {photo1_id}')
        self.stdout.write(f'  Name: {open_season_1["name"]}')
        self.stdout.write(f'  Key: {open_season_1["key"]}')
        self.stdout.write(f'  Proper noun: {open_season_1.get("is_proper_noun")}')
        self.stdout.write(f'  Description: {open_season_1.get("description", "")[:80]}...\n')

        self.stdout.write(f'Photo 2: {photo2_id}')
        self.stdout.write(f'  Name: {open_season_2["name"]}')
        self.stdout.write(f'  Key: {open_season_2["key"]}')
        self.stdout.write(f'  Proper noun: {open_season_2.get("is_proper_noun")}')
        self.stdout.write(f'  Description: {open_season_2.get("description", "")[:80]}...\n')

        # Generate embeddings for both descriptions
        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        text1 = f"{open_season_1['name']}\n{open_season_1.get('description', '')}"
        text2 = f"{open_season_2['name']}\n{open_season_2.get('description', '')}"

        self.stdout.write('Generating embeddings...')
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=[text1, text2]
        )

        embedding1 = np.array(response.data[0].embedding)
        embedding2 = np.array(response.data[1].embedding)

        # Calculate cosine distance
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        cosine_similarity = dot_product / (norm1 * norm2)
        cosine_distance = 1 - cosine_similarity

        self.stdout.write('\n' + '='*80)
        self.stdout.write('EMBEDDING SIMILARITY ANALYSIS')
        self.stdout.write('='*80)
        self.stdout.write(f'Cosine distance: {cosine_distance:.4f}')
        self.stdout.write(f'Cosine similarity: {cosine_similarity:.1%}')
        self.stdout.write(f'Threshold: {PROPER_NOUN_MATCHING_THRESHOLD} (85% similarity required)')

        if cosine_distance < PROPER_NOUN_MATCHING_THRESHOLD:
            self.stdout.write(self.style.SUCCESS(
                f'\n✓ WOULD MATCH - Distance {cosine_distance:.4f} < {PROPER_NOUN_MATCHING_THRESHOLD}'
            ))
            self.stdout.write('These would be considered the SAME suggestion.')
            self.stdout.write('Result: Same key, usage_count incremented')
        else:
            self.stdout.write(self.style.WARNING(
                f'\n✗ WOULD NOT MATCH - Distance {cosine_distance:.4f} >= {PROPER_NOUN_MATCHING_THRESHOLD}'
            ))
            self.stdout.write('These would be considered DIFFERENT suggestions.')
            self.stdout.write('Result: Second photo creates new suggestion with key "open-season-2"')

        # Check current Suggestion table state
        self.stdout.write('\n' + '='*80)
        self.stdout.write('CURRENT SUGGESTION TABLE STATE')
        self.stdout.write('='*80)

        open_season_suggestions = Suggestion.objects.filter(key__startswith='open-season').order_by('key')
        self.stdout.write(f'Found {open_season_suggestions.count()} suggestion(s) with key starting with "open-season":\n')

        for s in open_season_suggestions:
            self.stdout.write(f'  Key: {s.key}')
            self.stdout.write(f'  Name: {s.name}')
            self.stdout.write(f'  Usage count: {s.usage_count}')
            self.stdout.write(f'  Has embedding: {s.embedding is not None}')
            self.stdout.write(f'  Description: {s.description[:80]}...\n')

        self.stdout.write('='*80)
        self.stdout.write('RECOMMENDATION')
        self.stdout.write('='*80)
        self.stdout.write('To apply the new matching logic to existing data:')
        self.stdout.write('1. The new code will generate embeddings for proper nouns going forward')
        self.stdout.write('2. Existing proper noun suggestions without embeddings will work as-is')
        self.stdout.write('3. Optional: Run a migration to generate embeddings for existing proper nouns')
        self.stdout.write('4. Test by uploading a new photo of "Open Season" (movie or different book)')
        self.stdout.write('='*80 + '\n')
