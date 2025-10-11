# Generated migration - Update dark-mode theme to Teal Vibes color scheme

from django.db import migrations


def update_dark_mode_to_teal_vibes(apps, schema_editor):
    """Update dark-mode theme with Teal Vibes color scheme"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    try:
        theme = ChatTheme.objects.get(theme_id='dark-mode')

        # Update my messages (teal)
        theme.my_message = 'max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-3 bg-teal-600 text-white shadow-md'
        theme.my_text = 'text-white'

        # Update regular messages (slate)
        theme.regular_message = 'max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-3 bg-slate-700 text-white shadow-md'
        theme.regular_text = 'text-white'

        # Update pinned messages (orange with left border)
        theme.pinned_message = 'max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-3 bg-orange-600/20 border-l-4 border-orange-500 text-white shadow-md'
        theme.pinned_text = 'text-white'
        theme.sticky_pinned_message = 'rounded-xl px-4 py-3 bg-orange-600/20 border-l-4 border-orange-500 text-white shadow-md'

        # Update host messages (deep purple)
        theme.host_message = 'max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-3 bg-purple-700 text-white shadow-md'
        theme.host_text = 'text-white'
        theme.sticky_host_message = 'rounded-xl px-4 py-3 bg-purple-700 text-white shadow-md'

        # Update voice message styles
        theme.my_voice_message_styles = {
            'playButton': 'bg-teal-800/70',
            'playIconColor': 'text-white',
            'playButtonActive': 'bg-teal-400',
            'waveformActive': 'bg-white/60',
            'waveformInactive': 'bg-white/20'
        }

        theme.voice_message_styles = {
            'playButton': 'bg-slate-600/40',
            'playIconColor': 'text-white',
            'playButtonActive': 'bg-slate-500',
            'waveformActive': 'bg-white/60',
            'waveformInactive': 'bg-white/20'
        }

        theme.pinned_voice_message_styles = {
            'playButton': 'bg-orange-700/40',
            'playIconColor': 'text-white',
            'playButtonActive': 'bg-orange-500',
            'waveformActive': 'bg-white/60',
            'waveformInactive': 'bg-white/20'
        }

        theme.host_voice_message_styles = {
            'playButton': 'bg-purple-700/40',
            'playIconColor': 'text-white',
            'playButtonActive': 'bg-purple-500',
            'waveformActive': 'bg-white/60',
            'waveformInactive': 'bg-white/20'
        }

        theme.save()
        print("✓ Updated dark-mode theme to Teal Vibes color scheme")
        print("  - My messages: teal-600")
        print("  - Other messages: slate-700")
        print("  - Pinned messages: orange-600/20 with border-orange-500")
        print("  - Host messages: purple-700")

    except ChatTheme.DoesNotExist:
        print("⚠ dark-mode theme not found, skipping")


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0024_merge_20251009_1616'),
    ]

    operations = [
        migrations.RunPython(update_dark_mode_to_teal_vibes, reverse_code=migrations.RunPython.noop),
    ]
