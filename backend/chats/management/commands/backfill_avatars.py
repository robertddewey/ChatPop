"""
Django management command to backfill avatar URLs for existing users and participations.

Usage:
    python manage.py backfill_avatars          # Dry run (shows what would be done)
    python manage.py backfill_avatars --apply  # Actually apply changes
"""
from django.core.management.base import BaseCommand
from accounts.models import User
from chats.models import ChatParticipation


class Command(BaseCommand):
    help = """Backfill avatar URLs for existing data.

    1. Registered users with reserved_username but no avatar_url → generate avatar
    2. ChatParticipation records:
       - Registered + reserved_username → proxy URL
       - Registered + different username → generate direct URL if missing
       - Anonymous → generate direct URL if missing
    """

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually apply changes (default is dry run)'
        )

    def handle(self, *args, **options):
        apply = options['apply']

        if not apply:
            self.stdout.write(self.style.WARNING(
                "\n⚠️  DRY RUN MODE - No changes will be made. Use --apply to apply changes.\n"
            ))

        from chatpop.utils.media import generate_and_store_avatar

        # Track stats
        stats = {
            'users_missing_avatar': 0,
            'users_avatar_generated': 0,
            'participation_proxy_set': 0,
            'participation_direct_generated': 0,
            'participation_already_ok': 0,
        }

        # ============================================================
        # STEP 1: Backfill User.avatar_url for registered users
        # ============================================================
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("STEP 1: Backfill User.avatar_url")
        self.stdout.write("=" * 60)

        users_missing = User.objects.filter(
            reserved_username__isnull=False,
            avatar_url__isnull=True
        ).exclude(reserved_username='')

        stats['users_missing_avatar'] = users_missing.count()
        self.stdout.write(f"\nFound {stats['users_missing_avatar']} users with reserved_username but no avatar_url")

        for user in users_missing:
            self.stdout.write(f"  - {user.reserved_username} (ID: {user.id})")

            if apply:
                avatar_url = generate_and_store_avatar(user.reserved_username)
                if avatar_url:
                    user.avatar_url = avatar_url
                    user.save(update_fields=['avatar_url'])
                    stats['users_avatar_generated'] += 1
                    self.stdout.write(self.style.SUCCESS(f"    ✅ Generated: {avatar_url}"))
                else:
                    self.stdout.write(self.style.ERROR(f"    ❌ Failed to generate avatar"))

        # ============================================================
        # STEP 2: Backfill ChatParticipation.avatar_url
        # ============================================================
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("STEP 2: Backfill ChatParticipation.avatar_url")
        self.stdout.write("=" * 60)

        # Get all participations
        participations = ChatParticipation.objects.select_related('user', 'chat_room__theme').all()
        total = participations.count()
        self.stdout.write(f"\nProcessing {total} ChatParticipation records...")

        for i, p in enumerate(participations, 1):
            # Get avatar style from theme
            avatar_style = None
            if p.chat_room.theme and p.chat_room.theme.avatar_style:
                avatar_style = p.chat_room.theme.avatar_style

            if p.user and p.user.reserved_username:
                # Registered user
                if p.username.lower() == p.user.reserved_username.lower():
                    # Using reserved_username → proxy URL
                    expected_url = f'/api/chats/media/avatars/user/{p.user.id}'

                    if p.avatar_url == expected_url:
                        stats['participation_already_ok'] += 1
                    else:
                        self.stdout.write(
                            f"  [{i}/{total}] {p.username} (registered, reserved) → proxy URL"
                        )
                        if apply:
                            p.avatar_url = expected_url
                            p.save(update_fields=['avatar_url'])
                            self.stdout.write(self.style.SUCCESS(f"    ✅ Set: {expected_url}"))
                        stats['participation_proxy_set'] += 1
                else:
                    # Using different username → direct URL
                    if p.avatar_url:
                        stats['participation_already_ok'] += 1
                    else:
                        self.stdout.write(
                            f"  [{i}/{total}] {p.username} (registered, different name) → generate direct URL"
                        )
                        if apply:
                            avatar_url = generate_and_store_avatar(p.username, style=avatar_style)
                            if avatar_url:
                                p.avatar_url = avatar_url
                                p.save(update_fields=['avatar_url'])
                                self.stdout.write(self.style.SUCCESS(f"    ✅ Generated: {avatar_url}"))
                            else:
                                self.stdout.write(self.style.ERROR(f"    ❌ Failed to generate"))
                        stats['participation_direct_generated'] += 1
            else:
                # Anonymous user → direct URL
                if p.avatar_url:
                    stats['participation_already_ok'] += 1
                else:
                    self.stdout.write(
                        f"  [{i}/{total}] {p.username} (anonymous) → generate direct URL"
                    )
                    if apply:
                        avatar_url = generate_and_store_avatar(p.username, style=avatar_style)
                        if avatar_url:
                            p.avatar_url = avatar_url
                            p.save(update_fields=['avatar_url'])
                            self.stdout.write(self.style.SUCCESS(f"    ✅ Generated: {avatar_url}"))
                        else:
                            self.stdout.write(self.style.ERROR(f"    ❌ Failed to generate"))
                    stats['participation_direct_generated'] += 1

        # ============================================================
        # Summary
        # ============================================================
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("SUMMARY")
        self.stdout.write("=" * 60)
        self.stdout.write(f"\nUsers:")
        self.stdout.write(f"  - Missing avatar_url: {stats['users_missing_avatar']}")
        self.stdout.write(f"  - Avatars generated: {stats['users_avatar_generated'] if apply else '(dry run)'}")

        self.stdout.write(f"\nChatParticipation:")
        self.stdout.write(f"  - Already OK: {stats['participation_already_ok']}")
        self.stdout.write(f"  - Proxy URLs to set: {stats['participation_proxy_set']}")
        self.stdout.write(f"  - Direct URLs to generate: {stats['participation_direct_generated']}")

        if not apply:
            self.stdout.write(self.style.WARNING(
                "\n⚠️  DRY RUN - No changes made. Run with --apply to apply changes."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                "\n✅ Backfill complete!"
            ))
