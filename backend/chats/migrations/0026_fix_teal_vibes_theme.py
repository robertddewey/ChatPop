# Generated migration - Fix Teal Vibes theme issues

from django.db import migrations


def fix_teal_vibes_theme(apps, schema_editor):
    """Fix Teal Vibes theme: solid pinned messages, reduced height"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    try:
        theme = ChatTheme.objects.get(theme_id='dark-mode')

        # Fix message heights (py-3 → py-2.5) and pinned messages (solid bg)
        theme.my_message = 'max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-2.5 bg-teal-600 text-white shadow-md'
        theme.regular_message = 'max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-2.5 bg-slate-700 text-white shadow-md'
        theme.pinned_message = 'max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-2.5 bg-orange-600 text-white shadow-md'
        theme.sticky_pinned_message = 'rounded-xl px-4 py-2.5 bg-orange-600 text-white shadow-md'
        theme.host_message = 'max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-2.5 bg-purple-700 text-white shadow-md'
        theme.sticky_host_message = 'rounded-xl px-4 py-2.5 bg-purple-700 text-white shadow-md'

        theme.save()
        print("✓ Fixed Teal Vibes theme:")
        print("  - Changed pinned message from transparent (bg-orange-600/20) to solid (bg-orange-600)")
        print("  - Reduced message height from py-3 to py-2.5")

    except ChatTheme.DoesNotExist:
        print("⚠ dark-mode theme not found, skipping")


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0025_update_dark_mode_to_teal_vibes'),
    ]

    operations = [
        migrations.RunPython(fix_teal_vibes_theme, reverse_code=migrations.RunPython.noop),
    ]
