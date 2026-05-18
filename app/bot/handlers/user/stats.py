"""
Foydalanuvchi statistikasi — natijam, sovg'am
"""
import logging

from aiogram import Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_repo import UserRepository
from app.repositories.referral_repo import ReferralRepository
from app.repositories.contest_repo import ContestRepository
from app.bot.handlers.user.utils import safe_answer, progress_bar
from app.bot.handlers.user.keyboards import back_keyboard

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "my_referrals")
async def my_referrals_cb(callback: CallbackQuery, db: AsyncSession):
    await safe_answer(callback)

    user_id = callback.from_user.id
    user_repo = UserRepository(db)
    user = await user_repo.get_by_telegram_id(user_id)
    if not user:
        await safe_answer(callback, "Xatolik yuz berdi.", show_alert=True)
        return

    referral_repo = ReferralRepository(db)
    referrals = await referral_repo.get_user_referrals(user.id)
    ref_count = len(referrals)

    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()
    target = contest.required_referrals if contest else 5
    bar = progress_bar(ref_count, target)

    text = (
        f"📊 <b>Sizning natijangiz</b>\n\n"
        f"✅ Tasdiqlangan: <b>{ref_count} ta</b>\n\n"
        f"{bar}\n\n"
    )
    if referrals:
        text += "<b>So'nggi taklif qilganlar:</b>\n"
        for i, ref in enumerate(referrals[:10], 1):
            name = ref.referred.full_name if ref.referred else "Noma'lum"
            text += f"{i}. {name}\n"
        if len(referrals) > 10:
            text += f"\n...va yana {len(referrals) - 10} kishi"
    else:
        text += "Hali hech kim taklif qilmagansiz.\nHavolangizni ulashing! 🔗"

    await callback.message.edit_text(text, reply_markup=back_keyboard())


@router.callback_query(F.data == "my_gifts")
async def my_gifts_cb(callback: CallbackQuery, db: AsyncSession):
    await safe_answer(callback)

    user_id = callback.from_user.id
    user_repo = UserRepository(db)
    user = await user_repo.get_by_telegram_id(user_id)
    user_refs = user.referral_count if user else 0

    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()
    if not contest:
        await safe_answer(callback, "Hozircha konkurs yo'q.", show_alert=True)
        return

    target = contest.required_referrals
    prize_name = contest.prize_channel_title or "Prize Kanal"

    if user_refs >= target:
        status = f"✅ Shartni bajardingiz! ({user_refs}/{target})"
        note = "🎁 Mukofot linki shartni bajargan paytda yuborilgan."
    else:
        needed = target - user_refs
        status = f"🔒 Yana <b>{needed} ta</b> referral kerak ({user_refs}/{target})"
        note = f"🎯 {target} ta do'st taklif qiling va prize kanaliga kiring!"

    text = (
        f"🎁 <b>Sovg'a</b>\n\n"
        f"🏆 <b>{contest.title}</b>\n\n"
        f"🔒 Prize: <b>{prize_name}</b>\n"
        f"{status}\n\n"
        f"{note}"
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard())


@router.message(Command("mystats", "natija"))
async def cmd_mystats(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    user_repo = UserRepository(db)
    user = await user_repo.get_by_telegram_id(user_id)
    ref_count = user.referral_count if user else 0

    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()
    target = contest.required_referrals if contest else 5
    bar = progress_bar(ref_count, target)

    await message.answer(
        f"📊 <b>Sizning natijangiz</b>\n\n"
        f"✅ Tasdiqlangan: <b>{ref_count} ta</b>\n\n"
        f"{bar}"
    )
