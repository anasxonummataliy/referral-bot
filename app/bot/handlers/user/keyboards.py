"""
Barcha inline keyboard — premium stiker va emojilar bilan
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_keyboard(share_url: str | None = None) -> InlineKeyboardMarkup:
    buttons = []
    if share_url:
        buttons.append([InlineKeyboardButton(text="🚀 Do'stlarga ulashish ↗️", url=share_url)])
    else:
        buttons.append([InlineKeyboardButton(text="💎 Havolani Ulashish 🚀", callback_data="share_link")])

    buttons.extend([
        [
            InlineKeyboardButton(text="📈 Mening natijam ⭐️", callback_data="my_referrals"),
            InlineKeyboardButton(text="👑 Sovg'am 🎁", callback_data="my_gifts"),
        ],
        [
            InlineKeyboardButton(text="💬 Admin bilan bog'lanish ✍️", callback_data="contact_admin"),
        ],
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def subscription_keyboard(channels) -> InlineKeyboardMarkup:
    buttons = []
    for ch in channels:
        if ch.username:
            link = f"https://t.me/{ch.username.lstrip('@')}"
            icon = "📢"
        else:
            invite = getattr(ch, "invite_link", None)
            link = invite or f"https://t.me/c/{abs(ch.channel_id)}"
            icon = "🔒"
        buttons.append([InlineKeyboardButton(text=f"{icon} {ch.title} ↗️", url=link)])
    buttons.append([
        InlineKeyboardButton(text="⚡️ A'zo bo'ldim — Tekshirish ✅", callback_data="check_subscription")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def back_keyboard(cb_data: str = "back_to_main") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Asosiy menyuga qaytish", callback_data=cb_data)]
    ])


def prize_keyboard(channel_title: str, invite_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"👑 {channel_title} — Kirish 🚀", url=invite_url)]
    ])
