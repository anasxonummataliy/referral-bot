"""
/start handler

Muammo tahlili va yechimlar:
1. Konkurs matni + kanallar — BITTA postda (welcome_message ichida + kanallar inline)
2. Admin /start bosganida o'z Telegram ID sini ko'radi (telefonda ID topish oson bo'lsin)
3. setup_bot_commands — har safar /start bosganida yangilanadi
4. Referral is_new muammosi — qo'shimcha get_by_telegram_id tekshiruvi
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
from app.bot.handlers.user.prize import (
    check_and_send_prize,
    send_prize_link,
    kick_user_from_prize_channel,
)
from app.bot.handlers.user.referral_notify import notify_referrer

logger = logging.getLogger(__name__)
router = Router()

# ── Yuklanish animatsiyasi ────────────────────────────────────────────────────
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
            await asyncio.sleep(0.18)
            try:
                await anim.edit_text(frame)
            except Exception:
                pass
        await asyncio.sleep(0.12)
        try:
            await anim.delete()
        except Exception:
            pass
    except Exception:
        pass


# ── Obuna keyboard ────────────────────────────────────────────────────────────
def _subscription_keyboard(channels) -> InlineKeyboardMarkup:
    """Kanallar ro'yxati + tekshirish tugmasi."""
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
            InlineKeyboardButton(text=f"{icon} {ch.title} ↗️", url=link)
        ])
    buttons.append([
        InlineKeyboardButton(
            text="✅ A'zo bo'ldim — Tekshirish",
            callback_data="check_subscription",
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _build_subscription_text(contest) -> str:
    """
    Konkurs kirish xabari / rasm caption.
    """
    if contest and contest.welcome_message:
        return f"{contest.welcome_message.strip()}\n\n👇 <i>Qatnashish uchun quyidagi kanallarga a'zo bo'ling:</i>"
    elif contest:
        return (
            f"🏆 <b>{contest.title}</b> 🌟\n\n"
            f"🎯 <b>{contest.required_referrals} ta</b> do'stingizni taklif qiling "
            f"va <b>yopiq VIP kanalga</b> 1 martalik link oling! 🎁\n\n"
            "👇 <i>Qatnashish uchun quyidagi kanallarga a'zo bo'ling:</i>"
        )
    else:
        return "👋 <b>Assalomu alaykum!</b> ✨\n\nTez orada yangi konkurs boshlanadi — kuzatib boring! 🔔"


async def _send_or_replace(
    message: Message,
    text: str,
    reply_markup: InlineKeyboardMarkup,
    photo_id: str | None = None,
    edit: bool = False,
) -> None:
    if edit:
        try:
            await message.delete()
        except Exception:
            pass

    if photo_id:
        try:
            await message.answer_photo(photo_id, caption=text, reply_markup=reply_markup)
            return
        except Exception as e:
            logger.warning(f"Rasm yuborishda xatolik: {e}")

    await message.answer(text, reply_markup=reply_markup, disable_web_page_preview=True)


# ── Asosiy menyu ──────────────────────────────────────────────────────────────
async def show_main_menu(
    message: Message,
    db: AsyncSession,
    contest,
    edit: bool = False,
) -> None:
    """
    Foydalanuvchiga rasm + caption va kanallar yoki asosiy menyuni chiqarish.
    """
    import urllib.parse
    from app.bot.handlers.user.share import _build_share_text

    user_id = message.from_user.id
    sub_service = SubscriptionService(db)

    is_subscribed = await sub_service.check_full_subscription(
        bot=message.bot, telegram_id=user_id
    )

    photo_id = getattr(contest, "welcome_photo_file_id", None) if contest else None

    bot_info = await message.bot.get_me()
    bot_username = settings.BOT_USERNAME or bot_info.username

    ref_service = ReferralService(db)
    referral_link = await ref_service.get_user_referral_link(
        telegram_id=user_id, bot_username=bot_username
    )

    share_text = _build_share_text(contest, referral_link)
    share_url = "https://t.me/share/url?" + urllib.parse.urlencode({"text": share_text})

    if not is_subscribed:
        channels = await sub_service.get_required_channels()
        text = _build_subscription_text(contest)
        keyboard = _subscription_keyboard(channels)
        await _send_or_replace(message, text, keyboard, photo_id=photo_id, edit=edit)
        return

    # Obuna bor — 1-xabar: Faqat konkurs rasmi va matni; 2-xabar: Alohida matnda taklif/ulashish
    user_repo = UserRepository(db)
    user = await user_repo.get_by_telegram_id(user_id)
    ref_count = user.referral_count if user else 0
    target = contest.required_referrals if contest else 5
    bar = progress_bar(ref_count, target)

    contest_text = (contest.welcome_message or contest.title or "").strip()

    text_share = (
        f"🎯 <b>Konkurs sharti:</b> {target} ta do'st taklif qilish\n\n"
        f"📊 <b>Natijangiz:</b> {ref_count} / {target} ta do'st\n"
        f"{bar}\n\n"
        f"🔗 <b>Taklif havolangiz:</b>\n"
        f"<code>{referral_link}</code>"
    )
    keyboard = main_menu_keyboard(share_url=share_url)

    if edit:
        # Masalan, 'my_referrals' yoki 'my_gifts'dan 'Orqaga' bosilganda
        try:
            await message.edit_text(text_share, reply_markup=keyboard, disable_web_page_preview=True)
            return
        except Exception:
            pass

    # 1-xabar: Rasm va konkurs matni
    if photo_id:
        try:
            await message.answer_photo(photo_id, caption=contest_text)
        except Exception as e:
            logger.warning(f"Rasm yuborishda xatolik: {e}")
            if contest_text:
                await message.answer(contest_text, disable_web_page_preview=True)
    elif contest_text:
        await message.answer(contest_text, disable_web_page_preview=True)

    # 2-xabar: Pastda alohida matnda taklif/ulashish
    await message.answer(text_share, reply_markup=keyboard, disable_web_page_preview=True)


# ── /start ────────────────────────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot, db: AsyncSession):
    user_id = message.from_user.id

    # Userni doim yaratib qo'yamiz (admin bo'lsa ham)
    user_repo = UserRepository(db)
    _, _ = await user_repo.get_or_create(
        telegram_id=user_id,
        full_name=message.from_user.full_name,
        username=message.from_user.username,
        language_code=message.from_user.language_code,
    )

    # ── ADMIN ─────────────────────────────────────────────────────────────────
    if await is_admin_async(user_id, db):
        name = message.from_user.first_name or "Admin"

        # Commandlarni o'rnatish
        try:
            await setup_bot_commands(bot, admin_ids=settings.ADMIN_IDS)
        except Exception as e:
            logger.warning(f"setup_bot_commands xatolik: {e}")

        # Admin o'z ID sini ko'radi — telefonda qo'lda izlashga hojat yo'q
        await message.answer(
            f"🛡 <b>Xush kelibsiz, {name}!</b>\n\n"
            f"🆔 <b>Sizning Telegram ID:</b> <code>{user_id}</code>\n\n"
            "🔑 <b>Admin Panel</b>\n\nQuyidagi bo'limlardan birini tanlang:",
            reply_markup=admin_main_keyboard(),
        )
        return

    # ── REFERRAL PAYLOAD ──────────────────────────────────────────────────────
    referrer_id = None
    if message.text and len(message.text.split()) > 1:
        raw = message.text.split(maxsplit=1)[1].strip()
        try:
            payload = decode_payload(raw)
            if payload.isdigit():
                referrer_id = int(payload)
        except Exception:
            if raw.isdigit():
                referrer_id = int(raw)

    # ── USER YARATISH / OLISH ─────────────────────────────────────────────────
    user_repo = UserRepository(db)

    # is_new ni ishonchli aniqlash: avval bazada bor-yo'qligini tekshiramiz
    existing = await user_repo.get_by_telegram_id(user_id)
    is_really_new = existing is None

    _, _ = await user_repo.get_or_create(
        telegram_id=user_id,
        full_name=message.from_user.full_name,
        username=message.from_user.username,
        language_code=message.from_user.language_code,
    )

    # ── REFERRAL QAYD ─────────────────────────────────────────────────────────
    # Faqat haqiqatan yangi user + referrer mavjud + o'ziga o'zi emas
    if is_really_new and referrer_id and referrer_id != user_id:
        ref_service = ReferralService(db)
        registered = await ref_service.process_new_referral(
            new_user_telegram_id=user_id,
            referrer_telegram_id=referrer_id,
        )
        if registered:
            # Referrerga +1 bildirishnomasi
            await notify_referrer(
                bot=bot,
                referrer_telegram_id=referrer_id,
                new_user_name=message.from_user.first_name or "Do'st",
                db=db,
            )
            # Shartni bajardimi? → prize link
            await check_and_send_prize(
                bot=bot,
                referrer_telegram_id=referrer_id,
                db=db,
            )

    # ── KONKURS ───────────────────────────────────────────────────────────────
    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()

    # Yuklanish animatsiyasi
    await _loading_animation(message)

    if not contest:
        await message.answer(
            "🤖 <b>Assalomu alaykum!</b>\n\n"
            "⏳ Hozircha aktiv konkurs mavjud emas.\n\n"
            "Tez orada yangi konkurs e'lon qilinadi — kuzatib boring! 👀"
        )
        return

    # Asosiy menyu (obuna tekshiruvi + konkurs matni ichida)
    await show_main_menu(message, db, contest)


# ── Obunani tekshirish callback ───────────────────────────────────────────────
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

        # Agar foydalanuvchi yetarli referral to'plagan bo'lsa va kirish huquqi faol bo'lmasa,
        # unga yangi 1 martalik link beriladi!
        user_repo = UserRepository(db)
        user = await user_repo.get_by_telegram_id(user_id)
        if contest and contest.prize_channel_id and user and user.referral_count >= contest.required_referrals:
            if not user.has_prize_access:
                await send_prize_link(
                    bot=callback.bot,
                    user_id=user_id,
                    contest=contest,
                    is_resubscribed=True,
                )
                await user_repo.update_prize_access(user_id, True)

        if not contest:
            await callback.message.answer(
                "⏳ Hozircha aktiv konkurs mavjud emas.\n\nTez orada e'lon qilinadi!"
            )
            return

        await show_main_menu(callback.message, db, contest)
    else:
        # Obunani tekshirishda a'zo bo'lmaganligi aniqlansa va prize huquqi bo'lsa — prize kanaldan chiqarish
        contest_repo = ContestRepository(db)
        contest = await contest_repo.get_active_contest()
        if contest and contest.prize_channel_id:
            user_repo = UserRepository(db)
            user = await user_repo.get_by_telegram_id(user_id)
            if user and (user.has_prize_access or user.referral_count >= contest.required_referrals):
                await kick_user_from_prize_channel(callback.bot, contest.prize_channel_id, user_id)
                await user_repo.update_prize_access(user_id, False)

        await safe_answer(
            callback,
            "❌ Siz hali barcha kanallarga a'zo bo'lmagansiz!\n"
            "Har bir kanalga a'zo bo'lib, qayta urinib ko'ring.",
            show_alert=True,
        )


# ── Orqaga ─────────────────────────────────────────────────────────────────────
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


@router.callback_query(F.data == "user_mode_start")
async def user_mode_start_cb(callback: CallbackQuery, db: AsyncSession):
    await safe_answer(callback)
    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()
    if not contest:
        await callback.message.answer("Hozircha aktiv konkurs yo'q.")
        return
    try:
        await callback.message.delete()
    except Exception:
        pass
    await show_main_menu(callback.message, db, contest, edit=False)


# ── /admin command ─────────────────────────────────────────────────────────────
@router.message(_Command("admin"))
async def cmd_admin(message: Message, bot: Bot, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return
    user_id = message.from_user.id
    name = message.from_user.first_name or "Admin"

    try:
        await setup_bot_commands(bot, admin_ids=settings.ADMIN_IDS)
    except Exception as e:
        logger.warning(f"setup_bot_commands xatolik: {e}")

    await message.answer(
        f"🛡 <b>Xush kelibsiz, {name}!</b>\n\n"
        f"🆔 <b>Sizning Telegram ID:</b> <code>{user_id}</code>\n\n"
        "🔑 <b>Admin Panel</b>\n\nQuyidagi bo'limlardan birini tanlang:",
        reply_markup=admin_main_keyboard(),
    )
