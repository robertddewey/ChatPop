from django.db import migrations


def set_light_mode_my_message_color(apps, schema_editor):
    """Set Facebook blue color for light-mode 'my messages'"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    try:
        theme = ChatTheme.objects.get(theme_id='light-mode')
        # Facebook blue (#1877F2 / Tailwind's blue-500 is close enough)
        theme.my_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-2.5 bg-blue-500 shadow-md"
        theme.my_text = "text-white"
        theme.save()
        print('Updated light-mode my_message to Facebook blue')
    except ChatTheme.DoesNotExist:
        print('light-mode theme not found')


def reverse_my_message_color(apps, schema_editor):
    """Revert to default"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')
    try:
        theme = ChatTheme.objects.get(theme_id='light-mode')
        theme.my_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-2.5 bg-blue-500 shadow-md"
        theme.my_text = "text-white"
        theme.save()
    except ChatTheme.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0019_add_my_message_styles'),
    ]

    operations = [
        migrations.RunPython(set_light_mode_my_message_color, reverse_my_message_color),
    ]
