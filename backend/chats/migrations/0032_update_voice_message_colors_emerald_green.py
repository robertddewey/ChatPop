# Generated migration to update voice message colors for Emerald Green theme

from django.db import migrations


def update_voice_colors(apps, schema_editor):
    """Update voice message colors to match Emerald Green theme"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    try:
        theme = ChatTheme.objects.get(theme_id='dark-mode')

        # Update pinned voice message to use teal/emerald instead of amber
        theme.pinned_voice_message_styles = {
            'timeColor': 'text-white/60',
            'playButton': 'bg-teal-800',
            'playIconColor': 'text-white',
            'waveformActive': 'bg-white/80',
            'playButtonActive': 'bg-teal-500',
            'waveformInactive': 'bg-white/20',
        }

        theme.save()
        print(f"✓ Updated voice message colors for Emerald Green theme")

    except ChatTheme.DoesNotExist:
        print("✗ dark-mode theme not found")


def reverse_voice_colors(apps, schema_editor):
    """Revert to original voice message colors"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    try:
        theme = ChatTheme.objects.get(theme_id='dark-mode')

        # Revert to amber
        theme.pinned_voice_message_styles = {
            'timeColor': 'text-white/60',
            'playButton': 'bg-amber-800',
            'playIconColor': 'text-white',
            'waveformActive': 'bg-white/80',
            'playButtonActive': 'bg-amber-500',
            'waveformInactive': 'bg-white/20',
        }

        theme.save()
        print(f"✓ Reverted to original voice message colors")

    except ChatTheme.DoesNotExist:
        print("✗ dark-mode theme not found")


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0031_set_emerald_green_icon_colors'),
    ]

    operations = [
        migrations.RunPython(update_voice_colors, reverse_voice_colors),
    ]
