"""
Django management command to populate a chat room with test messages

Usage:
    python manage.py populate_chat <username/chat_code>
    python manage.py populate_chat <username/chat_code> --broadcast
    python manage.py populate_chat <username/chat_code> --broadcast --duration 60 --rate 2
    python manage.py populate_chat <username/chat_code> --broadcast --count 50 --rate 1
"""
import random
import time
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from accounts.models import User
from chats.models import ChatRoom, Message
from chats.serializers import MessageSerializer
from chats.utils.performance.cache import MessageCache


# Pool of realistic chat messages
REALISTIC_MESSAGES = [
    # Greetings and arrivals
    "Hey everyone! 👋",
    "Just joined, what did I miss?",
    "Hello hello!",
    "What's up everyone?",
    "Finally made it!",
    "Hey! Long time no see",
    "Yo! What's happening?",
    "Hi all!",
    "Greetings from NYC!",
    "Just popping in to say hi",

    # General conversation
    "This is such a cool chat room",
    "Love the vibe here",
    "Anyone else having a great day?",
    "This is exactly what I needed",
    "Can't believe how fast this chat is going",
    "LOL that's hilarious",
    "Haha totally agree",
    "So true!",
    "100% this",
    "Facts!",
    "No way!",
    "Wait what?",
    "That's awesome!",
    "Wow didn't expect that",
    "Mind = blown 🤯",

    # Questions and engagement
    "What does everyone think about this?",
    "Anyone else feel the same way?",
    "Has anyone tried this before?",
    "What's everyone's favorite part?",
    "Quick question - how does this work?",
    "Can someone explain?",
    "Is it just me or...?",
    "Anyone from California here?",
    "Who's watching the game later?",
    "What music is everyone into?",

    # Reactions and responses
    "That's a great point!",
    "Never thought about it that way",
    "You're absolutely right",
    "I was just thinking the same thing",
    "This is why I love this community",
    "Couldn't agree more",
    "Interesting perspective",
    "Thanks for sharing that!",
    "Really appreciate everyone here",
    "You guys are the best",

    # Casual chat
    "Just finished work, finally can relax",
    "Coffee break! ☕",
    "Working from home today",
    "Anyone else procrastinating? 😅",
    "Should probably be doing something productive",
    "This is way more fun than work",
    "Taking a quick break",
    "Lunch time here!",
    "It's almost Friday!",
    "Weekend vibes already",

    # Expressions
    "😂😂😂",
    "🔥🔥🔥",
    "❤️",
    "That's fire!",
    "LMAO",
    "Dead 💀",
    "I can't even",
    "Bruh",
    "No cap",
    "Fr fr",
]

# Pool of host messages
HOST_MESSAGES = [
    "Thanks for joining everyone! 🎉",
    "Welcome to the chat! Feel free to introduce yourselves",
    "Reminder: Keep it respectful and have fun!",
    "Great discussion going on here!",
    "Love seeing everyone engaged!",
    "Don't forget to check out the pinned messages",
    "Quick announcement coming up...",
    "Thanks for all the support! 🙏",
    "This community is amazing",
    "Shoutout to everyone participating today!",
]

# Pool of anonymous usernames
ANONYMOUS_USERNAMES = [
    "CoolCat99", "NightOwl", "StarGazer", "MoonWalker", "SunnyDay",
    "BlueSky", "RedPanda", "GreenTea", "PurpleHaze", "OrangeCrush",
    "SilverFox", "GoldenEagle", "IronWolf", "CrystalClear", "DiamondDust",
    "ThunderBolt", "LightningRod", "StormChaser", "RainMaker", "SnowFlake",
    "TechWiz", "CodeNinja", "DataDragon", "ByteMe", "PixelPerfect",
    "MusicLover", "BeatDrop", "MelodyMaker", "RhythmRider", "SoundWave",
    "FoodieLife", "CoffeeAddict", "PizzaKing", "TacoTuesday", "SushiSam",
    "TravelBug", "Wanderlust", "Globetrotter", "Adventurer", "Explorer",
    "NatureLover", "TreeHugger", "OceanVibes", "MountainMan", "DesertRose",
    "Gamer123", "ProPlayer", "NoobMaster", "AFK_Andy", "GGEasyWin",
    "Bookworm", "PageTurner", "StoryTime", "PlotTwist", "ChapterOne",
    "FitnessFreak", "GymRat", "YogaLife", "RunnerHigh", "LiftBro",
    "ArtistSoul", "CreativeMind", "DesignGuru", "ColorSplash", "SketchPad",
    "MovieBuff", "FilmFan", "CinemaLover", "PopcornTime", "BingeWatch",
    "NightShift", "EarlyBird", "Insomniac", "DreamCatcher", "SleepyHead",
    "LuckyCharm", "FourLeaf", "WishMaker", "StarDust", "MoonBeam",
    "CitySlicker", "CountryRoads", "SuburbLife", "Downtown", "Uptown",
    "RetroVibes", "Vintage90s", "OldSchool", "NewWave", "FutureTech",
    "ChillVibes", "RelaxMode", "ZenMaster", "PeacefulMind", "CalmSoul",
    "PartyPeople", "DanceFloor", "ClubLife", "MixMaster", "BeatJunkie",
]

