# Generated migration to fix Emerald Green theme colors

from django.db import migrations


def fix_emerald_green_theme(apps, schema_editor):
    """Fix dark-mode theme to match Emerald Green demo specification exactly"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    try:
        theme = ChatTheme.objects.get(theme_id='dark-mode')

        # Host messages - teal-600 with WHITE text
        theme.host_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-teal-600 font-medium transition-all duration-300"
        theme.sticky_host_message = "w-full rounded px-3 py-2 pr-[calc(2.5%+5rem-5px)] bg-teal-600 font-medium transition-all duration-300"
        theme.host_text = "text-white"
        theme.host_message_fade = "bg-gradient-to-l from-teal-600 to-transparent"

        # Pinned messages - amber-700 with WHITE text and amber-400 border
        theme.pinned_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-amber-700 border-l-4 border-amber-400 font-medium transition-all duration-300"
        theme.sticky_pinned_message = "w-full rounded px-3 py-2 pr-[calc(2.5%+5rem-5px)] bg-amber-700 border-l-4 border-amber-400 font-medium transition-all duration-300"
        theme.pinned_text = "text-white"
        theme.pinned_message_fade = "bg-gradient-to-l from-amber-700 to-transparent"

        # My messages - emerald-600 (already correct)
        theme.my_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-emerald-600 shadow-md"
        theme.my_text = "text-white"

        # Regular messages with emerald border accent
        theme.regular_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-zinc-800 border-l-2 border-emerald-500/50"

        # Filter buttons - emerald
        theme.filter_button_active = "px-3 py-1.5 rounded text-xs tracking-wider bg-emerald-500 text-emerald-950 border border-emerald-400"

        # Input field focus ring - emerald
        theme.input_field = "flex-1 px-4 py-2 border border-zinc-700 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent bg-zinc-800 text-zinc-100 placeholder-zinc-500"

        # Background pattern - green tint (120deg hue rotation)
        theme.messages_area_bg = "bg-[url('/bg-pattern.svg')] bg-repeat bg-[length:800px_533px] opacity-[0.06] [filter:invert(1)_sepia(1)_hue-rotate(120deg)_saturate(3)]"

        # Voice message styles - updated to match demo
        theme.my_voice_message_styles = {
            "playButton": "bg-emerald-800/70",
            "playButtonActive": "bg-emerald-400",
            "playIconColor": "text-white",
            "waveformActive": "bg-white/80",
            "waveformInactive": "bg-white/20",
            "timeColor": "text-white/60"
        }

        theme.host_voice_message_styles = {
            "playButton": "bg-teal-800",
            "playButtonActive": "bg-teal-500",
            "playIconColor": "text-white",
            "waveformActive": "bg-white/80",
            "waveformInactive": "bg-white/20",
            "timeColor": "text-white/60"
        }

        theme.pinned_voice_message_styles = {
            "playButton": "bg-amber-800",
            "playButtonActive": "bg-amber-500",
            "playIconColor": "text-white",
            "waveformActive": "bg-white/80",
            "waveformInactive": "bg-white/20",
            "timeColor": "text-white/60"
        }

        theme.voice_message_styles = {
            "playButton": "bg-zinc-600/40",
            "playButtonActive": "bg-zinc-500",
            "playIconColor": "text-white",
            "waveformActive": "bg-white/80",
            "waveformInactive": "bg-white/20",
            "timeColor": "text-white/60"
        }

        theme.save()
        print(f"✓ Fixed dark-mode theme to match Emerald Green specification")

    except ChatTheme.DoesNotExist:
        print("✗ dark-mode theme not found")


def reverse_fix(apps, schema_editor):
    """Revert to previous state (migration 0028)"""
    ChatTheme = apps.get_model('chats', 'ChatTheme')

    try:
        theme = ChatTheme.objects.get(theme_id='dark-mode')

        # Revert to 0028 state
        theme.host_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-teal-500 font-medium transition-all duration-300"
        theme.sticky_host_message = "w-full rounded px-3 py-2 pr-[calc(2.5%+5rem-5px)] bg-teal-500 font-medium transition-all duration-300"
        theme.host_text = "text-teal-950"
        theme.host_message_fade = "bg-gradient-to-l from-teal-500 to-transparent"

        theme.pinned_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-amber-600 font-medium transition-all duration-300"
        theme.sticky_pinned_message = "w-full rounded px-3 py-2 pr-[calc(2.5%+5rem-5px)] bg-amber-600 font-medium transition-all duration-300"
        theme.pinned_text = "text-amber-950"
        theme.pinned_message_fade = "bg-gradient-to-l from-amber-600 to-transparent"

        theme.my_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-emerald-600 shadow-md"
        theme.my_text = "text-white"

        theme.regular_message = "max-w-[calc(100%-2.5%-5rem+5px)] rounded px-3 py-2 bg-zinc-800 border-l-2 border-emerald-500/50"

        theme.filter_button_active = "px-3 py-1.5 rounded text-xs tracking-wider bg-emerald-500 text-emerald-950 border border-emerald-400"

        theme.input_field = "flex-1 px-4 py-2 border border-zinc-700 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-transparent bg-zinc-800 text-zinc-100 placeholder-zinc-500"

        theme.messages_area_bg = "bg-[url('/bg-pattern.svg')] bg-repeat bg-[length:800px_533px] opacity-[0.06] [filter:invert(1)_sepia(1)_hue-rotate(120deg)_saturate(3)]"

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
        print(f"✓ Reverted dark-mode theme to previous state")

    except ChatTheme.DoesNotExist:
        print("✗ dark-mode theme not found")


class Migration(migrations.Migration):

    dependencies = [
        ('chats', '0028_update_dark_mode_to_emerald_green'),
    ]

    operations = [
        migrations.RunPython(fix_emerald_green_theme, reverse_fix),
    ]
