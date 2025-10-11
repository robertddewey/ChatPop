# Generated migration - Adjust message padding to 11px using arbitrary value

from django.db import migrations


def adjust_message_padding(apps, schema_editor):
    """Use py-[11px] for exact 11px padding (between py-2.5=10px and py-3=12px)"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    try:
        theme = ChatTheme.objects.get(theme_id='dark-mode')

        # Update all messages to use py-[11px] for exact 11px padding
        theme.my_message = 'max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-[11px] bg-teal-600 text-white shadow-md'
        theme.regular_message = 'max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-[11px] bg-slate-700 text-white shadow-md'
        theme.pinned_message = 'max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-[11px] bg-orange-600 text-white shadow-md'
        theme.sticky_pinned_message = 'rounded-xl px-4 py-[11px] bg-orange-600 text-white shadow-md'
        theme.host_message = 'max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-[11px] bg-purple-700 text-white shadow-md'
        theme.sticky_host_message = 'rounded-xl px-4 py-[11px] bg-purple-700 text-white shadow-md'

        theme.save()
        print("✓ Adjusted message padding to py-[11px] (11px exact)")

    except ChatTheme.DoesNotExist:
        print("⚠ dark-mode theme not found, skipping")


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0026_fix_teal_vibes_theme'),
    ]

    operations = [
        migrations.RunPython(adjust_message_padding, reverse_code=migrations.RunPython.noop),
    ]