# Placeholder image URLs (using picsum.photos)
PLACEHOLDER_IMAGES = [
    "https://picsum.photos/seed/chatpop1/800/600",
    "https://picsum.photos/seed/chatpop2/800/600",
    "https://picsum.photos/seed/chatpop3/800/600",
    "https://picsum.photos/seed/chatpop4/800/600",
    "https://picsum.photos/seed/chatpop5/800/600",
    "https://picsum.photos/seed/chatpop6/600/800",  # Portrait
    "https://picsum.photos/seed/chatpop7/600/800",  # Portrait
    "https://picsum.photos/seed/chatpop8/800/800",  # Square
    "https://picsum.photos/seed/chatpop9/800/800",  # Square
    "https://picsum.photos/seed/chatpop10/800/600",
]


class Command(BaseCommand):
    help = """Populate a chat room with test messages.

    Basic usage (creates batch of test messages):
        python manage.py populate_chat username/chat_code

    Continuous mode with broadcasting:
        python manage.py populate_chat username/chat_code --broadcast --duration 60 --rate 2

    Fixed count with broadcasting:
        python manage.py populate_chat username/chat_code --broadcast --count 50 --rate 1

    Options:
        --broadcast    Send messages via WebSocket (appear live in chat)
        --duration     Duration in seconds to send messages (continuous mode)
        --rate         Messages per second (default: 1)
        --count        Total number of messages to send (alternative to duration)
    """

    def add_arguments(self, parser):
        parser.add_argument(
            'chat_path',
            type=str,
            help='Chat room path in format username/code (e.g., robert/bar-room)'
        )
        parser.add_argument(
            '--broadcast',
            action='store_true',
            help='Broadcast messages via WebSocket for live updates'
        )
        parser.add_argument(
            '--duration',
            type=int,
            default=0,
            help='Duration in seconds to continuously send messages'
        )
        parser.add_argument(
            '--rate',
            type=float,
            default=1.0,
            help='Messages per second (default: 1.0)'
        )
        parser.add_argument(
            '--count',
            type=int,
            default=0,
            help='Total number of messages to send (alternative to duration)'
        )

    def handle(self, *args, **options):
        """Create a variety of test messages for a chat room"""
        chat_path = options['chat_path']
        broadcast = options['broadcast']
        duration = options['duration']
        rate = options['rate']
        count = options['count']

        # Parse username/code format
        if '/' not in chat_path:
            raise CommandError(
                f"Invalid format: '{chat_path}'\n"
                f"Expected format: username/code (e.g., robert/bar-room)"
            )

        username, chat_code = chat_path.split('/', 1)

        # Look up the host user
        try:
            host_user = User.objects.get(reserved_username=username)
        except User.DoesNotExist:
            raise CommandError(f"User with username '{username}' not found")

        # Look up the chat room (scoped to host + code)
        try:
            chat_room = ChatRoom.objects.get(
                host=host_user,
                code=chat_code,
                is_active=True
            )
        except ChatRoom.DoesNotExist:
            raise CommandError(
                f"Chat room '{chat_code}' not found for user '{username}'\n"
                f"Full path: {username}/{chat_code}"
            )

        host = chat_room.host

        # Get or create some test users
        test_users = []
        for i in range(3):
            email = f"testuser{i+1}@test.com"
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': f'Test{i+1}',
                    'last_name': 'User'
                }
            )
            if created:
                user.set_password('demo123')
                user.save()
            test_users.append(user)

        # Check if continuous mode is requested
        if duration > 0 or count > 0:
            self._run_continuous_mode(
                chat_room, host, test_users, username, chat_code,
                broadcast, duration, rate, count
            )
        else:
            self._run_batch_mode(
                chat_room, host, test_users, username, chat_code, broadcast
            )

    def _broadcast_message(self, chat_room, message):
        """Broadcast a message via WebSocket"""
        import json
        channel_layer = get_channel_layer()
        serializer = MessageSerializer(message, context={'request': None})
        # Convert to JSON and back to ensure all types are serializable (UUIDs -> strings)
        message_data = json.loads(json.dumps(serializer.data, default=str))

        # Use chat_room.code to match the consumer's group naming: f'chat_{chat_code}'
        # Key must be 'message_data' to match what the consumer expects in chat_message handler
        async_to_sync(channel_layer.group_send)(
            f"chat_{chat_room.code}",
            {
                "type": "chat_message",
                "message_data": message_data,
            }
        )

    def _create_random_message(self, chat_room, host, test_users, broadcast=False):
        """Create a random message with realistic distribution"""
        # Distribution: 70% anonymous, 20% logged-in users, 8% host, 2% photo
        roll = random.random()

        if roll < 0.02:
            # 2% chance: Photo message (anonymous)
            msg = Message.objects.create(
                chat_room=chat_room,
                user=None,
                username=random.choice(ANONYMOUS_USERNAMES),
                content="",
                message_type=Message.MESSAGE_NORMAL,
                photo_url=random.choice(PLACEHOLDER_IMAGES)
            )
            msg_type = "📷 PHOTO"
        elif roll < 0.10:
            # 8% chance: Host message
            msg = Message.objects.create(
                chat_room=chat_room,
                user=host,
                username=host.get_display_name(),
                content=random.choice(HOST_MESSAGES),
                message_type=Message.MESSAGE_HOST
            )
            msg_type = "👑 HOST"
        elif roll < 0.30:
            # 20% chance: Logged-in user
            user = random.choice(test_users)
            msg = Message.objects.create(
                chat_room=chat_room,
                user=user,
                username=user.get_display_name(),
                content=random.choice(REALISTIC_MESSAGES),
                message_type=Message.MESSAGE_NORMAL
            )
            msg_type = "👤 USER"
        else:
            # 70% chance: Anonymous user
            msg = Message.objects.create(
                chat_room=chat_room,
                user=None,
                username=random.choice(ANONYMOUS_USERNAMES),
                content=random.choice(REALISTIC_MESSAGES),
                message_type=Message.MESSAGE_NORMAL
            )
            msg_type = "👻 ANON"

        # Add to Redis cache
        MessageCache.add_message(msg)

        # Broadcast if requested
        if broadcast:
            self._broadcast_message(chat_room, msg)

        return msg, msg_type

    def _run_continuous_mode(self, chat_room, host, test_users, username, chat_code,
                             broadcast, duration, rate, count):
        """Run in continuous mode, sending messages over time"""
        interval = 1.0 / rate if rate > 0 else 1.0

        self.stdout.write(f"🚀 Starting continuous mode for chat room: {chat_room.name}")
        self.stdout.write(f"📍 Path: {username}/{chat_code}")
        self.stdout.write(f"📡 Broadcasting: {'ON' if broadcast else 'OFF'}")

        if count > 0:
            self.stdout.write(f"🔢 Count: {count} messages")
        else:
            self.stdout.write(f"⏱️  Duration: {duration} seconds")

        self.stdout.write(f"⚡ Rate: {rate} msg/sec (interval: {interval:.2f}s)")
        self.stdout.write("")
        self.stdout.write("Press Ctrl+C to stop\n")

        messages_sent = 0
        start_time = time.time()

        try:
            while True:
                # Check stop conditions
                if count > 0 and messages_sent >= count:
                    break
                if duration > 0 and (time.time() - start_time) >= duration:
                    break

                # Create and optionally broadcast a random message
                msg, msg_type = self._create_random_message(
                    chat_room, host, test_users, broadcast
                )
                messages_sent += 1

                # Display progress
                display_content = msg.content[:40] + "..." if len(msg.content) > 40 else msg.content
                if msg.photo_url:
                    display_content = f"[Photo: {msg.photo_url}]"
                self.stdout.write(
                    f"  [{messages_sent}] {msg_type} {msg.username}: {display_content}"
                )

                # Wait for next message
                time.sleep(interval)

        except KeyboardInterrupt:
            self.stdout.write("\n\n⏹️  Stopped by user")

        elapsed = time.time() - start_time
        self.stdout.write(self.style.SUCCESS(
            f"\n✨ Sent {messages_sent} messages in {elapsed:.1f} seconds"
        ))
        self.stdout.write(f"📊 Chat room now has {chat_room.messages.filter(is_deleted=False).count()} total messages")
        self.stdout.write(f"\n🔗 Visit: https://localhost:4000/{username}/{chat_code}")

    def _run_batch_mode(self, chat_room, host, test_users, username, chat_code, broadcast):
        """Run in batch mode, creating a fixed set of test messages"""
        self.stdout.write(f"🎯 Creating test messages for chat room: {chat_room.name}")
        self.stdout.write(f"📍 Path: {username}/{chat_code}")
        self.stdout.write(f"👤 Host: {host.email}")
        self.stdout.write(f"👥 Test users: {', '.join([u.email for u in test_users])}")
        self.stdout.write(f"📡 Broadcasting: {'ON' if broadcast else 'OFF'}")
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
            # Pin the message (amount in cents)
            msg.pin_message(
                amount_paid_cents=500 + (i * 100),
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
        for anon_username, content in anonymous_pinned:
            msg = Message.objects.create(
                chat_room=chat_room,
                user=None,
                username=anon_username,
                content=content
            )
            msg.pin_message(
                amount_paid_cents=300,
                duration_minutes=60
            )
            messages_created.append(msg)
            self.stdout.write(self.style.SUCCESS(f"  ✅ {anon_username} (guest): {content} (Pinned)"))

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
        for anon_username, content in anonymous_messages:
            msg = Message.objects.create(
                chat_room=chat_room,
                user=None,
                username=anon_username,
                content=content
            )
            messages_created.append(msg)
            self.stdout.write(self.style.SUCCESS(f"  ✅ {anon_username} (guest): {content}"))

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
                _, anon_username, content = item
                msg_type = Message.MESSAGE_NORMAL
                msg = Message.objects.create(
                    chat_room=chat_room,
                    user=None,
                    username=anon_username,
                    content=content,
                    message_type=msg_type
                )
                self.stdout.write(self.style.SUCCESS(f"  ✅ {anon_username} (guest): {content}"))
            else:
                # Logged-in user message: (user, content, msg_type)
                user_val, content, msg_type = item
                display_username = user_val.get_display_name()
                msg = Message.objects.create(
                    chat_room=chat_room,
                    user=user_val,
                    username=display_username,
                    content=content,
                    message_type=msg_type
                )
                if msg_type == Message.MESSAGE_HOST:
                    self.stdout.write(self.style.SUCCESS(f"  ✅ HOST ({display_username}): {content}"))
                else:
                    self.stdout.write(self.style.SUCCESS(f"  ✅ {display_username}: {content}"))
            messages_created.append(msg)

        # Add all messages to Redis cache so they appear immediately
        self.stdout.write("\n📦 Adding messages to Redis cache...")
        cached_count = 0
        for msg in messages_created:
            if MessageCache.add_message(msg):
                cached_count += 1
        self.stdout.write(self.style.SUCCESS(f"  ✅ Cached {cached_count}/{len(messages_created)} messages"))

        # Broadcast all messages if requested
        if broadcast:
            self.stdout.write("\n📡 Broadcasting messages via WebSocket...")
            for msg in messages_created:
                self._broadcast_message(chat_room, msg)
            self.stdout.write(self.style.SUCCESS(f"  ✅ Broadcast {len(messages_created)} messages"))

        self.stdout.write(self.style.SUCCESS(f"\n✨ Successfully created {len(messages_created)} test messages!"))
        self.stdout.write(f"📊 Chat room now has {chat_room.messages.filter(is_deleted=False).count()} total messages")
        self.stdout.write(f"\n🔗 Visit: https://localhost:4000/{username}/{chat_code}")
