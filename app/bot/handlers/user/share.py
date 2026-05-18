"""
Havolani ulashish — do'stga taklif xabari + deeplink inline button
"""
import logging
import urllib.parse

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.utils.deep_linking import create_deep_link
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.referral_service import ReferralService
from app.repositories.contest_repo import ContestRepository
from app.bot.handlers.user.utils import safe_answer

logger = logging.getLogger(__name__)
router = Router()


def _build_invite_text(contest) -> str:
    """
    Do'stga yuboriladigan taklif matni.
    Telegram share URL ichiga kiradi — HTML ishlamaydi, plain text.
    """
    if contest and contest.welcome_message:
        # welcome_message dan HTML teglarini tozalaymiz
        import re
        clean = re.sub(r"<[^>]+>", "", contest.welcome_message).strip()
        contest_block = clean
    elif contest:
        contest_block = (
            f"🏆 {contest.title}\n\n"
            f"🎯 {contest.required_referrals} ta do'st taklif qil va sovrin yutib ol!"
        )
    else:
        contest_block = "🏆 Ajoyib konkurs!"

    return (
        f"{contest_block}\n\n"
        f"👇 Qatnashish uchun quyidagi tugmani bosing:"
    )


def _share_keyboard(referral_link: str, invite_text: str) -> InlineKeyboardMarkup:
    """
    Ulashish tugmasi — Telegram share URL (deeplink bilan).
    """
    encoded_url = urllib.parse.quote(referral_link, safe="")
    encoded_text = urllib.parse.quote(invite_text, safe="")
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

    invite_text = _build_invite_text(contest)
    keyboard = _share_keyboard(referral_link, invite_text)

    text = (
        f"🔗 <b>Sizning taklif havolangiz:</b>\n\n"
        f"<code>{referral_link}</code>\n\n"
        f"📌 Quyidagi <b>📤 Do'stlarga ulashish</b> tugmasini bosing.\n"
        f"Do'stingiz havolani bosib botga kirganida sizga <b>+1</b> qo'shiladi.\n\n"
        f"🏅 Maqsad: <b>{target} ta</b> do'st → sovrin yutib olasiz!"
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

    invite_text = _build_invite_text(contest)
    keyboard = _share_keyboard(referral_link, invite_text)

    text = (
        f"🔗 <b>Sizning taklif havolangiz:</b>\n\n"
        f"<code>{referral_link}</code>\n\n"
        f"📌 <b>📤 Do'stlarga ulashish</b> tugmasini bosib yuboring.\n\n"
        f"🏅 Maqsad: <b>{target} ta</b> do'st → sovrin yutib olasiz!"
    )

    await message.answer(
        text, reply_markup=keyboard, disable_web_page_preview=True
    )
