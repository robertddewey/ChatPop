"""
Script to create test messages for chat rooms
Usage: python create_test_messages.py <chat_room_code>
"""
import os
import sys
import django
from datetime import timedelta
from django.utils import timezone
from decimal import Decimal

# Setup Django environment
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatpop.settings')
django.setup()

from accounts.models import User
from chats.models import ChatRoom, Message


def create_test_messages(chat_code):
    """Create a variety of test messages for a chat room"""

    try:
        chat_room = ChatRoom.objects.get(code=chat_code, is_active=True)
    except ChatRoom.DoesNotExist:
        print(f"❌ Chat room with code '{chat_code}' not found")
        return

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

    print(f"🎯 Creating test messages for chat room: {chat_room.name} ({chat_code})")
    print(f"👤 Host: {host.email}")
    print(f"👥 Test users: {', '.join([u.email for u in test_users])}")
    print()

    messages_created = []

    # 1. HOST MESSAGES (should appear at the very top)
    print("📌 Creating host messages...")
    host_messages = [
        "Welcome to the chat! 👋",
        "Remember to be respectful to everyone here.",
        "Check out the pinned messages for important info!",
    ]
    for content in host_messages:
        msg = Message.objects.create(
            chat_room=chat_room,
            user=host,
            username=host.display_name or host.email.split('@')[0],
            message_type=Message.MESSAGE_HOST,
            content=content
        )
        messages_created.append(msg)
        print(f"  ✅ Host: {content}")

    # 2. PINNED MESSAGES by logged-in users
    print("\n📍 Creating pinned messages from logged-in users...")
    now = timezone.now()
    for i, user in enumerate(test_users[:2]):  # First 2 test users
        msg = Message.objects.create(
            chat_room=chat_room,
            user=user,
            username=user.display_name or user.email.split('@')[0],
            content=f"This is an important announcement from {user.display_name}!"
        )
        # Pin the message
        msg.pin_message(
            amount_paid=Decimal('5.00') + Decimal(i),
            duration_minutes=120
        )
        messages_created.append(msg)
        print(f"  ✅ {user.display_name}: {msg.content} (Pinned)")

    # 3. PINNED MESSAGES by anonymous users
    print("\n📍 Creating pinned messages from anonymous users...")
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
        print(f"  ✅ {username} (guest): {content} (Pinned)")

    # 4. REGULAR MESSAGES by logged-in users
    print("\n💬 Creating regular messages from logged-in users...")
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
            username=user.display_name or user.email.split('@')[0],
            content=content
        )
        messages_created.append(msg)
        print(f"  ✅ {user.display_name}: {content}")

    # 5. REGULAR MESSAGES by anonymous users (different usernames)
    print("\n💬 Creating regular messages from anonymous users...")
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
        print(f"  ✅ {username} (guest): {content}")

    # 6. Mix of messages to simulate a real conversation
    print("\n🔄 Creating mixed conversation...")
    mixed_messages = [
        (host, "Thanks for joining everyone!", Message.MESSAGE_HOST),
        (test_users[0], "Happy to be here!", Message.MESSAGE_NORMAL),
        (None, "GuestUser99", "This is awesome!", Message.MESSAGE_NORMAL),
        (test_users[1], "When's the next event?", Message.MESSAGE_NORMAL),
        (None, "EventPlanner", "Next Monday at 5PM!", Message.MESSAGE_NORMAL),
        (host, "Don't forget to check the schedule!", Message.MESSAGE_HOST),
    ]
    for user_or_none, content_or_username, msg_type in mixed_messages:
        if user_or_none is None:
            # Anonymous message
            msg = Message.objects.create(
                chat_room=chat_room,
                user=None,
                username=content_or_username,
                content=msg_type,  # In this case, msg_type is actually the content
                message_type=Message.MESSAGE_NORMAL
            )
            print(f"  ✅ {content_or_username} (guest): {msg_type}")
        else:
            # Logged-in user message
            username = user_or_none.display_name or user_or_none.email.split('@')[0]
            msg = Message.objects.create(
                chat_room=chat_room,
                user=user_or_none,
                username=username,
                content=content_or_username,
                message_type=msg_type
            )
            if msg_type == Message.MESSAGE_HOST:
                print(f"  ✅ HOST ({username}): {content_or_username}")
            else:
                print(f"  ✅ {username}: {content_or_username}")
        messages_created.append(msg)

    # Update message count
    chat_room.message_count = chat_room.messages.filter(is_deleted=False).count()
    chat_room.save()

    print(f"\n✨ Successfully created {len(messages_created)} test messages!")
    print(f"📊 Chat room now has {chat_room.message_count} total messages")
    print(f"\n🔗 Visit: http://localhost:3002/chat/{chat_code}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python create_test_messages.py <chat_room_code>")
        print("\nExample: python create_test_messages.py ABC123XY")
        sys.exit(1)

    chat_code = sys.argv[1].upper()
    create_test_messages(chat_code)
