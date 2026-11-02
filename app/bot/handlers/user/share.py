"""
Havolani ulashish.

Do'stga Telegram share URL orqali yuboriladigan matn:
  welcome_message (plain text) + referral link oxirida
  → Telegram bu linkni inline button (preview) sifatida ko'rsatadi

User botda ko'radigan xabar:
  welcome_message (HTML) + "Do'stlarga ulashish" tugmasi
"""

import logging
import re
import urllib.parse

from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.referral_service import ReferralService
from app.repositories.contest_repo import ContestRepository
from app.bot.handlers.user.utils import safe_answer

logger = logging.getLogger(__name__)
router = Router()


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _build_share_text(contest, referral_link: str) -> str:
    """
    Do'stga yuboriladigan matn:
    {referral_link}

    {message}
    👆 Qatnashish uchun quyidagi tugmani bosing.
    """
    if contest and contest.referral_message:
        msg = _strip_html(contest.referral_message).strip()
    elif contest and contest.welcome_message:
        msg = _strip_html(contest.welcome_message).strip()
    elif contest:
        msg = f"{contest.title}"
    else:
        msg = "Konkursda qatnashing!"

    return f"{referral_link}\n\n{msg}\n👆 Qatnashish uchun quyidagi tugmani bosing."


def _build_user_keyboard(referral_link: str, share_text: str) -> InlineKeyboardMarkup:
    share_url = "https://t.me/share/url?" + urllib.parse.urlencode({"text": share_text})
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Do'stlarga ulashish ↗️", url=share_url)],
            [InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="back_to_main")],
        ]
    )


@router.callback_query(F.data == "share_link")
async def share_link_cb(callback: CallbackQuery, db: AsyncSession):
    await safe_answer(callback)

    user_id = callback.from_user.id
    bot_info = await callback.bot.get_me()
    bot_username = settings.BOT_USERNAME or bot_info.username

    ref_service = ReferralService(db)
    referral_link = await ref_service.get_user_referral_link(
        telegram_id=user_id, bot_username=bot_username
    )

    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()
    target = contest.required_referrals if contest else 5

    share_text = _build_share_text(contest, referral_link)
    keyboard = _build_user_keyboard(referral_link, share_text)

    text = (
        "💎 <b>Sizning shaxsiy taklif havolangiz tayyor!</b> ✨\n\n"
        f"<code>{referral_link}</code>\n\n"
        "╭────────────────────────────╮\n"
        "📌 <b>Qanday ishlaydi?</b>\n"
        "1️⃣ «🚀 Do'stlarga ulashish» tugmasini bosing\n"
        "2️⃣ Do'stlaringiz yoki guruhlarga yuboring\n"
        "3️⃣ Ular botga kirganda sizga <b>+1 do'st</b> qo'shiladi\n"
        "╰────────────────────────────╯\n\n"
        f"🎯 Maqsad: <b>{target} ta</b> do'st → <b>Yopiq kanal</b> 1 martalik linki! 🎁"
    )

    photo_id = getattr(contest, "welcome_photo_file_id", None) if contest else None

    if photo_id:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer_photo(
            photo_id, caption=text, reply_markup=keyboard
        )
    else:
        await callback.message.edit_text(
            text, reply_markup=keyboard, disable_web_page_preview=True
        )


@router.message(Command("referral", "link"))
async def cmd_referral(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    bot_info = await message.bot.get_me()
    bot_username = settings.BOT_USERNAME or bot_info.username

    ref_service = ReferralService(db)
    referral_link = await ref_service.get_user_referral_link(
        telegram_id=user_id, bot_username=bot_username
    )

    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()
    target = contest.required_referrals if contest else 5

    share_text = _build_share_text(contest, referral_link)
    keyboard = _build_user_keyboard(referral_link, share_text)

    photo_id = getattr(contest, "welcome_photo_file_id", None) if contest else None

    if photo_id:
        await message.answer_photo(
            photo_id,
            caption=(
                f"🔗 <b>Sizning taklif havolangiz:</b>\n\n"
                f"<code>{referral_link}</code>\n\n"
                f"🏅 Maqsad: <b>{target} ta</b> do'st → sovrinni yutib olasiz!"
            ),
            reply_markup=keyboard,
        )
    else:
        await message.answer(
            f"🔗 <b>Sizning taklif havolangiz:</b>\n\n"
            f"<code>{referral_link}</code>\n\n"
            f"🏅 Maqsad: <b>{target} ta</b> do'st → sovrinni yutib olasiz!",
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
