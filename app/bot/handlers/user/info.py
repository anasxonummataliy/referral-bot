"""
Shartlar va yordam
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.contest_repo import ContestRepository
from app.bot.handlers.user.utils import safe_answer
from app.bot.handlers.user.keyboards import back_keyboard

router = Router()


@router.callback_query(F.data == "terms")
async def terms_cb(callback: CallbackQuery, db: AsyncSession):
    await safe_answer(callback)

    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()
    target = contest.required_referrals if contest else 5
    prize = contest.prize_channel_title if contest else "Sovg'a kanali"

    text = (
        "📜 <b>Konkurs shartlari:</b>\n\n"
        f"1. Taklif havolangizni do'stlaringizga yuboring.\n"
        f"2. Do'stlaringiz kanallarga a'zo bo'lishi kerak.\n"
        f"3. <b>{target} ta do'st</b> to'plaganingizda <b>{prize}</b> kanaliga 1 martalik link beriladi.\n\n"
        "<i>Eslatma: Majburiy kanallardan chiqib ketsangiz, sovg'a kanalidan ham chiqarilasiz.</i>"
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard())


@router.callback_query(F.data == "help")
async def help_cb(callback: CallbackQuery):
    await safe_answer(callback)

    text = (
        "❓ <b>Yordam</b>\n\n"
        "/start — Bosh menyu\n"
        "/referral — Taklif havolasi\n"
        "/mystats — Natijangiz\n\n"
        "Savollaringiz bo'lsa, «✉️ Bog'lanish» tugmasi orqali yozishingiz mumkin."
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "❓ <b>Yordam</b>\n\n"
        "/start — Bosh menyu\n"
        "/referral — Taklif havolasi\n"
        "/mystats — Natijangiz\n\n"
        "Savollaringiz bo'lsa, «✉️ Bog'lanish» tugmasi orqali yozishingiz mumkin."
    )
