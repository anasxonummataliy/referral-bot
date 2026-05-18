"""
/start handler — obuna tekshiruvi, konkurs matni, kanallar
"""

import asyncio
import logging

from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.filters import CommandStart, Command as _Command
from aiogram.utils.deep_linking import decode_payload
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.commands import setup_bot_commands
from app.core.config import settings
from app.services.subscription_service import SubscriptionService
from app.services.referral_service import ReferralService
from app.repositories.user_repo import UserRepository
from app.repositories.contest_repo import ContestRepository
from app.bot.handlers.admin.base import is_admin_async, admin_main_keyboard
from app.bot.handlers.user.utils import safe_answer, progress_bar
from app.bot.handlers.user.keyboards import main_menu_keyboard
from app.bot.handlers.user.prize import check_and_send_prize
from app.bot.handlers.user.referral_notify import notify_referrer

logger = logging.getLogger(__name__)
router = Router()

# ── Animatsiya ────────────────────────────────────────────────────────────────
PROGRESS_FRAMES = [
    "⬜⬜⬜⬜⬜  0%",
    "🟩⬜⬜⬜⬜ 20%",
    "🟩🟩⬜⬜⬜ 40%",
    "🟩🟩🟩⬜⬜ 60%",
    "🟩🟩🟩🟩⬜ 80%",
    "🟩🟩🟩🟩🟩 100% ✅",
]


async def _loading_animation(message: Message) -> None:
    try:
        anim = await message.answer("⏳ Yuklanmoqda...")
        for frame in PROGRESS_FRAMES:
            await asyncio.sleep(0.22)
            try:
                await anim.edit_text(frame)
            except Exception:
                pass
        await asyncio.sleep(0.15)
        try:
            await anim.delete()
        except Exception:
            pass
    except Exception:
        pass


