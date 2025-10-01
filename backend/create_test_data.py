#!/usr/bin/env python
"""
Script to create test data for ChatPop
Run with: ./venv/bin/python create_test_data.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'chatpop.settings')
django.setup()

from accounts.models import User, UserSubscription
from chats.models import ChatRoom, Message, BackRoom, BackRoomMember, Transaction

def create_test_data():
    print("Creating test data...")

    # Create superuser
    print("\n1. Creating superuser...")
    if not User.objects.filter(email='admin@chatpop.app').exists():
        superuser = User.objects.create_superuser(
            email='admin@chatpop.app',
            password='demo123',
            display_name='Admin'
        )
        print(f"✓ Superuser created: {superuser.email}")
    else:
        superuser = User.objects.get(email='admin@chatpop.app')
        print(f"✓ Superuser already exists: {superuser.email}")

    # Create test users (registered users - any can be a host)
    print("\n2. Creating test registered users...")
    user1, created = User.objects.get_or_create(
        email='jane@chatpop.app',
        defaults={
            'display_name': 'Jane Doe',
        }
    )
    if created:
        user1.set_password('demo123')
        user1.save()
        print(f"✓ User created: {user1.email}")
    else:
        print(f"✓ User already exists: {user1.email}")

    user2, created = User.objects.get_or_create(
        email='john@chatpop.app',
        defaults={
            'display_name': 'John Smith',
        }
    )
    if created:
        user2.set_password('demo123')
        user2.save()
        print(f"✓ User created: {user2.email}")
    else:
        print(f"✓ User already exists: {user2.email}")

    user3, created = User.objects.get_or_create(
        email='alice@chatpop.app',
        defaults={
            'display_name': 'Alice Wonder',
        }
    )
    if created:
        user3.set_password('demo123')
        user3.save()
        print(f"✓ User created: {user3.email}")
    else:
        print(f"✓ User already exists: {user3.email}")

    user4, created = User.objects.get_or_create(
        email='bob@chatpop.app',
        defaults={
            'display_name': 'Bob Builder',
        }
    )
    if created:
        user4.set_password('demo123')
        user4.save()
        print(f"✓ User created: {user4.email}")
    else:
        print(f"✓ User already exists: {user4.email}")

    # Create subscriptions
    print("\n3. Creating user subscriptions...")
    sub1, created = UserSubscription.objects.get_or_create(
        subscriber=user3,
        subscribed_to=user1,
        defaults={'notify_on_new_chat': True}
    )
    if created:
        print(f"✓ {user3.email} subscribed to {user1.email}")

    sub2, created = UserSubscription.objects.get_or_create(
        subscriber=user4,
        subscribed_to=user1,
        defaults={'notify_on_new_chat': True}
    )
    if created:
        print(f"✓ {user4.email} subscribed to {user1.email}")

    sub3, created = UserSubscription.objects.get_or_create(
        subscriber=user3,
        subscribed_to=user2,
        defaults={'notify_on_new_chat': True}
    )
    if created:
        print(f"✓ {user3.email} subscribed to {user2.email}")

    # Create test chat rooms
    print("\n4. Creating test chat rooms...")
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
        print(f"✓ Chat room created: {chat1.name} (/{chat1.code})")
    else:
        print(f"✓ Chat room already exists: {chat1.name} (/{chat1.code})")

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
        print(f"✓ Chat room created: {chat2.name} (/{chat2.code})")
    else:
        print(f"✓ Chat room already exists: {chat2.name} (/{chat2.code})")

    # Create back room for chat2
    print("\n5. Creating back room...")
    backroom, created = BackRoom.objects.get_or_create(
        chat_room=chat2,
        defaults={
            'price_per_seat': 9.99,
            'max_seats': 10,
            'is_active': True,
        }
    )
    if created:
        print(f"✓ Back room created for {chat2.name}: ${backroom.price_per_seat}/seat, {backroom.max_seats} seats")
    else:
        print(f"✓ Back room already exists for {chat2.name}")

    # Create test messages
    print("\n6. Creating test messages...")
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
        print(f"✓ Message created from {msg1.username}")

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
        print(f"✓ Message created from {msg2.username}")

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
        print(f"✓ Message created from {msg3.username} (guest, no account)")

    print("\n" + "="*60)
    print("✅ Test data creation complete!")
    print("="*60)
    print("\nLogin credentials (all users):")
    print("  Password: demo123")
    print("\nAccounts created:")
    print(f"  • Superuser: admin@chatpop.app")
    print(f"  • User 1: jane@chatpop.app (Jane Doe)")
    print(f"  • User 2: john@chatpop.app (John Smith)")
    print(f"  • User 3: alice@chatpop.app (Alice Wonder)")
    print(f"  • User 4: bob@chatpop.app (Bob Builder)")
    print("\nSubscriptions:")
    print(f"  • Alice subscribes to Jane")
    print(f"  • Bob subscribes to Jane")
    print(f"  • Alice subscribes to John")
    print("\nChat Rooms:")
    print(f"  • {chat1.name} - Public (code: {chat1.code})")
    print(f"  • {chat2.name} - Private (code: {chat2.code}, access: VIP2024)")
    print(f"    └─ Back Room: ${backroom.price_per_seat}/seat, {backroom.max_seats} seats max")
    print("\nDjango Admin: http://localhost:9000/admin")
    print("  Login with: admin@chatpop.app / demo123")
    print("="*60)

if __name__ == '__main__':
    create_test_data()
