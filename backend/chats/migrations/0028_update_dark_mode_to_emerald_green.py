# Generated migration to update dark-mode theme to Emerald Green

from django.db import migrations


def update_dark_mode_theme(apps, schema_editor):
    """Update dark-mode theme to Emerald Green color scheme"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    try:
        theme = ChatTheme.objects.get(theme_id='dark-mode')

        # Update host messages to teal/emerald
        theme.host_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-teal-500 font-medium transition-all duration-300"
        theme.sticky_host_message = "w-full rounded px-3 py-2 pr-[calc(2.5%+5rem-5px)] bg-teal-500 font-medium transition-all duration-300"
        theme.host_text = "text-teal-950"
        theme.host_message_fade = "bg-gradient-to-l from-teal-500 to-transparent"

        # Update pinned messages to amber/gold
        theme.pinned_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-amber-600 font-medium transition-all duration-300"
        theme.sticky_pinned_message = "w-full rounded px-3 py-2 pr-[calc(2.5%+5rem-5px)] bg-amber-600 font-medium transition-all duration-300"
        theme.pinned_text = "text-amber-950"
        theme.pinned_message_fade = "bg-gradient-to-l from-amber-600 to-transparent"

        # Update regular messages with emerald accent border
        theme.regular_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-zinc-800 border-l-2 border-emerald-500/50"

        # Update my messages to emerald green
        theme.my_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-emerald-600 shadow-md"

        # Update filter buttons to emerald
        theme.filter_button_active = "px-3 py-1.5 rounded text-xs tracking-wider bg-emerald-500 text-emerald-950 border border-emerald-400"

        # Update input field focus ring to emerald
        theme.input_field = "flex-1 px-4 py-2 border border-zinc-700 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent bg-zinc-800 text-zinc-100 placeholder-zinc-500"

        # Update background pattern to emerald/green tint (hue-rotate ~120deg for green)
        theme.messages_area_bg = "bg-[url('/bg-pattern.svg')] bg-repeat bg-[length:800px_533px] opacity-[0.06] [filter:invert(1)_sepia(1)_hue-rotate(120deg)_saturate(3)]"

        # Update voice message styles
        theme.my_voice_message_styles = {
            "playButton": "bg-emerald-700",
            "playIconColor": "text-white",
            "waveformActive": "bg-white/80",
            "waveformInactive": "bg-white/20"
        }

        theme.host_voice_message_styles = {
            "playButton": "bg-teal-700",
            "playIconColor": "text-white",
            "waveformActive": "bg-teal-950/80",
            "waveformInactive": "bg-teal-950/20"
        }

        theme.pinned_voice_message_styles = {
            "playButton": "bg-amber-800",
            "playIconColor": "text-white",
            "waveformActive": "bg-amber-950/80",
            "waveformInactive": "bg-amber-950/20"
        }

        theme.save()
        print(f"✓ Updated dark-mode theme to Emerald Green color scheme")

    except ChatTheme.DoesNotExist:
        print("✗ dark-mode theme not found")


def reverse_update(apps, schema_editor):
    """Revert to previous cyan/yellow color scheme"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    try:
        theme = ChatTheme.objects.get(theme_id='dark-mode')

        # Revert host messages to cyan
        theme.host_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-cyan-400 font-medium transition-all duration-300"
        theme.sticky_host_message = "w-full rounded px-3 py-2 pr-[calc(2.5%+5rem-5px)] bg-cyan-400 font-medium transition-all duration-300"
        theme.host_text = "text-cyan-950"
        theme.host_message_fade = "bg-gradient-to-l from-cyan-400 to-transparent"

        # Revert pinned messages to yellow
        theme.pinned_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-yellow-400 font-medium transition-all duration-300"
        theme.sticky_pinned_message = "w-full rounded px-3 py-2 pr-[calc(2.5%+5rem-5px)] bg-yellow-400 font-medium transition-all duration-300"
        theme.pinned_text = "text-yellow-950"
        theme.pinned_message_fade = "bg-gradient-to-l from-yellow-400 to-transparent"

        # Revert regular messages with cyan accent border
        theme.regular_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-zinc-800 border-l-2 border-cyan-500/50"

        # Revert my messages to blue
        theme.my_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-blue-500 shadow-md"

        # Revert filter buttons to cyan
        theme.filter_button_active = "px-3 py-1.5 rounded text-xs tracking-wider bg-cyan-400 text-cyan-950 border border-cyan-300"

        # Revert input field focus ring to cyan
        theme.input_field = "flex-1 px-4 py-2 border border-zinc-700 rounded-lg focus:ring-2 focus:ring-cyan-400 focus:border-transparent bg-zinc-800 text-zinc-100 placeholder-zinc-500"

        # Revert background pattern to cyan tint
        theme.messages_area_bg = "bg-[url('/bg-pattern.svg')] bg-repeat bg-[length:800px_533px] opacity-[0.06] [filter:invert(1)_sepia(1)_hue-rotate(180deg)_saturate(3)]"

        # Revert voice message styles
        theme.my_voice_message_styles = {}
        theme.host_voice_message_styles = {}
        theme.pinned_voice_message_styles = {}

        theme.save()
        print(f"✓ Reverted dark-mode theme to previous color scheme")

    except ChatTheme.DoesNotExist:
        print("✗ dark-mode theme not found")


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0027_adjust_message_padding'),
    ]

    operations = [
        migrations.RunPython(update_dark_mode_theme, reverse_update),
    ]
