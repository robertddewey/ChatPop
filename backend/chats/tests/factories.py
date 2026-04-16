"""
Test factories for cache performance work.

Fast, bulk-friendly builders for User, ChatRoom, ChatParticipation, and Message.
Designed for integration and load tests that need thousands of rows without
thousands of round-trips.

Design notes:
- `make_user`, `make_room`, `make_participation` create single rows — use for
  small setups.
- `make_messages` is the bulk path: `Message.bulk_create` + direct timestamp
  assignment (bypasses `auto_now_add`) so chronological ordering is controllable.
- `MessageMix` holds the type distribution for realistic mixes
  (e.g. 5% photo / 2% video / 2% voice / 1% highlight).

Intentionally does NOT touch Redis — factories are Postgres-only so tests can
exercise the cache-hydration path or write their own Redis state.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import List, Optional

from django.utils import timezone

from accounts.models import User
from chats.models import ChatParticipation, ChatRoom, Message


# ---------------------------------------------------------------------------
# Single-row builders
# ---------------------------------------------------------------------------


def make_user(
    email: Optional[str] = None,
    reserved_username: Optional[str] = None,
    password: str = 'testpass123',
) -> User:
    """Create a single user. Email and reserved_username auto-generated if omitted."""
    suffix = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        email=email or f'user-{suffix}@example.com',
        password=password,
        reserved_username=reserved_username or f'User{suffix}',
    )


def make_room(
    host: Optional[User] = None,
    name: str = 'Test Chat',
    code: Optional[str] = None,
    access_mode: str = 'public',
) -> ChatRoom:
    """Create a single chat room. Host auto-created if omitted."""
    return ChatRoom.objects.create(
        code=code or f'test-{uuid.uuid4().hex[:8]}',
        name=name,
        host=host or make_user(),
        access_mode=access_mode,
    )


def make_participation(
    room: ChatRoom,
    username: str,
    user: Optional[User] = None,
    is_spotlight: bool = False,
) -> ChatParticipation:
    """Create a ChatParticipation. Caller provides username explicitly."""
    return ChatParticipation.objects.create(
        chat_room=room,
        user=user,
        username=username,
        ip_address='127.0.0.1',
        is_spotlight=is_spotlight,
    )


# ---------------------------------------------------------------------------
# Message bulk builder
# ---------------------------------------------------------------------------


@dataclass
class MessageMix:
    """Percentage distribution for `make_messages`. Remaining % is plain text.

    Example: MessageMix(photo_pct=5, voice_pct=2, video_pct=2, highlight_pct=1)
    -> 5% photos, 2% voice, 2% video, 1% highlighted text, 90% plain text.
    """
    photo_pct: float = 0
    video_pct: float = 0
    voice_pct: float = 0
    gift_pct: float = 0
    highlight_pct: float = 0

    def __post_init__(self):
        total = self.photo_pct + self.video_pct + self.voice_pct + self.gift_pct + self.highlight_pct
        if total > 100:
            raise ValueError(f'MessageMix percentages sum to {total}%, must be <= 100')


def _build_message(
    room: ChatRoom,
    username: str,
    created_at,
    kind: str,
    content: str,
    user: Optional[User] = None,
) -> Message:
    """Construct a Message instance (unsaved) with fields set based on `kind`."""
    msg = Message(
        id=uuid.uuid4(),
        chat_room=room,
        username=username,
        user=user,
        content=content,
        created_at=created_at,
        updated_at=created_at,
    )
    if kind == 'photo':
        msg.photo_url = f'/api/chats/media/photos/{uuid.uuid4()}.jpg'
        msg.photo_width = 1080
        msg.photo_height = 1920
    elif kind == 'video':
        msg.video_url = f'/api/chats/media/videos/{uuid.uuid4()}.mp4'
        msg.video_duration = Decimal('12.50')
        msg.video_thumbnail_url = f'/api/chats/media/video_thumbnails/{uuid.uuid4()}_thumb.jpg'
        msg.video_width = 1080
        msg.video_height = 1920
    elif kind == 'voice':
        msg.voice_url = f'/api/chats/media/voice_messages/{uuid.uuid4()}.m4a'
        msg.voice_duration = Decimal('6.73')
        msg.voice_waveform = [0.1, 0.5, 0.8, 0.4, 0.2]
    elif kind == 'gift':
        msg.message_type = 'gift'
        msg.gift_recipient = username  # placeholder — caller can override
    elif kind == 'highlight':
        msg.is_highlight = True
        msg.highlighted_at = created_at
    # 'text' kind needs no extra fields
    return msg


def make_messages(
    room: ChatRoom,
    count: int,
    usernames: Optional[List[str]] = None,
    mix: Optional[MessageMix] = None,
    start_time=None,
    step_seconds: float = 1.0,
) -> List[Message]:
    """Bulk-create `count` messages in `room` with controllable type distribution.

    Uses `Message.objects.bulk_create` for speed (3000+ messages/sec on local Postgres).
    Timestamps are assigned explicitly and increase monotonically, so chronological
    ordering is deterministic across runs — critical for eviction-order assertions.

    Args:
        room: the chat room to attach messages to.
        count: total messages to create.
        usernames: pool of usernames to cycle through. Defaults to ['Alice', 'Bob', 'Carol'].
        mix: MessageMix controlling type distribution. Defaults to all-text.
        start_time: timezone-aware datetime of the first message. Defaults to now - count*step.
        step_seconds: seconds between consecutive messages.

    Returns:
        List of created Message instances (ordered oldest-first).
    """
    if count <= 0:
        return []

    usernames = usernames or ['Alice', 'Bob', 'Carol']
    mix = mix or MessageMix()
    if start_time is None:
        start_time = timezone.now() - timedelta(seconds=count * step_seconds)

    # Determine the type of each message based on mix percentages.
    # Simple deterministic distribution: walk the count and assign by modulo buckets.
    # Not statistically random, but predictable and repeatable for tests.
    kinds: List[str] = []
    photo_cutoff = mix.photo_pct
    video_cutoff = photo_cutoff + mix.video_pct
    voice_cutoff = video_cutoff + mix.voice_pct
    gift_cutoff = voice_cutoff + mix.gift_pct
    highlight_cutoff = gift_cutoff + mix.highlight_pct
    for i in range(count):
        pct = (i * 100.0 / count) % 100.0  # 0.0 .. <100.0
        if pct < photo_cutoff:
            kinds.append('photo')
        elif pct < video_cutoff:
            kinds.append('video')
        elif pct < voice_cutoff:
            kinds.append('voice')
        elif pct < gift_cutoff:
            kinds.append('gift')
        elif pct < highlight_cutoff:
            kinds.append('highlight')
        else:
            kinds.append('text')

    instances = []
    for i, kind in enumerate(kinds):
        ts = start_time + timedelta(seconds=i * step_seconds)
        username = usernames[i % len(usernames)]
        instances.append(_build_message(
            room=room,
            username=username,
            created_at=ts,
            kind=kind,
            content=f'{kind} message {i}',
        ))

    # bulk_create does not honor auto_now_add; explicit created_at/updated_at survives.
    Message.objects.bulk_create(instances, batch_size=1000)
    return instances


def count_by_kind(messages: List[Message]) -> dict:
    """Utility: tally kinds in a message list. Useful for asserting mix distributions."""
    counts = {'text': 0, 'photo': 0, 'video': 0, 'voice': 0, 'gift': 0, 'highlight': 0}
    for m in messages:
        if m.message_type == 'gift':
            counts['gift'] += 1
        elif m.is_highlight:
            counts['highlight'] += 1
        elif m.photo_url:
            counts['photo'] += 1
        elif m.video_url:
            counts['video'] += 1
        elif m.voice_url:
            counts['voice'] += 1
        else:
            counts['text'] += 1
    return counts
