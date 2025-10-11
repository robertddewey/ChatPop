# Generated migration to set Emerald Green icon colors

from django.db import migrations


def set_icon_colors(apps, schema_editor):
    """Set icon colors for dark-mode theme to match Emerald Green specification"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    try:
        theme = ChatTheme.objects.get(theme_id='dark-mode')

        # Set icon colors from dark-theme-demo Emerald Green specification
        theme.pin_icon_color = "text-amber-400"
        theme.crown_icon_color = "text-teal-400"
        theme.badge_icon_color = "text-emerald-400"
        theme.reply_icon_color = "text-emerald-300"

        theme.save()
        print(f"✓ Set Emerald Green icon colors for dark-mode theme")

    except ChatTheme.DoesNotExist:
        print("✗ dark-mode theme not found")


def reverse_icon_colors(apps, schema_editor):
    """Revert to default icon colors"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    try:
        theme = ChatTheme.objects.get(theme_id='dark-mode')

        # Revert to default colors
        theme.pin_icon_color = "text-yellow-400"
        theme.crown_icon_color = "text-yellow-400"
        theme.badge_icon_color = "text-blue-400"
        theme.reply_icon_color = "text-cyan-400"

        theme.save()
        print(f"✓ Reverted to default icon colors")

    except ChatTheme.DoesNotExist:
        print("✗ dark-mode theme not found")


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0030_add_icon_color_fields'),
    ]

    operations = [
        migrations.RunPython(set_icon_colors, reverse_icon_colors),
    ]
