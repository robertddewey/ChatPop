"""
Data migration: populate the 6 new JSON style fields for the existing dark-mode theme.
These values match what was previously hardcoded in the frontend components.
"""

from django.db import migrations


def populate_component_styles(apps, schema_editor):
    ChatTheme = apps.get_model("chats", "ChatTheme")

    for theme in ChatTheme.objects.filter(name="Dark Mode"):
        theme.modal_styles = {
            "overlay": "bg-black/60 backdrop-blur-md",
            "container": "bg-zinc-900",
            "border": "border border-zinc-700",
            "dragHandle": "bg-gray-600",
            "messagePreview": "bg-zinc-800 border border-zinc-600 rounded-lg shadow-xl",
            "actionButton": "bg-zinc-700 hover:bg-zinc-600 active:bg-zinc-500 text-zinc-50 border border-zinc-500",
            "actionIcon": "text-cyan-400",
            "divider": "border-zinc-700/50",
            "usernameText": "text-gray-300",
            "title": "text-zinc-50",
            "body": "text-zinc-400",
            "primaryButton": "bg-[#404eed] hover:bg-[#3640d9] text-white",
            "secondaryButton": "bg-zinc-700 hover:bg-zinc-600 text-zinc-50",
            "input": "bg-zinc-800 border border-zinc-600 text-zinc-50 placeholder-zinc-400 focus:ring-2 focus:ring-cyan-400",
            "closeButton": "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800",
            "error": "bg-red-900/20 border border-red-800 text-red-400",
        }

        theme.emoji_picker_styles = {
            "selectedBg": "bg-purple-500/30",
            "selectedRing": "ring-2 ring-purple-500/60",
            "unselectedBg": "bg-zinc-800 hover:bg-zinc-700",
        }

        theme.gift_styles = {
            "cardBgForMe": "bg-purple-950/50 border border-purple-500/50",
            "cardBg": "bg-zinc-800/80 border border-zinc-700",
            "emojiContainer": "bg-zinc-700/80",
            "nameText": "text-white",
            "priceBadge": "bg-cyan-900/50 text-cyan-400",
            "recipientTextForMe": "text-purple-400",
            "recipientText": "text-zinc-300",
        }

        theme.input_styles = {
            "sendButton": "bg-gradient-to-r from-purple-600 to-blue-600 text-white hover:from-purple-700 hover:to-blue-700",
            "collapseButton": "bg-zinc-700 text-gray-400 hover:bg-zinc-600",
            "disabledBg": "bg-zinc-800/60 border border-zinc-700/50",
            "disabledText": "text-zinc-500",
            "textFadeGradient": "rgb(39, 39, 42)",
            "avatarFallbackBg": "bg-zinc-700",
            "youPill": "bg-white/10 text-zinc-400",
        }

        theme.video_player_styles = {
            "overlay": "bg-black/30",
            "playButtonBg": "bg-white/90",
            "playIcon": "text-gray-800",
            "spinner": "border-gray-600",
            "hoverOverlay": "bg-black/20",
            "pauseIcon": "text-white",
            "durationBadge": "bg-black/70 text-white",
            "progressBg": "bg-black/30",
            "progressFill": "bg-white",
        }

        theme.ui_styles = {
            "emptyStateText": "text-zinc-600",
            "emptyStateSubtext": "text-zinc-500",
            "avatarConnector": "bg-zinc-600/30",
            "avatarFallbackBg": "bg-zinc-700",
            "badgeIconBg": "#18181b",
            "loadingBg": "bg-zinc-900",
            "loadingCard": "bg-zinc-800 text-zinc-200",
            "pinAmountText": "text-zinc-300",
        }

        theme.save()


def clear_component_styles(apps, schema_editor):
    ChatTheme = apps.get_model("chats", "ChatTheme")
    ChatTheme.objects.filter(name="Dark Mode").update(
        modal_styles={},
        emoji_picker_styles={},
        gift_styles={},
        input_styles={},
        video_player_styles={},
        ui_styles={},
    )


class Migration(migrations.Migration):

    dependencies = [
        ("chats", "0068_remove_avatar_style_add_component_style_fields"),
    ]

    operations = [
        migrations.RunPython(populate_component_styles, clear_component_styles),
    ]
