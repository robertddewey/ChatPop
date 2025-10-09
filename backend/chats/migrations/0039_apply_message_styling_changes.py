# Generated migration to update message styling
from django.db import migrations


def update_message_styling(apps, schema_editor):
    """Update dark-mode theme to match regular message styling"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    try:
        theme = ChatTheme.objects.get(id=1)  # dark-mode theme

        # Make my_message match regular_message (remove blue bg, remove green border)
        theme.my_message = 'max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-zinc-800'
        theme.regular_message = 'max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-zinc-800'

        # Set pinned_username to gray to match regular_username
        theme.pinned_username = 'text-xs font-semibold text-gray-400'

        theme.save()
    except ChatTheme.DoesNotExist:
        pass  # Theme doesn't exist, skip


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0038_update_message_styling_to_match_regular'),
    ]

    operations = [
        migrations.RunPython(update_message_styling, reverse_code=migrations.RunPython.noop),
    ]
