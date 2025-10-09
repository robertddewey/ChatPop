# Generated migration to apply emerald green styling to pinned messages
from django.db import migrations


def update_pinned_message_styling(apps, schema_editor):
    """Apply emerald green color scheme to pinned messages"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    try:
        theme = ChatTheme.objects.get(id=1)  # dark-mode theme

        # Apply emerald green styling with left border accent
        theme.pinned_message = 'max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-3 bg-emerald-600 text-white shadow-lg border-l-4 border-emerald-400'
        theme.pinned_text = 'text-sm text-white'
        theme.pin_icon_color = 'text-emerald-400'

        # Set pinned_username to gray (frontend will use myUsername for owned messages)
        theme.pinned_username = 'text-xs font-semibold text-gray-400'

        # Update sticky pinned message styling
        theme.sticky_pinned_message = 'w-full rounded-xl px-4 py-3 bg-emerald-600 text-white shadow-lg border-l-4 border-emerald-400'

        # Update voice message player styles for pinned messages
        theme.pinned_voice_message_styles = {
            'containerBg': 'bg-emerald-800',
            'playButton': 'bg-emerald-800',
            'playButtonActive': 'bg-emerald-400',
            'playIconColor': 'text-white',
            'waveformActive': 'bg-white/80',
            'waveformInactive': 'bg-white/20',
            'durationTextColor': 'text-white/60'
        }

        # Make my voice messages match regular messages (zinc colors)
        theme.my_voice_message_styles = {
            'containerBg': 'bg-zinc-600/40',
            'playButton': 'bg-zinc-600/40',
            'playButtonActive': 'bg-zinc-500',
            'playIconColor': 'text-white',
            'waveformActive': 'bg-white/80',
            'waveformInactive': 'bg-white/20',
            'durationTextColor': 'text-white/60'
        }

        theme.save()
    except ChatTheme.DoesNotExist:
        pass  # Theme doesn't exist, skip


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0039_apply_message_styling_changes'),
    ]

    operations = [
        migrations.RunPython(update_pinned_message_styling, reverse_code=migrations.RunPython.noop),
    ]
