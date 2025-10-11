# Generated migration to fix pinned voice message colors to amber (gold)

from django.db import migrations


def fix_pinned_voice_colors(apps, schema_editor):
    """Update pinned voice message colors from teal to amber"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    try:
        theme = ChatTheme.objects.get(theme_id='dark-mode')

        # Update pinned voice message styles to use amber instead of teal
        theme.pinned_voice_message_styles = {
            'timeColor': 'text-white/60',
            'playButton': 'bg-amber-800',
            'playIconColor': 'text-white',
            'waveformActive': 'bg-white/80',
            'playButtonActive': 'bg-amber-500',
            'waveformInactive': 'bg-white/20',
            'containerBg': 'bg-amber-800',
        }

        theme.save()
        print(f"✓ Fixed pinned voice message colors to amber for Emerald Green theme")

    except ChatTheme.DoesNotExist:
        print("✗ dark-mode theme not found")


def revert_pinned_voice_colors(apps, schema_editor):
    """Revert pinned voice message colors back to teal"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    try:
        theme = ChatTheme.objects.get(theme_id='dark-mode')

        # Revert to teal
        theme.pinned_voice_message_styles = {
            'timeColor': 'text-white/60',
            'playButton': 'bg-teal-800',
            'playIconColor': 'text-white',
            'waveformActive': 'bg-white/80',
            'playButtonActive': 'bg-teal-500',
            'waveformInactive': 'bg-white/20',
            'containerBg': 'bg-teal-800',
        }

        theme.save()
        print(f"✓ Reverted pinned voice message colors to teal")

    except ChatTheme.DoesNotExist:
        print("✗ dark-mode theme not found")


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0033_add_voice_container_backgrounds'),
    ]

    operations = [
        migrations.RunPython(fix_pinned_voice_colors, revert_pinned_voice_colors),
    ]
