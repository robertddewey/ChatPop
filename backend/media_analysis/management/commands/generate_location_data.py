"""
Generate fake LocationAnalysis data for stress testing the lightning strike map.

Usage examples:
    # Generate ~3 points/second for 60 seconds (with variance)
    ./venv/bin/python manage.py generate_location_data --rate 3 --duration 60

    # Generate ~10 points/second for 300 seconds
    ./venv/bin/python manage.py generate_location_data --rate 10 --duration 300

    # Higher variance (0-20 instead of 0-10 when rate=5)
    ./venv/bin/python manage.py generate_location_data --rate 5 --duration 120 --variance 15

    # Delete all test data
    ./venv/bin/python manage.py generate_location_data --delete

Test data is marked with fingerprint prefix "TEST_DATA_" for easy cleanup.
"""

import random
import signal
import sys
import time
import uuid
from datetime import datetime
from typing import List, Tuple

from django.core.management.base import BaseCommand
from django.utils import timezone

from media_analysis.models import LocationAnalysis
from media_analysis.utils.location import encode_location

# Continental US bounding box
US_BOUNDS = {
    'min_lat': 24.396308,   # Southern tip of Florida
    'max_lat': 49.384358,   # Northern border with Canada
    'min_lng': -125.000000,  # West coast
    'max_lng': -66.934570,   # East coast
}

# Major US cities with approximate coordinates (for more realistic distribution)
# Weighted more heavily than random points
US_CITIES = [
    ('New York', 40.7128, -74.0060),
    ('Los Angeles', 34.0522, -118.2437),
    ('Chicago', 41.8781, -87.6298),
    ('Houston', 29.7604, -95.3698),
    ('Phoenix', 33.4484, -112.0740),
    ('Philadelphia', 39.9526, -75.1652),
    ('San Antonio', 29.4241, -98.4936),
    ('San Diego', 32.7157, -117.1611),
    ('Dallas', 32.7767, -96.7970),
    ('San Jose', 37.3382, -121.8863),
    ('Austin', 30.2672, -97.7431),
    ('Jacksonville', 30.3322, -81.6557),
    ('Fort Worth', 32.7555, -97.3308),
    ('Columbus', 39.9612, -82.9988),
    ('Charlotte', 35.2271, -80.8431),
    ('San Francisco', 37.7749, -122.4194),
    ('Indianapolis', 39.7684, -86.1581),
    ('Seattle', 47.6062, -122.3321),
    ('Denver', 39.7392, -104.9903),
    ('Washington DC', 38.9072, -77.0369),
    ('Boston', 42.3601, -71.0589),
    ('Nashville', 36.1627, -86.7816),
    ('Detroit', 42.3314, -83.0458),
    ('Portland', 45.5152, -122.6784),
    ('Las Vegas', 36.1699, -115.1398),
    ('Miami', 25.7617, -80.1918),
    ('Atlanta', 33.7490, -84.3880),
    ('Minneapolis', 44.9778, -93.2650),
    ('New Orleans', 29.9511, -90.0715),
    ('Tampa', 27.9506, -82.4572),
]

# Fingerprint prefix for test data identification
TEST_DATA_PREFIX = "TEST_DATA_"