def _subscription_keyboard(channels) -> InlineKeyboardMarkup:
    """Konkurs kanallari ro'yxati + tekshirish tugmasi."""
    buttons = []
    for ch in channels:
        if ch.username:
            link = f"https://t.me/{ch.username.lstrip('@')}"
            icon = "📢"
        else:
            invite = getattr(ch, "invite_link", None)
            link = invite or f"https://t.me/c/{abs(ch.channel_id)}"
            icon = "🔒"
        buttons.append([
            InlineKeyboardButton(text=f"{icon} {ch.title}", url=link)
        ])
    buttons.append([
        InlineKeyboardButton(
            text="✅ A'zo bo'ldim — tekshirish",
            callback_data="check_subscription",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _build_subscription_text(contest) -> str:
    """
    Konkurs matni + obuna so'rovi — bitta postda chiqadi.
    welcome_message bo'lsa uni ishlatadi, yo'q bo'lsa avtomatik matn.
    """
    if contest and contest.welcome_message:
        contest_block = contest.welcome_message.strip()
    elif contest:
        contest_block = (
            f"🏆 <b>{contest.title}</b>\n\n"
            f"🎯 {contest.required_referrals} ta do'st taklif qiling va sovrin yutib oling!"
        )
    else:
        contest_block = "🏆 <b>Konkurs</b>\n\nTez orada boshlanadi — kuzatib boring!"

    return (
        f"{contest_block}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n\n"
        f"📌 <b>Konursda qatnashishdan avval quyidagi kanallarga a'zo bo'ling:</b>\n\n"
        f"A'zo bo'lgach <b>✅ A'zo bo'ldim — tekshirish</b> tugmasini bosing."
    )


# ── Asosiy menyu ──────────────────────────────────────────────────────────────
async def show_main_menu(
    message: Message,
    db: AsyncSession,
    contest,
    edit: bool = False,
) -> None:
    user_id = message.from_user.id
    sub_service = SubscriptionService(db)

    is_subscribed = await sub_service.check_full_subscription(
        bot=message.bot, telegram_id=user_id
    )
    if not is_subscribed:
        channels = await sub_service.get_required_channels()
        keyboard = _subscription_keyboard(channels)
        text = _build_subscription_text(contest)
        if edit:
            try:
                await message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)
            except Exception:
                await message.answer(text, reply_markup=keyboard, disable_web_page_preview=True)
        else:
            await message.answer(text, reply_markup=keyboard, disable_web_page_preview=True)
        return

    # Referral ma'lumotlari
    bot_info = await message.bot.get_me()
    bot_username = settings.BOT_USERNAME or bot_info.username

    ref_service = ReferralService(db)
    referral_link = await ref_service.get_user_referral_link(
        telegram_id=user_id, bot_username=bot_username
    )

    user_repo = UserRepository(db)
    user = await user_repo.get_by_telegram_id(user_id)
    ref_count = user.referral_count if user else 0
    target = contest.required_referrals if contest else 5
    bar = progress_bar(ref_count, target)
    name = message.from_user.first_name or "Foydalanuvchi"

    text = (
        f"👋 <b>Xush kelibsiz, {name}!</b>\n\n"
        f"🏆 <b>{contest.title}</b>\n\n"
        f"📊 <b>Sizning natijangiz:</b>\n"
        f"✅ Tasdiqlangan do'stlar: <b>{ref_count} / {target}</b>\n\n"
        f"{bar}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 <b>Sizning taklif havolangiz:</b>\n"
        f"<code>{referral_link}</code>"
    )

    if edit:
        try:
            await message.edit_text(
                text, reply_markup=main_menu_keyboard(), disable_web_page_preview=True
            )
        except Exception:
            await message.answer(
                text, reply_markup=main_menu_keyboard(), disable_web_page_preview=True
            )
    else:
        await message.answer(
            text, reply_markup=main_menu_keyboard(), disable_web_page_preview=True
        )


# ── /start ────────────────────────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot, db: AsyncSession):
    user_id = message.from_user.id

    # Admin → admin panel
    if await is_admin_async(user_id, db):
        name = message.from_user.first_name or "Admin"
        await message.answer(
            f"🛡 <b>Xush kelibsiz, {name}!</b>\n\n"
            "🔑 <b>Admin Panel</b>\n\nQuyidagi bo'limlardan birini tanlang:",
            reply_markup=admin_main_keyboard(),
        )
        try:
            await setup_bot_commands(bot, admin_ids=settings.ADMIN_IDS)
        except Exception as e:
            logger.warning(f"setup_bot_commands xatolik: {e}")
        return

    # Referral payload
    referrer_id = None
    if message.text and len(message.text.split()) > 1:
        args = message.text.split()[1]
        try:
            payload = decode_payload(args)
            if payload.isdigit():
                referrer_id = int(payload)
        except Exception:
            try:
                if args.isdigit():
                    referrer_id = int(args)
            except Exception:
                pass

    # User yaratish / olish
    user_repo = UserRepository(db)
    _, is_new = await user_repo.get_or_create(
        telegram_id=user_id,
        full_name=message.from_user.full_name,
        username=message.from_user.username,
        language_code=message.from_user.language_code,
    )

    # Yangi user + referrer → referral qayd
    if is_new and referrer_id and referrer_id != user_id:
        ref_service = ReferralService(db)
        registered = await ref_service.process_new_referral(
            new_user_telegram_id=user_id,
            referrer_telegram_id=referrer_id,
        )
        if registered:
            await notify_referrer(
                bot=message.bot,
                referrer_telegram_id=referrer_id,
                new_user_name=message.from_user.first_name or "Do'st",
                db=db,
            )
            await check_and_send_prize(
                bot=message.bot,
                referrer_telegram_id=referrer_id,
                db=db,
            )

    # Konkursni olish
    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()

    # Animatsiya
    await _loading_animation(message)

    if not contest:
        await message.answer(
            "🤖 <b>Assalomu alaykum!</b>\n\n"
            "⏳ Hozircha aktiv konkurs mavjud emas.\n\n"
            "Tez orada yangi konkurs e'lon qilinadi — kuzatib boring! 👀"
        )
        return

    await show_main_menu(message, db, contest)


# ── Obunani tekshirish ────────────────────────────────────────────────────────
@router.callback_query(F.data == "check_subscription")
async def check_subscription_cb(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    sub_service = SubscriptionService(db)

    is_subscribed = await sub_service.check_full_subscription(
        bot=callback.bot, telegram_id=user_id
    )

    if is_subscribed:
        await safe_answer(callback, "✅ Obuna tasdiqlandi!")
        try:
            await callback.message.delete()
        except Exception:
            pass

        contest_repo = ContestRepository(db)
        contest = await contest_repo.get_active_contest()

        if not contest:
            await callback.message.answer(
                "⏳ Hozircha aktiv konkurs mavjud emas.\n\nTez orada e'lon qilinadi!"
            )
            return

        await show_main_menu(callback.message, db, contest)
    else:
        await safe_answer(
            callback,
            "❌ Siz hali barcha kanallarga a'zo bo'lmagansiz!\n"
            "Har bir kanalga a'zo bo'lib, qayta urinib ko'ring.",
            show_alert=True,
        )


# ── Orqaga ────────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "back_to_main")
async def back_to_main_cb(callback: CallbackQuery, db: AsyncSession):
    await safe_answer(callback)

    if await is_admin_async(callback.from_user.id, db):
        await callback.message.edit_text(
            "🛡 <b>Admin Panel</b>\n\nQuyidagi bo'limlardan birini tanlang:",
            reply_markup=admin_main_keyboard(),
        )
        return

    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()

    if not contest:
        await callback.message.edit_text(
            "⏳ Hozircha aktiv konkurs mavjud emas.\n\nTez orada e'lon qilinadi!"
        )
        return

    await show_main_menu(callback.message, db, contest, edit=True)


# ── /admin command ────────────────────────────────────────────────────────────
@router.message(_Command("admin"))
async def cmd_admin(message: Message, bot: Bot, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return
    name = message.from_user.first_name or "Admin"
    await message.answer(
        f"🛡 <b>Xush kelibsiz, {name}!</b>\n\n"
        "🔑 <b>Admin Panel</b>\n\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=admin_main_keyboard(),
    )
    try:
        await setup_bot_commands(bot, admin_ids=settings.ADMIN_IDS)
    except Exception as e:
        logger.warning(f"setup_bot_commands xatolik: {e}")
