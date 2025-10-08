from django.db import migrations


def update_light_mode_colors(apps, schema_editor):
    """Update light-mode theme with user-specified colors"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    try:
        theme = ChatTheme.objects.get(theme_id='light-mode')

        # Regular messages (other users): light gray background, black text
        theme.regular_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-2.5 bg-gray-100 shadow-sm"
        theme.regular_text = "text-gray-900"

        # Host messages: red background, white text (both regular and sticky)
        theme.host_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-2.5 bg-red-500 font-medium transition-all duration-300 shadow-md"
        theme.sticky_host_message = "w-full rounded-xl px-4 py-2.5 pr-[calc(2.5%+5rem-5px)] bg-red-500 font-medium transition-all duration-300 shadow-md"
        theme.host_text = "text-white"
        theme.host_message_fade = "bg-gradient-to-l from-red-500 to-transparent"

        # Pinned messages: purple background, white text (both regular and sticky)
        theme.pinned_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-2.5 bg-purple-600 font-medium transition-all duration-300 shadow-md"
        theme.sticky_pinned_message = "w-full rounded-xl px-4 py-2.5 pr-[calc(2.5%+5rem-5px)] bg-purple-600 font-medium transition-all duration-300 shadow-md"
        theme.pinned_text = "text-white"
        theme.pinned_message_fade = "bg-gradient-to-l from-purple-600 to-transparent"

        theme.save()
        print(f'Updated light-mode theme colors')

    except ChatTheme.DoesNotExist:
        print('light-mode theme not found, skipping color update')


def reverse_colors(apps, schema_editor):
    """Revert to original light-mode colors"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    try:
        theme = ChatTheme.objects.get(theme_id='light-mode')

        # Revert to original colors
        theme.regular_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-2.5 bg-white border border-gray-200 shadow-sm"
        theme.regular_text = "text-gray-900"

        theme.host_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-2.5 bg-gradient-to-br from-blue-500 to-indigo-600 font-medium transition-all duration-300 shadow-md"
        theme.sticky_host_message = "w-full rounded-xl px-4 py-2.5 pr-[calc(2.5%+5rem-5px)] bg-gradient-to-br from-blue-500 to-indigo-600 font-medium transition-all duration-300 shadow-md"
        theme.host_text = "text-white"
        theme.host_message_fade = "bg-gradient-to-l from-indigo-600 to-transparent"

        theme.pinned_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-2.5 bg-gradient-to-br from-amber-400 to-orange-500 font-medium transition-all duration-300 shadow-md"
        theme.sticky_pinned_message = "w-full rounded-xl px-4 py-2.5 pr-[calc(2.5%+5rem-5px)] bg-gradient-to-br from-amber-400 to-orange-500 font-medium transition-all duration-300 shadow-md"
        theme.pinned_text = "text-white"
        theme.pinned_message_fade = "bg-gradient-to-l from-orange-500 to-transparent"

        theme.save()

    except ChatTheme.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0017_add_messages_area_container'),
    ]

    operations = [
        migrations.RunPython(update_light_mode_colors, reverse_colors),
    ]
