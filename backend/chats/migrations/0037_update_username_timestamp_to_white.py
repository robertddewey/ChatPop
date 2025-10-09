# Generated migration to update username and timestamp styling to white

from django.db import migrations


def update_username_timestamp_styling(apps, schema_editor):
    """Update all existing themes to use white username and timestamp text"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    for theme in ChatTheme.objects.all():
        # Update usernames to white if they have the old gray default
        if theme.my_username == 'text-xs font-semibold text-gray-400':
            theme.my_username = 'text-xs font-semibold text-white'
        if theme.regular_username == 'text-xs font-semibold text-gray-400':
            theme.regular_username = 'text-xs font-semibold text-white'

        # Update timestamps to include white text
        if theme.my_timestamp == 'text-xs opacity-60':
            theme.my_timestamp = 'text-xs text-white opacity-60'
        if theme.regular_timestamp == 'text-xs opacity-60':
            theme.regular_timestamp = 'text-xs text-white opacity-60'

        theme.save()


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0036_add_username_and_timestamp_styling'),
    ]

    operations = [
        migrations.RunPython(update_username_timestamp_styling, reverse_code=migrations.RunPython.noop),
    ]
