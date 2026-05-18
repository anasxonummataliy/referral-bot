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
    prize = contest.prize_channel_title if contest else "Prize Kanal"

    text = (
        "📜 <b>Konkurs Shartlari</b>\n\n"
        f"🏆 <b>{contest.title if contest else 'Konkurs'}</b>\n\n"
        f"1️⃣ O'z taklif havolangiz orqali do'stlarni taklif qiling.\n"
        f"2️⃣ Taklif qilingan do'st majburiy kanallarga a'zo bo'lishi shart.\n"
        f"3️⃣ Bir odam faqat bir marta hisoblanadi.\n"
        f"4️⃣ Soxta akkauntlar aniqlansa, hisob bekor qilinadi.\n"
        f"5️⃣ <b>{target} ta</b> do'st taklif qilgandan so'ng \n"
        f"   <b>{prize}</b> kanaliga 1 martalik kirish havolasi yuboriladi.\n"
        f"6️⃣ Qayta link olish uchun yana shartni bajarish kerak."
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard())


@router.callback_query(F.data == "help")
async def help_cb(callback: CallbackQuery):
    await safe_answer(callback)

    text = (
        "❓ <b>Yordam</b>\n\n"
        "<b>Buyruqlar:</b>\n"
        "🔹 /start — Botni qayta ishga tushirish\n"
        "🔹 /referral — Mening taklif havolam\n"
        "🔹 /mystats — Mening natijam\n"
        "🔹 /help — Yordam\n\n"
        "📩 Muammolar uchun adminlarga murojaat qiling."
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "❓ <b>Yordam</b>\n\n"
        "🔹 /start — Botni qayta ishga tushirish\n"
        "🔹 /referral — Mening taklif havolam\n"
        "🔹 /mystats — Mening natijam\n"
        "🔹 /help — Yordam\n\n"
        "📩 Muammolar uchun adminlarga murojaat qiling."
    )
