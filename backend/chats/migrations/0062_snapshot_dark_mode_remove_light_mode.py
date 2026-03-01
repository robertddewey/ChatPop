# Snapshot dark-mode theme to match production and remove light-mode theme

from django.db import migrations


def snapshot_themes(apps, schema_editor):
    """Snapshot dark-mode theme to current production values and delete light-mode."""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    # Delete light-mode theme
    ChatTheme.objects.filter(theme_id='light-mode').delete()

    # Update dark-mode to match current production database exactly
    try:
        theme = ChatTheme.objects.get(theme_id='dark-mode')
    except ChatTheme.DoesNotExist:
        return

    # Layout & Container
    theme.name = 'Dark Mode'
    theme.is_dark_mode = True
    theme.theme_color_light = '#18181b'
    theme.theme_color_dark = '#18181b'
    theme.container = 'h-[100dvh] w-screen max-w-full overflow-x-hidden flex flex-col bg-zinc-950'
    theme.header = 'border-b border-zinc-800 bg-zinc-900 px-4 py-3 flex-shrink-0'
    theme.header_title = 'text-lg font-bold text-zinc-100'
    theme.header_title_fade = 'bg-gradient-to-l from-zinc-900 to-transparent'
    theme.header_subtitle = 'text-sm text-zinc-400'

    # Messages Area
    theme.sticky_section = 'absolute top-0 left-0 right-0 z-20 border-b border-zinc-800 bg-zinc-900/90 px-4 py-2 space-y-2 shadow-lg'
    theme.messages_area = 'absolute inset-0 overflow-y-auto px-4 py-4 space-y-2'
    theme.messages_area_container = 'bg-zinc-900'
    theme.messages_area_bg = ''

    # Host Messages
    theme.host_message = 'max-w-[calc(100%-2.5%-5rem+5px)] rounded pb-1 font-medium transition-all duration-300'
    theme.sticky_host_message = 'w-full rounded-xl px-3 py-2 pr-[calc(2.5%+5rem-5px)] bg-blue-600 font-medium transition-all duration-300'
    theme.host_text = 'text-sm text-white'
    theme.host_message_fade = 'bg-gradient-to-l from-teal-600 to-transparent'

    # Pinned Messages
    theme.pinned_message = 'max-w-[calc(100%-2.5%-5rem+5px)] rounded pb-1'
    theme.sticky_pinned_message = 'w-full rounded-xl px-3 py-2 pr-[calc(2.5%+5rem-5px)] bg-purple-600 shadow-md'
    theme.pinned_text = 'text-sm text-white'
    theme.pinned_message_fade = 'bg-gradient-to-l from-amber-700 to-transparent'

    # Regular Messages
    theme.regular_message = 'max-w-[calc(100%-2.5%-5rem+5px)] rounded pb-1'
    theme.regular_text = 'text-sm text-white'

    # My Messages
    theme.my_message = 'max-w-[calc(100%-2.5%-5rem+5px)] rounded pb-1'
    theme.my_text = 'text-sm text-white'

    # Voice Message Styles (unified white-on-dark)
    voice_style = {
        "playButton": "bg-white hover:bg-white/90",
        "containerBg": "bg-white/10",
        "playIconColor": "text-zinc-800",
        "waveformActive": "bg-white",
        "waveformInactive": "bg-white/40",
        "durationTextColor": "text-white/80"
    }
    theme.voice_message_styles = voice_style
    theme.my_voice_message_styles = voice_style
    theme.host_voice_message_styles = voice_style
    theme.pinned_voice_message_styles = voice_style

    # Filter Buttons
    theme.filter_button_active = 'px-3 py-1.5 rounded text-xs tracking-wider bg-emerald-500 text-emerald-950 border border-emerald-400'
    theme.filter_button_inactive = 'px-3 py-1.5 rounded text-xs tracking-wider bg-zinc-800 text-zinc-400 border border-zinc-700'

    # Input Area
    theme.input_area = 'border-t border-zinc-800 bg-zinc-900 px-4 py-3 flex-shrink-0'
    theme.input_field = 'flex-1 px-4 py-2 border border-zinc-700 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent bg-zinc-800 text-zinc-100 placeholder-zinc-500'

    # Icon Colors
    theme.pin_icon_color = 'text-purple-400'
    theme.crown_icon_color = 'text-amber-400'
    theme.badge_icon_color = 'text-emerald-400'
    theme.reply_icon_color = 'text-emerald-300'

    # Reaction Highlights
    theme.reaction_highlight_bg = 'bg-purple-500/20'
    theme.reaction_highlight_border = 'border border-purple-500/50'
    theme.reaction_highlight_text = 'text-zinc-200'

    # Avatar
    theme.avatar_spacing = 'mr-3'

    # Usernames
    theme.my_username = 'text-sm font-bold text-red-500'
    theme.regular_username = 'text-sm font-bold text-white'
    theme.host_username = 'text-sm font-bold text-amber-400'
    theme.my_host_username = 'text-sm font-semibold text-red-500'
    theme.pinned_username = 'text-sm font-bold text-purple-400'
    theme.sticky_host_username = 'text-xs font-semibold text-amber-400'
    theme.sticky_pinned_username = 'text-xs font-semibold text-purple-400'

    # Timestamps
    theme.my_timestamp = 'text-xs text-white opacity-60'
    theme.regular_timestamp = 'text-xs text-white opacity-60'
    theme.host_timestamp = 'text-xs opacity-60'
    theme.pinned_timestamp = 'text-xs opacity-60'

    # Reply Preview
    theme.reply_preview_container = 'flex items-center justify-between px-4 py-2 bg-gray-100 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700'
    theme.reply_preview_icon = 'w-4 h-4 flex-shrink-0 text-blue-500'
    theme.reply_preview_username = 'text-xs font-semibold text-gray-700 dark:text-gray-300'
    theme.reply_preview_content = 'text-xs text-gray-600 dark:text-gray-400 truncate'
    theme.reply_preview_close_button = 'p-1 hover:bg-gray-200 dark:hover:bg-gray-700 rounded'
    theme.reply_preview_close_icon = 'w-4 h-4 text-gray-500'

    theme.save()


def reverse_snapshot(apps, schema_editor):
    """Recreate light-mode theme (reverse operation)."""
    ChatTheme = apps.get_model('chats', 'ChatTheme')
    if not ChatTheme.objects.filter(theme_id='light-mode').exists():
        ChatTheme.objects.create(
            theme_id='light-mode',
            name='Light Mode',
            is_dark_mode=False,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0061_multi_emoji_reactions'),
    ]

    operations = [
        migrations.RunPython(snapshot_themes, reverse_snapshot),
    ]
