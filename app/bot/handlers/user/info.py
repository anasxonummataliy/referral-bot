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
        "📜 <b>Konkurs Qoidalari va Shartlari</b> ✨\n\n"
        f"🏆 <b>{contest.title if contest else 'Konkurs'}</b> 🌟\n\n"
        "╭────────────────────────────╮\n"
        "1️⃣ O'z maxsus taklif havolangiz orqali do'stlaringizni taklif qiling.\n"
        "2️⃣ Taklif qilingan do'st barcha majburiy kanallarga a'zo bo'lishi shart.\n"
        "3️⃣ Bitta akkaunt faqat 1 marta referral sifatida hisoblanadi.\n"
        f"4️⃣ <b>{target} ta do'st</b> taklif qilganingizda sizga <b>{prize}</b> yopiq kanaliga <b>1 martalik kirish havolasi</b> beriladi! 🎁\n"
        "5️⃣ ⚠️ <b>Muhim:</b> Agar majburiy kanallarning birontasidan chiqib ketsangiz, yopiq kanaldan ham chiqarilasiz!\n"
        "6️⃣ Qayta barcha kanallarga a'zo bo'lsangiz, yangi 1 martalik link taqdim etiladi! 🚀\n"
        "╰────────────────────────────╯"
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard())


@router.callback_query(F.data == "help")
async def help_cb(callback: CallbackQuery):
    await safe_answer(callback)

    text = (
        "❓ <b>Qo'llanma va Yordam</b> 💡\n\n"
        "🤖 <b>Botdagi mavjud buyruqlar:</b>\n"
        "🚀 /start — Botning bosh menyusiga qaytish\n"
        "🔗 /referral — Shaxsiy taklif havolangizni olish\n"
        "📊 /mystats — Takliflaringiz natijasini tekshirish\n"
        "❓ /help — Foydalanish yo'riqnomasi\n\n"
        "💬 <i>Savol yoki takliflar bo'lsa, admin bilan bog'laning!</i>"
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard())


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "❓ <b>Qo'llanma va Yordam</b> 💡\n\n"
        "🤖 <b>Botdagi mavjud buyruqlar:</b>\n"
        "🚀 /start — Botning bosh menyusiga qaytish\n"
        "🔗 /referral — Shaxsiy taklif havolangizni olish\n"
        "📊 /mystats — Takliflaringiz natijasini tekshirish\n"
        "❓ /help — Foydalanish yo'riqnomasi\n\n"
        "💬 <i>Savol yoki takliflar bo'lsa, admin bilan bog'laning!</i>"
    )
