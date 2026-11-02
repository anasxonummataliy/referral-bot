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
    referrals = await referral_repo.get_user_referrals(user.id, only_confirmed=True)
    ref_count = user.referral_count

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
        text += "👥 <b>Do'stlaringiz:</b>\n"
        for i, ref in enumerate(referrals[:5], 1):
            name = ref.referred.full_name if ref.referred else "Foydalanuvchi"
            text += f"{i}. {name}\n"
        if len(referrals) > 5:
            text += f"...va yana {len(referrals) - 5} nafar"
    else:
        text += "Hali hech kimni taklif qilmadingiz."

    await callback.message.edit_text(text, reply_markup=back_keyboard())


from app.services.subscription_service import SubscriptionService
from app.bot.handlers.user.prize import send_prize_link, kick_user_from_prize_channel


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
        sub_service = SubscriptionService(db)
        is_sub = await sub_service.check_full_subscription(callback.bot, user_id)

        if not is_sub:
            # Obunasi to'liq emas — agar kirish huquqi bo'lgan bo'lsa, prize kanaldan chiqaramiz
            if user and (user.has_prize_access or user.referral_count >= target):
                if contest.prize_channel_id:
                    await kick_user_from_prize_channel(callback.bot, contest.prize_channel_id, user_id)
                    await user_repo.update_prize_access(user_id, False)

            text = (
                f"⚠️ <b>Obuna bekor qilingan!</b>\n\n"
                f"Sovg'ani olish uchun barcha majburiy kanallarga qayta a'zo bo'ling."
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⚡️ A'zolikni tekshirish", callback_data="check_subscription")],
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")],
            ])
            await callback.message.edit_text(text, reply_markup=keyboard)
            return

        text = (
            f"🎁 <b>Sovg'a: {prize_name}</b>\n\n"
            f"✅ Shart bajarilgan ({user_refs}/{target} ta do'st).\n\n"
            f"Kirish havolasini olish uchun tugmani bosing:"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔗 Havolani olish", callback_data="get_prize_link")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")],
        ])
        await callback.message.edit_text(text, reply_markup=keyboard)
        return
    else:
        needed = target - user_refs
        text = (
            f"🎁 <b>Sovg'a: {prize_name}</b>\n\n"
            f"Holat: <b>{user_refs} / {target}</b> ta do'st\n"
            f"Yana <b>{needed} ta</b> do'st taklif qilishingiz kerak."
        )
        await callback.message.edit_text(text, reply_markup=back_keyboard())


@router.callback_query(F.data == "get_prize_link")
async def get_prize_link_cb(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    user_repo = UserRepository(db)
    user = await user_repo.get_by_telegram_id(user_id)

    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()

    if not contest or not contest.prize_channel_id:
        await safe_answer(callback, "❌ Prize kanal mavjud emas.", show_alert=True)
        return

    if not user or user.referral_count < contest.required_referrals:
        await safe_answer(callback, "❌ Siz hali yetarli referral to'plamadingiz!", show_alert=True)
        return

    sub_service = SubscriptionService(db)
    is_sub = await sub_service.check_full_subscription(callback.bot, user_id)
    if not is_sub:
        await user_repo.update_prize_access(user_id, False)
        await kick_user_from_prize_channel(callback.bot, contest.prize_channel_id, user_id)
        await safe_answer(
            callback,
            "❌ Siz majburiy kanallardan chiqib ketgansiz! Avval kanallarga a'zo bo'ling.",
            show_alert=True,
        )
        return

    sent = await send_prize_link(
        bot=callback.bot,
        user_id=user_id,
        contest=contest,
        is_resubscribed=False,
    )
    if sent:
        await user_repo.update_prize_access(user_id, True)
        await safe_answer(callback, "✅ Yopiq kanal uchun 1 martalik link yuborildi!", show_alert=True)
    else:
        await safe_answer(
            callback,
            "❌ Havola yaratishda xatolik yuz berdi. Bot kanalda admin ekanligini tekshiring.",
            show_alert=True,
        )


@router.message(Command("mystats", "stats", "natija"))
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
