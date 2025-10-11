# Generated migration to rename timeColor to durationTextColor in all voice message styles

from django.db import migrations


def rename_timecolor_to_durationtextcolor(apps, schema_editor):
    """Rename timeColor to durationTextColor for consistency with component props"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    for theme in ChatTheme.objects.all():
        updated = False

        # Update voice_message_styles
        if theme.voice_message_styles and 'timeColor' in theme.voice_message_styles:
            theme.voice_message_styles['durationTextColor'] = theme.voice_message_styles.pop('timeColor')
            updated = True

        # Update my_voice_message_styles
        if theme.my_voice_message_styles and 'timeColor' in theme.my_voice_message_styles:
            theme.my_voice_message_styles['durationTextColor'] = theme.my_voice_message_styles.pop('timeColor')
            updated = True

        # Update host_voice_message_styles
        if theme.host_voice_message_styles and 'timeColor' in theme.host_voice_message_styles:
            theme.host_voice_message_styles['durationTextColor'] = theme.host_voice_message_styles.pop('timeColor')
            updated = True

        # Update pinned_voice_message_styles
        if theme.pinned_voice_message_styles and 'timeColor' in theme.pinned_voice_message_styles:
            theme.pinned_voice_message_styles['durationTextColor'] = theme.pinned_voice_message_styles.pop('timeColor')
            updated = True

        if updated:
            theme.save()
            print(f"✓ Renamed timeColor to durationTextColor for theme: {theme.name}")


def rename_durationtextcolor_to_timecolor(apps, schema_editor):
    """Revert durationTextColor back to timeColor"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    for theme in ChatTheme.objects.all():
        updated = False

        # Revert voice_message_styles
        if theme.voice_message_styles and 'durationTextColor' in theme.voice_message_styles:
            theme.voice_message_styles['timeColor'] = theme.voice_message_styles.pop('durationTextColor')
            updated = True

        # Revert my_voice_message_styles
        if theme.my_voice_message_styles and 'durationTextColor' in theme.my_voice_message_styles:
            theme.my_voice_message_styles['timeColor'] = theme.my_voice_message_styles.pop('durationTextColor')
            updated = True

        # Revert host_voice_message_styles
        if theme.host_voice_message_styles and 'durationTextColor' in theme.host_voice_message_styles:
            theme.host_voice_message_styles['timeColor'] = theme.host_voice_message_styles.pop('durationTextColor')
            updated = True

        # Revert pinned_voice_message_styles
        if theme.pinned_voice_message_styles and 'durationTextColor' in theme.pinned_voice_message_styles:
            theme.pinned_voice_message_styles['timeColor'] = theme.pinned_voice_message_styles.pop('durationTextColor')
            updated = True

        if updated:
            theme.save()
            print(f"✓ Reverted durationTextColor to timeColor for theme: {theme.name}")


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0034_fix_pinned_voice_colors_to_amber'),
    ]

    operations = [
        migrations.RunPython(rename_timecolor_to_durationtextcolor, rename_durationtextcolor_to_timecolor),
    ]
