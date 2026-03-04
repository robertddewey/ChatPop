"""Fix dark-mode reply preview to use explicit dark colors instead of dark: prefixes.

iOS Safari in light system mode ignores dark: prefixes, causing white backgrounds
in the reply preview bar even though the chat theme is dark.
"""

from django.db import migrations


def fix_reply_preview(apps, schema_editor):
    ChatTheme = apps.get_model('chats', 'ChatTheme')
    try:
        theme = ChatTheme.objects.get(name='Dark Mode')
    except ChatTheme.DoesNotExist:
        return

    theme.reply_preview_container = 'flex items-center justify-between px-4 py-2 bg-zinc-800 border-b border-zinc-700'
    theme.reply_preview_icon = 'w-4 h-4 flex-shrink-0 text-cyan-400'
    theme.reply_preview_username = 'text-xs font-semibold text-zinc-300'
    theme.reply_preview_content = 'text-xs text-zinc-400 truncate'
    theme.reply_preview_close_button = 'p-1 hover:bg-zinc-700 rounded'
    theme.reply_preview_close_icon = 'w-4 h-4 text-zinc-500'
    theme.save()


def reverse_fix(apps, schema_editor):
    ChatTheme = apps.get_model('chats', 'ChatTheme')
    try:
        theme = ChatTheme.objects.get(name='Dark Mode')
    except ChatTheme.DoesNotExist:
        return

    theme.reply_preview_container = 'flex items-center justify-between px-4 py-2 bg-gray-100 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700'
    theme.reply_preview_icon = 'w-4 h-4 flex-shrink-0 text-blue-500'
    theme.reply_preview_username = 'text-xs font-semibold text-gray-700 dark:text-gray-300'
    theme.reply_preview_content = 'text-xs text-gray-600 dark:text-gray-400 truncate'
    theme.reply_preview_close_button = 'p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded'
    theme.reply_preview_close_icon = 'w-4 h-4 text-gray-500'
    theme.save()


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0064_add_is_gift_acknowledged_to_message'),
    ]

    operations = [
        migrations.RunPython(fix_reply_preview, reverse_fix),
    ]
