# Generated manually

from django.db import migrations


def add_light_mode_theme(apps, schema_editor):
    """Create a light mode theme with rounded bubbles"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    ChatTheme.objects.create(
        theme_id='light-mode',
        name='Light Mode',
        is_dark_mode=False,
        theme_color_light='#ffffff',
        theme_color_dark='#f9fafb',

        # Layout & Container - Light backgrounds
        container='h-[100dvh] w-screen max-w-full overflow-x-hidden flex flex-col bg-gray-50',
        header='border-b border-gray-200 bg-white px-4 py-3 flex-shrink-0',
        header_title='text-lg font-bold text-gray-900',
        header_title_fade='bg-gradient-to-l from-white to-transparent',
        header_subtitle='text-sm text-gray-600',

        # Messages Area
        sticky_section='absolute top-0 left-0 right-0 z-20 border-b border-gray-200 bg-white/90 backdrop-blur-lg px-4 py-2 space-y-2 shadow-md',
        messages_area='absolute inset-0 overflow-y-auto px-4 py-4 space-y-2',
        messages_area_bg="bg-[url('/bg-pattern-light.svg')] bg-repeat bg-[length:800px_533px] opacity-[0.30]",

        # Host Messages - Blue/Indigo theme with rounded-xl
        host_message='max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-2.5 bg-gradient-to-br from-blue-500 to-indigo-600 font-medium transition-all duration-300 shadow-sm',
        sticky_host_message='w-full rounded-xl px-4 py-2.5 pr-[calc(2.5%+5rem-5px)] bg-gradient-to-br from-blue-500 to-indigo-600 font-medium transition-all duration-300 shadow-sm',
        host_text='text-white',
        host_message_fade='bg-gradient-to-l from-indigo-600 to-transparent',

        # Pinned Messages - Amber theme with rounded-xl
        pinned_message='max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-2.5 bg-gradient-to-br from-amber-400 to-orange-500 font-medium transition-all duration-300 shadow-sm',
        sticky_pinned_message='w-full rounded-xl px-4 py-2.5 pr-[calc(2.5%+5rem-5px)] bg-gradient-to-br from-amber-400 to-orange-500 font-medium transition-all duration-300 shadow-sm',
        pinned_text='text-white',
        pinned_message_fade='bg-gradient-to-l from-orange-500 to-transparent',

        # Regular Messages - Light gray with subtle border, rounded-xl
        regular_message='max-w-[calc(100%-2.5%-5rem+5px)] rounded-xl px-4 py-2.5 bg-white border border-gray-200 shadow-sm',
        regular_text='text-gray-900',

        # Filter Buttons
        filter_button_active='px-3 py-1.5 rounded-lg text-xs tracking-wider bg-blue-500 text-white border border-blue-600 shadow-sm',
        filter_button_inactive='px-3 py-1.5 rounded-lg text-xs tracking-wider bg-white text-gray-600 border border-gray-300 hover:bg-gray-50',

        # Input Area
        input_area='border-t border-gray-200 bg-white px-4 py-3 flex-shrink-0',
        input_field='flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-400 focus:border-blue-400 bg-white text-gray-900 placeholder-gray-400',
    )


def reverse_add_light_mode(apps, schema_editor):
    """Remove the light-mode theme"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')
    ChatTheme.objects.filter(theme_id='light-mode').delete()


class Migration(migrations.Migration):

    dependencies = [
        ("chats", "0015_remove_redundant_svg_fields"),
    ]

    operations = [
        migrations.RunPython(add_light_mode_theme, reverse_add_light_mode),
    ]
