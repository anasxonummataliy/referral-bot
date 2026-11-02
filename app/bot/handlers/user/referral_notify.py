"""
Referrerga bildirishnoma — yangi do'st qo'shilganda.
"""
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
) -> None:
    """
    Referrerga yangi do'st qo'shilgani haqida xabar.
    Matn: admin referral_message (agar bo'lsa) + avtomatik natija.
    Keyboard: referrerning o'z havolasini ulashish tugmasi.
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
    prize_name = (contest.prize_channel_title or "Sovrin kanal") if contest else "Sovrin kanal"

    from app.bot.handlers.user.share import _build_share_text

    text = (
        f"👤 <b>{new_user_name}</b> taklif havolangiz orqali qo'shildi! (+1)\n\n"
        f"📊 Natijangiz: <b>{ref_count} / {target}</b> ta do'st"
    )
    if remaining > 0:
        text += f"\nYana <b>{remaining} ta</b> do'st taklif qilishingiz kerak."

    # ── Keyboard — referrerning deeplinki bilan ulashish ─────────────────────
    bot_info = await bot.get_me()
    bot_username = settings.BOT_USERNAME or bot_info.username

    referral_link = create_deep_link(
        username=bot_username,
        payload=str(referrer_telegram_id),
        encode=False,
        link_type="start",
    )
    share_msg = _build_share_text(contest, referral_link)
    share_url = "https://t.me/share/url?" + urllib.parse.urlencode({"text": share_msg})

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🚀 Do'stlarga ulashish",
            url=share_url,
        )],
    ])

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
