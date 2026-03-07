"""
Data migration: fix 3 out-of-sync theme fields and add new JSON keys.

Fields changed via direct DB edits with no migration:
- sticky_host_message: bg-blue-600 -> bg-zinc-800
- sticky_pinned_message: bg-purple-600 -> bg-purple-900 border border-purple-500/40
- badge_icon_color: text-emerald-400 -> text-blue-500

New JSON keys added to modal_styles, gift_styles, and ui_styles for
replacing hardcoded themeIsDarkMode ternaries in frontend components.
"""

from django.db import migrations


def fix_theme_fields(apps, schema_editor):
    ChatTheme = apps.get_model("chats", "ChatTheme")

    for theme in ChatTheme.objects.filter(theme_id="dark-mode"):
        # Fix 3 stale scalar fields
        theme.sticky_host_message = (
            "w-full rounded-xl px-3 py-2 pr-[calc(2.5%+5rem-5px)] "
            "bg-zinc-800 font-medium transition-all duration-300"
        )
        theme.sticky_pinned_message = (
            "w-full rounded-xl px-3 py-2 pr-[calc(2.5%+5rem-5px)] "
            "bg-purple-900 border border-purple-500/40 shadow-md"
        )
        theme.badge_icon_color = "text-blue-500"

        # Add new modal_styles keys
        modal = theme.modal_styles or {}
        modal.setdefault("messageText", "text-white")
        modal.setdefault("photoThumbnailBg", "bg-zinc-700")
        modal.setdefault("voiceText", "text-white/60")
        modal.setdefault("timestampText", "text-white opacity-60")
        modal.setdefault("actionLabel", "text-zinc-50")
        modal.setdefault("subtitle", "text-gray-400")
        modal.setdefault("inputField", "bg-zinc-700 text-white")
        modal.setdefault("inputBorder", "border-zinc-500")
        modal.setdefault("avatarFallbackBg", "bg-zinc-700")
        modal.setdefault("badgeIconBg", "#18181b")
        modal.setdefault("destructiveText", "text-red-400")
        modal.setdefault("actionBtnBg", "#27272a")
        modal.setdefault("actionBtnBorder", "#3f3f46")
        theme.modal_styles = modal

        # Add new gift_styles keys
        gift = theme.gift_styles or {}
        gift.setdefault("toPrefix", "text-zinc-400")
        gift.setdefault("priceText", "text-cyan-400")
        theme.gift_styles = gift

        # Add new ui_styles keys
        ui = theme.ui_styles or {}
        ui.setdefault("reactionPillBg", "bg-zinc-800 border border-zinc-700")
        ui.setdefault("reactionPillText", "text-zinc-400")
        ui.setdefault("reactionHighlightBg", "bg-purple-500/20")
        ui.setdefault("reactionHighlightBorder", "border border-purple-500/50")
        ui.setdefault("reactionHighlightText", "text-zinc-200")
        ui.setdefault("pinBadgeBg", "bg-white/10")
        ui.setdefault("loadingIndicatorText", "text-gray-400")
        ui.setdefault("loadingIndicatorBg", "bg-black/50")
        ui.setdefault("replyContextOwn", "bg-white/10 border border-white/10 hover:bg-white/15")
        ui.setdefault("replyContextOther", "bg-white/10 border border-zinc-600 hover:bg-white/15")
        ui.setdefault("replyIconColor", "text-gray-300")
        ui.setdefault("replyGiftBadge", "bg-zinc-700/60 border border-zinc-600/50")
        ui.setdefault("replyGiftText", "text-zinc-300")
        ui.setdefault("replyPreviewText", "text-gray-300")
        ui.setdefault("mediaLoadingText", "text-gray-500")
        theme.ui_styles = ui

        theme.save()


def revert_theme_fields(apps, schema_editor):
    ChatTheme = apps.get_model("chats", "ChatTheme")

    for theme in ChatTheme.objects.filter(theme_id="dark-mode"):
        # Revert scalar fields to 0062 values
        theme.sticky_host_message = (
            "w-full rounded-xl px-3 py-2 pr-[calc(2.5%+5rem-5px)] "
            "bg-blue-600 font-medium transition-all duration-300"
        )
        theme.sticky_pinned_message = (
            "w-full rounded-xl px-3 py-2 pr-[calc(2.5%+5rem-5px)] "
            "bg-purple-600 shadow-md"
        )
        theme.badge_icon_color = "text-emerald-400"

        # Remove added keys from JSON fields
        modal = theme.modal_styles or {}
        for key in ["messageText", "photoThumbnailBg", "voiceText", "timestampText",
                     "actionLabel", "subtitle", "inputField", "inputBorder",
                     "avatarFallbackBg", "badgeIconBg", "destructiveText",
                     "actionBtnBg", "actionBtnBorder"]:
            modal.pop(key, None)
        theme.modal_styles = modal

        gift = theme.gift_styles or {}
        gift.pop("toPrefix", None)
        gift.pop("priceText", None)
        theme.gift_styles = gift

        ui = theme.ui_styles or {}
        for key in ["reactionPillBg", "reactionPillText", "reactionHighlightBg",
                     "reactionHighlightBorder", "reactionHighlightText", "pinBadgeBg",
                     "loadingIndicatorText", "loadingIndicatorBg",
                     "replyContextOwn", "replyContextOther", "replyIconColor",
                     "replyGiftBadge", "replyGiftText", "replyPreviewText",
                     "mediaLoadingText"]:
            ui.pop(key, None)
        theme.ui_styles = ui

        theme.save()


class Migration(migrations.Migration):

    dependencies = [
        ("chats", "0069_populate_component_style_fields"),
    ]

    operations = [
        migrations.RunPython(fix_theme_fields, revert_theme_fields),
    ]
