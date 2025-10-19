"""
Django management command to populate a chat room with test messages

Usage:
    python manage.py populate_chat <chat_room_code>
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from decimal import Decimal
from accounts.models import User
from chats.models import ChatRoom, Message


class Command(BaseCommand):
    help = """Populate a chat room with various test messages.

    Creates:
    - HOST messages (3)
    - PINNED messages from logged-in users (2)
    - PINNED messages from anonymous users (2)
    - REGULAR messages from logged-in users (5)
    - REGULAR messages from anonymous users (10)
    - Mixed conversation (6)
    """

    def add_arguments(self, parser):
        parser.add_argument(
            'chat_code',
            type=str,
            help='Chat room code (e.g., ABC123XY)'
        )

    def handle(self, *args, **options):
        """Create a variety of test messages for a chat room"""
        chat_code = options['chat_code'].upper()

        try:
            chat_room = ChatRoom.objects.get(code=chat_code, is_active=True)
        except ChatRoom.DoesNotExist:
            raise CommandError(f"Chat room with code '{chat_code}' not found")

        host = chat_room.host

        # Get or create some test users
        test_users = []
        for i in range(3):
            email = f"testuser{i+1}@test.com"
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'display_name': f'TestUser{i+1}',
                    'first_name': f'Test{i+1}',
                    'last_name': 'User'
                }
            )
            if created:
                user.set_password('demo123')
                user.save()
            test_users.append(user)

        self.stdout.write(f"🎯 Creating test messages for chat room: {chat_room.name} ({chat_code})")
        self.stdout.write(f"👤 Host: {host.email}")
        self.stdout.write(f"👥 Test users: {', '.join([u.email for u in test_users])}")
        self.stdout.write("")

        messages_created = []

        # 1. HOST MESSAGES (should appear at the very top)
        self.stdout.write("📌 Creating host messages...")
        host_messages = [
            "Welcome to the chat! 👋",
            "Remember to be respectful to everyone here.",
            "Check out the pinned messages for important info!",
        ]
        for content in host_messages:
            msg = Message.objects.create(
                chat_room=chat_room,
                user=host,
                username=host.get_display_name(),
                message_type=Message.MESSAGE_HOST,
                content=content
            )
            messages_created.append(msg)
            self.stdout.write(self.style.SUCCESS(f"  ✅ Host: {content}"))

        # 2. PINNED MESSAGES by logged-in users
        self.stdout.write("\n📍 Creating pinned messages from logged-in users...")
        for i, user in enumerate(test_users[:2]):  # First 2 test users
            msg = Message.objects.create(
                chat_room=chat_room,
                user=user,
                username=user.get_display_name(),
                content=f"This is an important announcement from {user.get_display_name()}!"
            )
            # Pin the message
            msg.pin_message(
                amount_paid=Decimal('5.00') + Decimal(i),
                duration_minutes=120
            )
            messages_created.append(msg)
            self.stdout.write(self.style.SUCCESS(f"  ✅ {user.get_display_name()}: {msg.content} (Pinned)"))

        # 3. PINNED MESSAGES by anonymous users
        self.stdout.write("\n📍 Creating pinned messages from anonymous users...")
        anonymous_pinned = [
            ("JohnDoe", "Hey everyone! This message is pinned!"),
            ("SarahK", "Important: Event starts at 3PM!"),
        ]
        for username, content in anonymous_pinned:
            msg = Message.objects.create(
                chat_room=chat_room,
                user=None,
                username=username,
                content=content
            )
            msg.pin_message(
                amount_paid=Decimal('3.00'),
                duration_minutes=60
            )
            messages_created.append(msg)
            self.stdout.write(self.style.SUCCESS(f"  ✅ {username} (guest): {content} (Pinned)"))

        # 4. REGULAR MESSAGES by logged-in users
        self.stdout.write("\n💬 Creating regular messages from logged-in users...")
        logged_in_messages = [
            (test_users[0], "Hey everyone! Great to be here!"),
            (test_users[1], "This is such a cool chat room!"),
            (test_users[2], "I totally agree with the previous messages"),
            (test_users[0], "Has anyone tried the new feature?"),
            (test_users[1], "Yes! It's amazing!"),
        ]
        for user, content in logged_in_messages:
            msg = Message.objects.create(
                chat_room=chat_room,
                user=user,
                username=user.get_display_name(),
                content=content
            )
            messages_created.append(msg)
            self.stdout.write(self.style.SUCCESS(f"  ✅ {user.get_display_name()}: {content}"))

        # 5. REGULAR MESSAGES by anonymous users (different usernames)
        self.stdout.write("\n💬 Creating regular messages from anonymous users...")
        anonymous_messages = [
            ("Alice123", "Hello from a guest user!"),
            ("BobTheBuilder", "This is my first time here"),
            ("CoolCat99", "Love the vibe in this chat!"),
            ("RandomUser", "Can someone help me with something?"),
            ("Alice123", "Sure, what do you need help with?"),
            ("TechGuru", "I might be able to help!"),
            ("BobTheBuilder", "Thanks everyone, you're all so helpful!"),
            ("MusicLover", "Anyone else here a fan of indie music?"),
            ("CoolCat99", "Absolutely! What are your favorite bands?"),
            ("Anonymous", "Just stopping by to say hi 👋"),
        ]
        for username, content in anonymous_messages:
            msg = Message.objects.create(
                chat_room=chat_room,
                user=None,
                username=username,
                content=content
            )
            messages_created.append(msg)
            self.stdout.write(self.style.SUCCESS(f"  ✅ {username} (guest): {content}"))

        # 6. Mix of messages to simulate a real conversation
        self.stdout.write("\n🔄 Creating mixed conversation...")
        mixed_messages = [
            (host, "Thanks for joining everyone!", Message.MESSAGE_HOST),
            (test_users[0], "Happy to be here!", Message.MESSAGE_NORMAL),
            (None, "GuestUser99", "This is awesome!"),
            (test_users[1], "When's the next event?", Message.MESSAGE_NORMAL),
            (None, "EventPlanner", "Next Monday at 5PM!"),
            (host, "Don't forget to check the schedule!", Message.MESSAGE_HOST),
        ]
        for item in mixed_messages:
            if item[0] is None:
                # Anonymous message: (None, username, content)
                _, username, content = item
                msg_type = Message.MESSAGE_NORMAL
                msg = Message.objects.create(
                    chat_room=chat_room,
                    user=None,
                    username=username,
                    content=content,
                    message_type=msg_type
                )
                self.stdout.write(self.style.SUCCESS(f"  ✅ {username} (guest): {content}"))
            else:
                # Logged-in user message: (user, content, msg_type)
                user_val, content, msg_type = item
                username = user_val.get_display_name()
                msg = Message.objects.create(
                    chat_room=chat_room,
                    user=user_val,
                    username=username,
                    content=content,
                    message_type=msg_type
                )
                if msg_type == Message.MESSAGE_HOST:
                    self.stdout.write(self.style.SUCCESS(f"  ✅ HOST ({username}): {content}"))
                else:
                    self.stdout.write(self.style.SUCCESS(f"  ✅ {username}: {content}"))
            messages_created.append(msg)

        self.stdout.write(self.style.SUCCESS(f"\n✨ Successfully created {len(messages_created)} test messages!"))
        self.stdout.write(f"📊 Chat room now has {chat_room.messages.filter(is_deleted=False).count()} total messages")
        self.stdout.write(f"\n🔗 Visit: https://localhost:4000/chat/{chat_code}")
