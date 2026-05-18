"""
Havolani ulashish — konkurs matni + deeplink inline button

Do'stga yuboriladigan xabarda:
- Konkurs matni (welcome_message yoki avtomatik)
- "Qatnashish uchun quyidagi tugmani bosing" matni
- Inline button → botga deeplink (bosganida /start?start=REFERRER_ID)
"""
import logging
import re
import urllib.parse

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
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
    """HTML teglarni olib tashlash — Telegram share URLsi uchun."""
    return re.sub(r"<[^>]+>", "", text).strip()


def _build_share_text(contest) -> str:
    """
    Do'stga yuboriladigan taklif matni (plain text, HTML yo'q).
    Telegram share URL'da ko'rinadi.
    """
    if contest and contest.welcome_message:
        contest_block = _strip_html(contest.welcome_message)
    elif contest:
        contest_block = (
            f"🏆 {contest.title}\n\n"
            f"🎯 {contest.required_referrals} ta do'st taklif qil — sovrin yutib ol!"
        )
    else:
        contest_block = "🏆 Ajoyib konkurs boshlanmoqda!"

    return (
        f"{contest_block}\n\n"
        "👇 Qatnashish uchun quyidagi tugmani bosing:"
    )


def _build_share_keyboard(referral_link: str, share_text: str) -> InlineKeyboardMarkup:
    """
    Ulashish tugmasi — Telegram share URL (deeplink + matn birgalikda).
    Do'st tugmani bosganida: Telegram share dialog ochiladi.
    Do'st havolani bosganida: bot /start?start=REFERRER_ID qabul qiladi.
    """
    encoded_url = urllib.parse.quote(referral_link, safe="")
    encoded_text = urllib.parse.quote(share_text, safe="")
    share_url = f"https://t.me/share/url?url={encoded_url}&text={encoded_text}"

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Do'stlarga ulashish ↗", url=share_url)],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")],
    ])


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

    share_text = _build_share_text(contest)
    keyboard = _build_share_keyboard(referral_link, share_text)

    text = (
        "🔗 <b>Taklif havolangiz tayyor!</b>\n\n"
        f"<code>{referral_link}</code>\n\n"
        "📌 <b>Qanday ishlaydi?</b>\n"
        "1️⃣ Quyidagi tugmani bosib do'stlaringizga yuboring\n"
        "2️⃣ Do'stingiz havolani bosib botga kiradi\n"
        "3️⃣ Sizga avtomatik <b>+1</b> qo'shiladi\n\n"
        f"🏅 Maqsad: <b>{target} ta</b> do'st → sovrinni yutib olasiz!"
    )

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

    share_text = _build_share_text(contest)
    keyboard = _build_share_keyboard(referral_link, share_text)

    await message.answer(
        f"🔗 <b>Sizning taklif havolangiz:</b>\n\n"
        f"<code>{referral_link}</code>\n\n"
        f"🏅 Maqsad: <b>{target} ta</b> do'st → sovrinni yutib olasiz!",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )
