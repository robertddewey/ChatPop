# Generated migration

from django.db import migrations


def set_dark_mode_my_message_blue(apps, schema_editor):
    """Set dark-mode theme to use blue for my_message"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    try:
        theme = ChatTheme.objects.get(theme_id='dark-mode')
        theme.my_message = 'max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-3 bg-blue-600 text-white shadow-md'
        theme.my_text = 'text-white'
        theme.save()
        print(f"✓ Updated dark-mode theme: my_message = blue (bg-blue-600)")
    except ChatTheme.DoesNotExist:
        print("⚠ dark-mode theme not found, skipping")


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0020_set_light_mode_my_message_color'),
    ]

    operations = [
        migrations.RunPython(set_dark_mode_my_message_blue, reverse_code=migrations.RunPython.noop),
    ]
