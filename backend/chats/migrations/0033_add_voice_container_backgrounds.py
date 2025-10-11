# Generated migration to add container backgrounds to voice message styles for Emerald Green theme

from django.db import migrations


def add_voice_container_backgrounds(apps, schema_editor):
    """Add containerBg property to voice message styles"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    try:
        theme = ChatTheme.objects.get(theme_id='dark-mode')

        # Add containerBg to my_voice_message_styles (emerald)
        if not theme.my_voice_message_styles:
            theme.my_voice_message_styles = {}
        theme.my_voice_message_styles['containerBg'] = 'bg-emerald-800/70'

        # Add containerBg to host_voice_message_styles (teal)
        if not theme.host_voice_message_styles:
            theme.host_voice_message_styles = {}
        theme.host_voice_message_styles['containerBg'] = 'bg-teal-800'

        # Add containerBg to pinned_voice_message_styles (teal for now, matches demo)
        if not theme.pinned_voice_message_styles:
            theme.pinned_voice_message_styles = {}
        theme.pinned_voice_message_styles['containerBg'] = 'bg-teal-800'

        # Add containerBg to regular voice_message_styles (zinc/gray)
        if not theme.voice_message_styles:
            theme.voice_message_styles = {}
        theme.voice_message_styles['containerBg'] = 'bg-zinc-600/40'

        theme.save()
        print(f"✓ Added voice message container backgrounds for Emerald Green theme")

    except ChatTheme.DoesNotExist:
        print("✗ dark-mode theme not found")


def remove_voice_container_backgrounds(apps, schema_editor):
    """Remove containerBg property from voice message styles"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    try:
        theme = ChatTheme.objects.get(theme_id='dark-mode')

        # Remove containerBg from all voice message styles
        if theme.my_voice_message_styles and 'containerBg' in theme.my_voice_message_styles:
            del theme.my_voice_message_styles['containerBg']
        if theme.host_voice_message_styles and 'containerBg' in theme.host_voice_message_styles:
            del theme.host_voice_message_styles['containerBg']
        if theme.pinned_voice_message_styles and 'containerBg' in theme.pinned_voice_message_styles:
            del theme.pinned_voice_message_styles['containerBg']
        if theme.voice_message_styles and 'containerBg' in theme.voice_message_styles:
            del theme.voice_message_styles['containerBg']

        theme.save()
        print(f"✓ Removed voice message container backgrounds")

    except ChatTheme.DoesNotExist:
        print("✗ dark-mode theme not found")


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0032_update_voice_message_colors_emerald_green'),
    ]

    operations = [
        migrations.RunPython(add_voice_container_backgrounds, remove_voice_container_backgrounds),
    ]
