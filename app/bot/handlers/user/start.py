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
    """Kanallar ro'yxati va obunani tekshirish tugmasi."""
    buttons = []
    for i, ch in enumerate(channels, 1):
        if ch.username:
            link = f"https://t.me/{ch.username.lstrip('@')}"
            icon = "📢"
        else:
            invite = getattr(ch, "invite_link", None)
            link = invite or f"https://t.me/c/{abs(ch.channel_id)}"
            icon = "🔒"
        prefix = f"{i}. " if len(channels) > 1 else ""
        buttons.append([
            InlineKeyboardButton(text=f"{prefix}{icon} {ch.title} ↗️", url=link)
        ])
    buttons.append([
        InlineKeyboardButton(text="✅ A'zo bo'ldim", callback_data="check_subscription")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _build_subscription_text(contest) -> str:
    """
    Konkurs kirish xabari / rasm caption.
    """
    if contest and contest.welcome_message:
        return (
            f"{contest.welcome_message.strip()}\n\n"
            "👇 <i>Qatnashish uchun quyidagi kanallarga a'zo bo'ling va <b>«✅ A'zo bo'ldim»</b> tugmasini bosing:</i>"
        )
    elif contest:
        return (
            f"🏆 <b>{contest.title}</b> 🌟\n\n"
            f"🎯 <b>{contest.required_referrals} ta</b> do'stingizni taklif qiling "
            f"va <b>yopiq VIP kanalga</b> 1 martalik link oling! 🎁\n\n"
            "👇 <i>Qatnashish uchun quyidagi kanallarga a'zo bo'ling va <b>«✅ A'zo bo'ldim»</b> tugmasini bosing:</i>"
        )
    else:
        return (
            "👋 <b>Assalomu alaykum!</b> ✨\n\n"
            "👇 <i>Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling va <b>«✅ A'zo bo'ldim»</b> tugmasini bosing:</i>"
        )


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
    user_id: int | None = None,
) -> None:
    """
    Foydalanuvchiga rasm + caption va kanallar yoki asosiy menyuni chiqarish.
    """
    from app.bot.handlers.user.share import build_share_url

    if user_id is None:
        is_bot = getattr(message.from_user, "is_bot", False) is True
        user_id = message.chat.id if is_bot else (message.from_user.id if message.from_user else message.chat.id)

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

    share_url = build_share_url(referral_link, contest)

    if not is_subscribed:
        if contest and contest.prize_channel_id:
            user_repo = UserRepository(db)
            db_user = await user_repo.get_by_telegram_id(user_id)
            if db_user and (db_user.has_prize_access or db_user.referral_count >= contest.required_referrals):
                from app.bot.handlers.user.prize import kick_user_from_prize_channel
                await kick_user_from_prize_channel(message.bot, contest.prize_channel_id, user_id)
                await user_repo.update_prize_access(user_id, False)

        channels = await sub_service.get_required_channels()
        text = _build_subscription_text(contest)
        keyboard = _subscription_keyboard(channels)
        await _send_or_replace(message, text, keyboard, photo_id=photo_id, edit=edit)
        return

    # Obuna bor — 1-xabar: Faqat konkurs rasmi va matni; 2-xabar: Alohida matnda taklif/ulashish
    user_repo = UserRepository(db)
    user = await user_repo.get_by_telegram_id(user_id)
    if not user:
        chat_name = getattr(message.chat, "full_name", None) or "Foydalanuvchi"
        chat_user = getattr(message.chat, "username", None)
        user, _ = await user_repo.get_or_create(
            telegram_id=user_id,
            full_name=chat_name,
            username=chat_user,
        )
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

    # is_new ni ishonchli aniqlash: get_or_create dan avval tekshiramiz
    existing = await user_repo.get_by_telegram_id(user_id)
    is_really_new = existing is None

    user, _ = await user_repo.get_or_create(
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

    # ── REFERRAL QAYD ─────────────────────────────────────────────────────────
    # Faqat referrer mavjud + o'ziga o'zi emas + haqiqatdan ham botga birinchi marta kirgan yangi user
    if referrer_id and referrer_id != user_id and is_really_new:
        ref_service = ReferralService(db)
        registered = await ref_service.process_new_referral(
            new_user_telegram_id=user_id,
            referrer_telegram_id=referrer_id,
            give_bonus=False,
        )
        if registered:
            # Agar majburiy kanallar bo'lmasa yoki user allaqachon a'zo bo'lsa — darhol tasdiqlash
            sub_service = SubscriptionService(db)
            if await sub_service.check_full_subscription(bot=bot, telegram_id=user_id, bypass_cache=True):
                await ref_service.confirm_referral(user_id, bot)

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

    # Foydalanuvchi "A'zo bo'ldim" tugmasini bosganda keshni chetlab o'tib jonli tekshiramiz
    unsubscribed = await sub_service.get_unsubscribed_channels(
        bot=callback.bot, telegram_id=user_id, bypass_cache=True
    )

    if not unsubscribed:
        # Yangi referral bo'lsa uni tasdiqlaymiz (+1 qo'shiladi)
        ref_service = ReferralService(db)
        await ref_service.confirm_referral(user_id, callback.bot)

        await safe_answer(callback, "✅ Obuna tasdiqlandi! Xush kelibsiz! 🎉")
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

        user_repo = UserRepository(db)
        user = await user_repo.get_by_telegram_id(user_id)
        ref_count = user.referral_count if user else 0
        target = contest.required_referrals if contest else 5
        bar = progress_bar(ref_count, target)

        bot_info = await callback.bot.get_me()
        bot_username = settings.BOT_USERNAME or bot_info.username

        referral_link = await ref_service.get_user_referral_link(
            telegram_id=user_id, bot_username=bot_username
        )
        from app.bot.handlers.user.share import build_share_url
        share_url = build_share_url(referral_link, contest)

        # Agar foydalanuvchi yetarli referral to'plagan bo'lsa va prize kanal bo'lsa:
        if contest.prize_channel_id and ref_count >= target:
            from app.bot.handlers.user.prize import is_user_in_prize_channel
            in_prize = await is_user_in_prize_channel(callback.bot, contest.prize_channel_id, user_id)
            if in_prize:
                await user_repo.update_prize_access(user_id, True)
            elif not user.has_prize_access:
                sent = await send_prize_link(
                    bot=callback.bot,
                    user_id=user_id,
                    contest=contest,
                    is_resubscribed=True,
                    ref_count=ref_count,
                    db=db,
                )
                if sent:
                    await user_repo.update_prize_access(user_id, True)
                    return  # Bitta birlashtirilgan post yuborildi!

        # Prize link bo'lmaganda yoki shart to'liq bajarilmaganda — natija va havolani bitta postda chiqaramiz:
        text = (
            "✅ <b>Obuna tasdiqlandi!</b>\n\n"
            f"🎯 <b>Konkurs sharti:</b> {target} ta do'st taklif qilish\n\n"
            f"📊 <b>Natijangiz:</b> {ref_count} / {target} ta do'st\n"
            f"{bar}\n\n"
            f"🔗 <b>Taklif havolangiz:</b>\n"
            f"<code>{referral_link}</code>"
        )
        keyboard = main_menu_keyboard(share_url=share_url)
        await callback.message.answer(text, reply_markup=keyboard, disable_web_page_preview=True)
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

        # Alert matni Telegram limiti (200 belgi) dan oshmasligi shart:
        await safe_answer(
            callback,
            "❌ Hali a'zo bo'lmagan kanallaringiz bor!",
            show_alert=True,
        )

        missing_keyboard = _subscription_keyboard(unsubscribed)
        missing_text = (
            "⚠️ <b>Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:</b>\n\n"
            + "\n".join([f"• <b>{html.escape(c.title)}</b>" for c in unsubscribed])
            + "\n\nA'zo bo'lgach, «⚡️ A'zolikni tekshirish» tugmasini bosing:"
        )
        try:
            await callback.message.edit_text(missing_text, reply_markup=missing_keyboard)
        except Exception:
            try:
                await callback.message.edit_caption(caption=missing_text, reply_markup=missing_keyboard)
            except Exception:
                await callback.message.answer(missing_text, reply_markup=missing_keyboard)


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

    await show_main_menu(callback.message, db, contest, edit=True, user_id=callback.from_user.id)


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
    await show_main_menu(callback.message, db, contest, edit=False, user_id=callback.from_user.id)


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
