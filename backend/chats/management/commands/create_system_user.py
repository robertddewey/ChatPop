"""
Management command to create the system user for AI-generated discover rooms.

Usage:
    python manage.py create_system_user
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Create system user for AI-generated discover rooms'

    def handle(self, *args, **options):
        email = 'discover@chatpop.app'
        username = 'ChatPopDiscover'

        # Check if system user already exists
        existing_user = User.objects.filter(email=email).first()
        if existing_user:
            self.stdout.write(
                self.style.WARNING(f'System user already exists: {existing_user.email} (ID: {existing_user.id})')
            )
            return

        # Create system user
        system_user = User.objects.create(
            email=email,
            reserved_username=username,
            is_active=False,  # Cannot login
            is_staff=False,
            is_superuser=False,
        )

        # Set unusable password (cannot be used to login)
        system_user.set_unusable_password()
        system_user.save()

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created system user: {system_user.email} (ID: {system_user.id})'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f'Reserved username: {system_user.reserved_username}'
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                'This user owns all AI-generated /discover rooms'
            )
        )
