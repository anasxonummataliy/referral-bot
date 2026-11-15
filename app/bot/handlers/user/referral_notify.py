"""
Referrerga bildirishnoma — yangi do'st qo'shilganda.
"""
import html
import logging
import urllib.parse

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.deep_linking import create_deep_link
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.contest_repo import ContestRepository
from app.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)


async def notify_referrer(
    bot: Bot,
    referrer_telegram_id: int,
    new_user_name: str,
    db: AsyncSession,
    new_user_id: int | None = None,
    new_user_username: str | None = None,
    new_user=None,
) -> None:
    """
    Referrerga yangi do'st qo'shilgani haqida to'liq ma'lumotlar bilan xabar.
    """
    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()

    user_repo = UserRepository(db)
    referrer = await user_repo.get_by_telegram_id(referrer_telegram_id)
    if not referrer:
        return

    ref_count = referrer.referral_count
    target = contest.required_referrals if contest else 5
    remaining = max(0, target - ref_count)

    from app.bot.handlers.user.share import build_share_url

    # Yangi kelgan foydalanuvchi ma'lumotlarini to'liq shakllantirish
    if new_user:
        u_id = getattr(new_user, "telegram_id", None) or new_user_id
        u_name = getattr(new_user, "full_name", None) or new_user_name
        u_uname = getattr(new_user, "username", None) or new_user_username
    else:
        u_id = new_user_id
        u_name = new_user_name
        u_uname = new_user_username

    clean_name = html.escape(u_name or "Do'st")
    uname_str = f"@{html.escape(u_uname)}" if u_uname else "<i>Mavjud emas</i>"

    lines = [
        "👤 <b>Yangi do'st taklif havolangiz orqali qo'shildi! (+1)</b>\n",
        "📋 <b>Foydalanuvchi ma'lumotlari:</b>",
        f"• <b>Ism:</b> {clean_name}",
        f"• <b>Username:</b> {uname_str}",
    ]
    if u_id:
        lines.append(f"• <b>Profil:</b> <a href=\"tg://user?id={u_id}\">Profilga o'tish ↗️</a>")

    lines.append(f"\n📊 Natijangiz: <b>{ref_count} / {target}</b> ta do'st")
    if remaining > 0:
        lines.append(f"Yana <b>{remaining} ta</b> do'st taklif qilishingiz kerak.")
    else:
        lines.append("\n🎉 <b>Tabriklaymiz! Siz barcha shartlarni bajardingiz!</b>")

    text = "\n".join(lines)

    # ── Keyboard — referrerning deeplinki bilan ulashish ─────────────────────
    bot_info = await bot.get_me()
    bot_username = settings.BOT_USERNAME or bot_info.username

    referral_link = create_deep_link(
        username=bot_username,
        payload=str(referrer_telegram_id),
        encode=False,
        link_type="start",
    )
    share_url = build_share_url(referral_link, contest)

    buttons = []
    if ref_count >= target:
        buttons.append([InlineKeyboardButton(text="🎁 Sovg'ani olish", callback_data="get_prize_link")])
    buttons.append([
        InlineKeyboardButton(
            text="🚀 Do'stlarga ulashish",
            url=share_url,
        )
    ])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    try:
        await bot.send_message(
            chat_id=referrer_telegram_id,
            text=text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        logger.info(f"notify_referrer OK: referrer={referrer_telegram_id}, new={new_user_name}")
    except Exception as e:
        logger.error(f"notify_referrer XATO (referrer={referrer_telegram_id}): {e}")
