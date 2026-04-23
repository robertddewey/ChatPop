"""
check_apis — functional health check for external APIs.

Runs live probes against the providers ChatPop depends on and reports
whether each endpoint is reachable and whether the configured API key
works. See `docs/MANAGEMENT_COMMANDS.md` for details.
"""

import json
from django.core.management.base import BaseCommand, CommandError

from media_analysis.utils.health import run_probes, CATEGORIES, PROVIDERS
from media_analysis.utils.health.base import resolve_providers


STATUS_SYMBOLS = {
    'ok': '✓',
    'degraded': '~',
    'down': '✗',
    'not_configured': '·',
    'error': '!',
}


class Command(BaseCommand):
    help = (
        'Run health probes against external APIs (location, audio, image).\n\n'
        'Each probe makes a real request that exercises the configured API key.\n'
        'Status values: ok, degraded, down, not_configured.\n\n'
        'Selectors for --provider:\n'
        '  all              run every probe (default)\n'
        '  location         tomtom + google_places\n'
        '  audio            acrcloud\n'
        '  image            openai\n'
        '  tomtom           only the TomTom reverse-geocode probe\n'
        '  google_places    only the Google Places geocode probe\n'
        '  acrcloud         only the ACRCloud identify probe\n'
        '  openai           only the OpenAI vision probe\n\n'
        'Examples:\n'
        '  ./manage.py check_apis\n'
        '  ./manage.py check_apis --provider location\n'
        '  ./manage.py check_apis --provider tomtom\n'
        '  ./manage.py check_apis --json'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--provider',
            default='all',
            help=(
                "Which probe(s) to run. One of: 'all', a category "
                f"({', '.join(CATEGORIES)}), or a specific provider "
                f"({', '.join(PROVIDERS)}). Default: all."
            ),
        )
        parser.add_argument(
            '--json',
            action='store_true',
            help='Emit results as JSON (one array) instead of a table.',
        )

    def handle(self, *args, **options):
        selector = options['provider']
        as_json = options['json']

        try:
            resolve_providers(selector)  # validate early for a clean error
        except ValueError as e:
            raise CommandError(str(e))

        results = run_probes(selector)

        if as_json:
            payload = [r.to_dict() for r in results]
            self.stdout.write(json.dumps(payload, indent=2))
            return

        self._render_table(results)

        # Exit non-zero if anything is down (useful in CI / scripts).
        if any(r.status == 'down' for r in results):
            raise CommandError('One or more probes reported status=down.')

    def _render_table(self, results):
        header = f"{'':2s}  {'SERVICE':9s}  {'PROVIDER':15s}  {'STATUS':16s}  {'LATENCY':>9s}  MESSAGE"
        self.stdout.write(header)
        self.stdout.write('-' * 120)
        for r in results:
            symbol = STATUS_SYMBOLS.get(r.status, '?')
            latency = f'{r.latency_ms} ms' if r.latency_ms is not None else '-'
            line = (
                f'{symbol:2s}  {r.service:9s}  {r.provider:15s}  '
                f'{r.status:16s}  {latency:>9s}  {r.message}'
            )
            style = self._style_for(r.status)
            self.stdout.write(style(line) if style else line)

    def _style_for(self, status):
        return {
            'ok': self.style.SUCCESS,
            'degraded': self.style.WARNING,
            'down': self.style.ERROR,
            'not_configured': self.style.NOTICE,
            'error': self.style.ERROR,
        }.get(status)
