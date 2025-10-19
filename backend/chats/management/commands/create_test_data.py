"""
Django management command to create test data for ChatPop

Usage:
    python manage.py create_test_data
"""
from django.core.management.base import BaseCommand
from accounts.models import User, UserSubscription
from chats.models import ChatRoom, Message


class Command(BaseCommand):
    help = """Create test data for ChatPop development.

    Creates:
    - Superuser (admin@chatpop.app)
    - 4 test users (jane, john, alice, bob @chatpop.app)
    - User subscriptions
    - 2 test chat rooms (public and private)
    - Initial test messages

    All users have password: demo123
    """

    def handle(self, *args, **options):
        """Create test data"""
        self.stdout.write("Creating test data...")

        # Create superuser
        self.stdout.write("\n1. Creating superuser...")
        if not User.objects.filter(email='admin@chatpop.app').exists():
            superuser = User.objects.create_superuser(
                email='admin@chatpop.app',
                password='demo123',
                display_name='Admin'
            )
            self.stdout.write(self.style.SUCCESS(f"✓ Superuser created: {superuser.email}"))
        else:
            superuser = User.objects.get(email='admin@chatpop.app')
            self.stdout.write(f"✓ Superuser already exists: {superuser.email}")

        # Create test users (registered users - any can be a host)
        self.stdout.write("\n2. Creating test registered users...")
        user1, created = User.objects.get_or_create(
            email='jane@chatpop.app',
            defaults={
                'display_name': 'Jane Doe',
            }
        )
        if created:
            user1.set_password('demo123')
            user1.save()
            self.stdout.write(self.style.SUCCESS(f"✓ User created: {user1.email}"))
        else:
            self.stdout.write(f"✓ User already exists: {user1.email}")

        user2, created = User.objects.get_or_create(
            email='john@chatpop.app',
            defaults={
                'display_name': 'John Smith',
            }
        )
        if created:
            user2.set_password('demo123')
            user2.save()
            self.stdout.write(self.style.SUCCESS(f"✓ User created: {user2.email}"))
        else:
            self.stdout.write(f"✓ User already exists: {user2.email}")

        user3, created = User.objects.get_or_create(
            email='alice@chatpop.app',
            defaults={
                'display_name': 'Alice Wonder',
            }
        )
        if created:
            user3.set_password('demo123')
            user3.save()
            self.stdout.write(self.style.SUCCESS(f"✓ User created: {user3.email}"))
        else:
            self.stdout.write(f"✓ User already exists: {user3.email}")

        user4, created = User.objects.get_or_create(
            email='bob@chatpop.app',
            defaults={
                'display_name': 'Bob Builder',
            }
        )
        if created:
            user4.set_password('demo123')
            user4.save()
            self.stdout.write(self.style.SUCCESS(f"✓ User created: {user4.email}"))
        else:
            self.stdout.write(f"✓ User already exists: {user4.email}")

        # Create subscriptions
        self.stdout.write("\n3. Creating user subscriptions...")
        sub1, created = UserSubscription.objects.get_or_create(
            subscriber=user3,
            subscribed_to=user1,
            defaults={'notify_on_new_chat': True}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"✓ {user3.email} subscribed to {user1.email}"))

        sub2, created = UserSubscription.objects.get_or_create(
            subscriber=user4,
            subscribed_to=user1,
            defaults={'notify_on_new_chat': True}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"✓ {user4.email} subscribed to {user1.email}"))

        sub3, created = UserSubscription.objects.get_or_create(
            subscriber=user3,
            subscribed_to=user2,
            defaults={'notify_on_new_chat': True}
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"✓ {user3.email} subscribed to {user2.email}"))

        # Create test chat rooms
        self.stdout.write("\n4. Creating test chat rooms...")
        chat1, created = ChatRoom.objects.get_or_create(
            name='Tech Talk Tuesday',
            host=user1,
            defaults={
                'description': 'Weekly tech discussion and Q&A',
                'access_mode': ChatRoom.ACCESS_PUBLIC,
                'voice_enabled': True,
                'video_enabled': False,
                'photo_enabled': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"✓ Chat room created: {chat1.name} (/{chat1.code})"))
        else:
            self.stdout.write(f"✓ Chat room already exists: {chat1.name} (/{chat1.code})")

        chat2, created = ChatRoom.objects.get_or_create(
            name='VIP Community',
            host=user2,
            defaults={
                'description': 'Exclusive community for members',
                'access_mode': ChatRoom.ACCESS_PRIVATE,
                'access_code': 'VIP2024',
                'voice_enabled': True,
                'video_enabled': True,
                'photo_enabled': True,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"✓ Chat room created: {chat2.name} (/{chat2.code})"))
        else:
            self.stdout.write(f"✓ Chat room already exists: {chat2.name} (/{chat2.code})")

        # Create test messages
        self.stdout.write("\n5. Creating test messages...")
        msg1, created = Message.objects.get_or_create(
            chat_room=chat1,
            username=user1.get_display_name(),
            user=user1,
            defaults={
                'content': 'Welcome everyone! Today we\'re discussing the latest in web development.',
                'message_type': Message.MESSAGE_HOST,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"✓ Message created from {msg1.username}"))

        msg2, created = Message.objects.get_or_create(
            chat_room=chat1,
            username=user3.get_display_name(),
            user=user3,
            defaults={
                'content': 'Thanks for hosting! Excited to be here.',
                'message_type': Message.MESSAGE_NORMAL,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"✓ Message created from {msg2.username}"))

        msg3, created = Message.objects.get_or_create(
            chat_room=chat1,
            username='Anonymous User',
            user=None,
            defaults={
                'content': 'Can someone explain what Next.js is?',
                'message_type': Message.MESSAGE_NORMAL,
            }
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"✓ Message created from {msg3.username} (guest, no account)"))

        # Summary
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.SUCCESS("✅ Test data creation complete!"))
        self.stdout.write("="*60)
        self.stdout.write("\nLogin credentials (all users):")
        self.stdout.write("  Password: demo123")
        self.stdout.write("\nAccounts created:")
        self.stdout.write("  • Superuser: admin@chatpop.app")
        self.stdout.write("  • User 1: jane@chatpop.app (Jane Doe)")
        self.stdout.write("  • User 2: john@chatpop.app (John Smith)")
        self.stdout.write("  • User 3: alice@chatpop.app (Alice Wonder)")
        self.stdout.write("  • User 4: bob@chatpop.app (Bob Builder)")
        self.stdout.write("\nSubscriptions:")
        self.stdout.write("  • Alice subscribes to Jane")
        self.stdout.write("  • Bob subscribes to Jane")
        self.stdout.write("  • Alice subscribes to John")
        self.stdout.write("\nChat Rooms:")
        self.stdout.write(f"  • {chat1.name} - Public (code: {chat1.code})")
        self.stdout.write(f"  • {chat2.name} - Private (code: {chat2.code}, access: VIP2024)")
        self.stdout.write("\nDjango Admin: https://localhost:9000/admin")
        self.stdout.write("  Login with: admin@chatpop.app / demo123")
        self.stdout.write("="*60)