class Command(BaseCommand):
    help = 'Generate fake LocationAnalysis data for stress testing'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.should_stop = False
        self.points_created = 0
        self.start_time = None

    def add_arguments(self, parser):
        parser.add_argument(
            '--rate',
            type=float,
            default=3.0,
            help='Average points per second (default: 3)'
        )
        parser.add_argument(
            '--duration',
            type=int,
            default=60,
            help='Duration in seconds (default: 60)'
        )
        parser.add_argument(
            '--variance',
            type=float,
            default=None,
            help='Max deviation from rate (default: 2x rate, so rate=3 means 0-6 range)'
        )
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Delete all test data instead of generating'
        )
        parser.add_argument(
            '--city-bias',
            type=float,
            default=0.7,
            help='Probability of generating point near a city vs random (default: 0.7)'
        )

    def handle(self, *args, **options):
        if options['delete']:
            self._delete_test_data()
            return

        # Set up Ctrl+C handler
        signal.signal(signal.SIGINT, self._signal_handler)

        rate = options['rate']
        duration = options['duration']
        variance = options['variance']
        city_bias = options['city_bias']

        # Default variance is rate itself (so rate=3 gives 0-6 range)
        if variance is None:
            variance = rate

        self.stdout.write(self.style.NOTICE(
            f"\nStarting location data generation:"
            f"\n  Rate: ~{rate} points/second (variance: ±{variance})"
            f"\n  Duration: {duration} seconds"
            f"\n  Expected total: ~{int(rate * duration)} points"
            f"\n  City bias: {city_bias * 100}%"
            f"\n\nPress Ctrl+C to stop gracefully...\n"
        ))

        self.start_time = time.time()
        self._generate_points(rate, duration, variance, city_bias)

        # Final summary
        elapsed = time.time() - self.start_time
        actual_rate = self.points_created / elapsed if elapsed > 0 else 0

        self.stdout.write(self.style.SUCCESS(
            f"\n{'=' * 50}"
            f"\nGeneration complete!"
            f"\n  Points created: {self.points_created}"
            f"\n  Time elapsed: {elapsed:.1f}s"
            f"\n  Actual rate: {actual_rate:.2f} points/second"
            f"\n{'=' * 50}\n"
        ))

    def _signal_handler(self, signum, frame):
        """Handle Ctrl+C gracefully."""
        self.stdout.write(self.style.WARNING(
            f"\n\nStopping... (created {self.points_created} points so far)"
        ))
        self.should_stop = True

    def _delete_test_data(self):
        """Delete all test data marked with TEST_DATA_ fingerprint prefix."""
        count = LocationAnalysis.objects.filter(
            fingerprint__startswith=TEST_DATA_PREFIX
        ).count()

        if count == 0:
            self.stdout.write(self.style.WARNING("No test data found to delete."))
            return

        self.stdout.write(self.style.NOTICE(
            f"Found {count} test data records. Deleting..."
        ))

        deleted, _ = LocationAnalysis.objects.filter(
            fingerprint__startswith=TEST_DATA_PREFIX
        ).delete()

        self.stdout.write(self.style.SUCCESS(
            f"Deleted {deleted} test data records."
        ))

    def _generate_points(self, rate: float, duration: int, variance: float, city_bias: float):
        """Generate points in real-time with randomized rate."""
        end_time = time.time() + duration

        while time.time() < end_time and not self.should_stop:
            second_start = time.time()

            # Calculate points for this second with variance
            # Using a bounded random distribution around the rate
            min_points = max(0, int(rate - variance))
            max_points = int(rate + variance)
            points_this_second = random.randint(min_points, max_points)

            # Generate the points
            if points_this_second > 0:
                points = self._create_batch(points_this_second, city_bias)
                self.points_created += len(points)

                # Progress output
                elapsed = time.time() - self.start_time
                self.stdout.write(
                    f"[{elapsed:6.1f}s] Created {points_this_second} points "
                    f"(total: {self.points_created})"
                )

            # Wait for remainder of the second
            elapsed_in_second = time.time() - second_start
            if elapsed_in_second < 1.0:
                time.sleep(1.0 - elapsed_in_second)

    def _create_batch(self, count: int, city_bias: float) -> List[LocationAnalysis]:
        """Create a batch of LocationAnalysis records."""
        records = []

        for _ in range(count):
            lat, lng, city_name = self._generate_location(city_bias)
            geohash = encode_location(lat, lng)

            record = LocationAnalysis(
                latitude=lat,
                longitude=lng,
                geohash=geohash,
                city_name=city_name,
                neighborhood_name='',
                fingerprint=f"{TEST_DATA_PREFIX}{uuid.uuid4().hex[:16]}",
                ip_address='127.0.0.1',
                cache_source='api',
                cache_hit=False,
            )
            records.append(record)

        # Bulk create for efficiency
        created = LocationAnalysis.objects.bulk_create(records)
        return created

    def _generate_location(self, city_bias: float) -> Tuple[float, float, str]:
        """
        Generate a random location within continental US.

        Returns (latitude, longitude, city_name)
        """
        if random.random() < city_bias:
            # Generate near a city with some jitter
            city_name, base_lat, base_lng = random.choice(US_CITIES)

            # Add random offset (roughly within ~50km of city center)
            lat = base_lat + random.uniform(-0.3, 0.3)
            lng = base_lng + random.uniform(-0.4, 0.4)

            # Clamp to US bounds
            lat = max(US_BOUNDS['min_lat'], min(US_BOUNDS['max_lat'], lat))
            lng = max(US_BOUNDS['min_lng'], min(US_BOUNDS['max_lng'], lng))

            return lat, lng, city_name
        else:
            # Generate completely random point in US
            lat = random.uniform(US_BOUNDS['min_lat'], US_BOUNDS['max_lat'])
            lng = random.uniform(US_BOUNDS['min_lng'], US_BOUNDS['max_lng'])

            return lat, lng, ''
