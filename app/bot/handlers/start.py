"""
Asosiy /start handler
• Admin bo'lsa — admin panel ko'rsatiladi (referral shart emas)
• Konkurs yo'q bo'lsa — "Hozircha konkurs yo'q" xabari
• Konkurs bor bo'lsa:
  1. Welcome message (majburiy kanallardan OLDIN)
  2. Majburiy kanallar tekshiruvi
  3. Asosiy menyu + progress bar
• Referral shartini bajargan userga — 1 martalik prize kanal linki
"""

import asyncio
import logging

from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand,
)
from aiogram.filters import CommandStart, Command
from aiogram.utils.deep_linking import decode_payload
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.subscription_service import SubscriptionService
from app.services.referral_service import ReferralService
from app.repositories.user_repo import UserRepository
from app.repositories.contest_repo import ContestRepository
from app.bot.handlers.admin.base import is_admin_async, admin_main_keyboard

logger = logging.getLogger(__name__)
router = Router()


# ── HTML xavfsiz yuborish ─────────────────────────────────────────────────────
import html as _html_module
import re as _re

# Telegram qo'llab-quvvatlaydigan HTML teglar
_ALLOWED_TAGS = {
    "b",
    "strong",
    "i",
    "em",
    "u",
    "ins",
    "s",
    "strike",
    "del",
    "code",
    "pre",
    "a",
    "tg-spoiler",
    "tg-emoji",
    "blockquote",
    "br",
}


def _has_unsupported_html(text: str) -> bool:
    """Matnda Telegram qo'llab-quvvatlamaydigan HTML teg bormi?"""
    tags = _re.findall(r"</?(\w[\w\d]*)", text)
    return any(t.lower() not in _ALLOWED_TAGS for t in tags)


async def safe_send_message(message: Message, text: str) -> None:
    """
    Matnni xavfsiz yuborish:
    - Agar faqat ruxsat etilgan HTML teglari bo'lsa → parse_mode=HTML
    - Agar noto'g'ri / qo'llab-quvvatlanmaydigan teglar bo'lsa → parse_mode=None (oddiy matn)
    """
    if "<" in text and _has_unsupported_html(text):
        # Noto'g'ri HTML — oddiy matn sifatida yuborish
        logger.warning(
            "welcome_message HTML xatolik bor, plain text sifatida yuborilmoqda"
        )
        await message.answer(text, parse_mode=None, disable_web_page_preview=True)
    else:
        await message.answer(text, disable_web_page_preview=True)


# ── Progress bar ─────────────────────────────────────────────────────────────
PROGRESS_FRAMES = [
    "⬜⬜⬜⬜⬜  0%",
    "🟩⬜⬜⬜⬜ 20%",
    "🟩🟩⬜⬜⬜ 40%",
    "🟩🟩🟩⬜⬜ 60%",
    "🟩🟩🟩🟩⬜ 80%",
    "🟩🟩🟩🟩🟩 100% ✅",
]


def _progress_bar(current: int, total: int) -> str:
    if total <= 0:
        total = 5
    filled = min(int(current / total * 5), 5)
    empty = 5 - filled
    pct = min(int(current / total * 100), 100)
    bar = "🟩" * filled + "⬜" * empty
    return f"{bar}\n{current}/{total} ({pct}%)"


async def _loading_animation(message: Message) -> None:
    """Faqat /start message uchun — callback uchun ISHLATMANG"""
    try:
        anim_msg = await message.answer("⏳ Yuklanmoqda...")
        for frame in PROGRESS_FRAMES:
            await asyncio.sleep(0.22)
            try:
                await anim_msg.edit_text(frame)
            except Exception:
                pass
        await asyncio.sleep(0.2)
        try:
            await anim_msg.delete()
        except Exception:
            pass
    except Exception:
        pass


# ── Bot commandlarini o'rnatish ──────────────────────────────────────────────
async def set_bot_commands(bot: Bot) -> None:
    """Bot uchun /commands ro'yxatini o'rnatish"""
    commands = [
        BotCommand(command="start", description="🏠 Bosh menyu"),
        BotCommand(command="referral", description="🔗 Mening taklif havolam"),
        BotCommand(command="mystats", description="📊 Mening natijam"),
        BotCommand(command="help", description="❓ Yordam"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("✅ Bot commandlari o'rnatildi")
    except Exception as e:
        logger.error(f"Bot commandlarini o'rnatishda xatolik: {e}")


# ── Safe callback answer ──────────────────────────────────────────────────────
async def safe_answer(
    callback: CallbackQuery, text: str = "", show_alert: bool = False
) -> None:
    """
    callback.answer() — xatolikni yutib yuboradi.
    Telegram 30 sekund limitdan o'tsa TelegramBadRequest chiqaradi,
    shu holda bot ishdan chiqmasin.
    """
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramBadRequest as e:
        logger.warning(
            f"callback.answer() xatoligi (user={callback.from_user.id}): {e}"
        )
    except Exception as e:
        logger.warning(f"callback.answer() noma'lum xatolik: {e}")


# ── Subscription keyboard ────────────────────────────────────────────────────
def _build_subscription_keyboard(channels) -> InlineKeyboardMarkup:
    buttons = []
    for ch in channels:
        if ch.username:
            link = f"https://t.me/{ch.username.lstrip('@')}"
            icon = "📢 "
        else:
            invite = getattr(ch, "invite_link", None)
            link = invite or f"https://t.me/c/{str(abs(ch.channel_id))}"
            icon = "🔒 "
        buttons.append([InlineKeyboardButton(text=f"{icon}{ch.title}", url=link)])
    buttons.append(
        [InlineKeyboardButton(text="✅ Tekshirish", callback_data="check_subscription")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Havolani Ulashish ↗", callback_data="share_link"
                )
            ],
            [
                InlineKeyboardButton(text="📊 Natijam", callback_data="my_referrals"),
                InlineKeyboardButton(text="🎁 Sovg'am", callback_data="my_gifts"),
            ],
            [
                InlineKeyboardButton(text="📜 Shartlar", callback_data="terms"),
                InlineKeyboardButton(text="❓ Yordam", callback_data="help"),
            ],
        ]
    )


# ── Admin panel ──────────────────────────────────────────────────────────────
async def _show_admin_panel(message: Message) -> None:
    name = message.from_user.first_name if message.from_user else "Admin"
    text = (
        f"🛡 <b>Xush kelibsiz, {name}!</b>\n\n"
        f"🔑 <b>Admin Panel</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:"
    )
    await message.answer(text, reply_markup=admin_main_keyboard())


# ── Asosiy menyu (user) ──────────────────────────────────────────────────────
async def _show_main_menu(
    message: Message,
    db: AsyncSession,
    contest,
    edit: bool = False,
):
    user_id = message.from_user.id
    subscription_service = SubscriptionService(db)

    is_subscribed = await subscription_service.check_full_subscription(
        bot=message.bot, telegram_id=user_id
    )
    if not is_subscribed:
        required_channels = await subscription_service.get_required_channels()
        keyboard = _build_subscription_keyboard(required_channels)
        text = (
            "👋 <b>Assalomu alaykum!</b>\n\n"
            "🔐 Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:\n\n"
            "A'zo bo'lgach <b>✅ Tekshirish</b> tugmasini bosing."
        )
        if edit:
            try:
                await message.edit_text(text, reply_markup=keyboard)
            except Exception:
                await message.answer(text, reply_markup=keyboard)
        else:
            await message.answer(text, reply_markup=keyboard)
        return

    bot_info = await message.bot.get_me()
    bot_username = settings.BOT_USERNAME or bot_info.username

    referral_service = ReferralService(db)
    referral_link = await referral_service.get_user_referral_link(
        telegram_id=user_id, bot_username=bot_username
    )

    user_repo = UserRepository(db)
    user = await user_repo.get_by_telegram_id(user_id)
    referral_count = user.referral_count if user else 0
    target = contest.required_referrals if contest else 5

    bar = _progress_bar(referral_count, target)
    name = message.from_user.first_name if message.from_user else "Foydalanuvchi"

    text = (
        f"👋 <b>Xush kelibsiz, {name}!</b>\n\n"
        f"🏆 <b>Konkurs:</b> {contest.title}\n"
        f"🎯 Maqsad: <b>{target} ta</b> do'st taklif qiling\n\n"
        f"📊 <b>Sizning natijangiz:</b>\n"
        f"✅ Tasdiqlangan: <b>{referral_count} ta</b>\n\n"
        f"{bar}\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 <b>Sizning havolangiz:</b>\n"
        f"<code>{referral_link}</code>"
    )

    keyboard = _main_menu_keyboard()

    if edit:
        try:
            await message.edit_text(
                text, reply_markup=keyboard, disable_web_page_preview=True
            )
        except Exception:
            await message.answer(
                text, reply_markup=keyboard, disable_web_page_preview=True
            )
    else:
        await message.answer(text, reply_markup=keyboard, disable_web_page_preview=True)


# ── Prize link berish (1 martalik) ───────────────────────────────────────────
async def _send_prize_link(bot, user_id: int, contest) -> None:
    """
    1 martalik invite link yaratib inline button orqali yuborish.
    member_limit=1 -> faqat bitta kishi kirishi mumkin (Telegram kafolati).
    """
    if not contest or not contest.prize_channel_id:
        return
    try:
        invite = await bot.create_chat_invite_link(
            chat_id=contest.prize_channel_id,
            member_limit=1,  # Faqat 1 kishi - Telegram kafolati
            creates_join_request=False,
        )
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=f"🎁 {contest.prize_channel_title} ga kirish",
                        url=invite.invite_link,
                    )
                ]
            ]
        )
        await bot.send_message(
            chat_id=user_id,
            text=(
                f"🎉 <b>Tabriklaymiz!</b>"
                f"Siz <b>{contest.required_referrals} ta</b> do'st taklif qildingiz!"
                f"⬇️ Quyidagi tugmani bosing va kanalga kiring:"
                f"⚠️ <b>Diqqat:</b> Bu havola faqat <b>1 marta</b> ishlaydi!"
                f"Boshqa birovga bermang — kirish huquqi faqat sizga."
            ),
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        logger.info(f"Prize link yuborildi: user={user_id}")
    except Exception as e:
        logger.error(f"Prize link yaratishda xatolik (user={user_id}): {e}")


# ── /start ───────────────────────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message, db: AsyncSession):
    user_id = message.from_user.id

    if await is_admin_async(user_id, db):
        await _show_admin_panel(message)
        return

    args = None
    if message.text and len(message.text.split()) > 1:
        args = message.text.split()[1]

    referrer_id = None
    if args:
        try:
            payload = decode_payload(args)
            if payload.isdigit():
                referrer_id = int(payload)
        except Exception:
            if args.isdigit():
                referrer_id = int(args)

    user_repo = UserRepository(db)
    referral_service = ReferralService(db)

    user, is_new = await user_repo.get_or_create(
        telegram_id=user_id,
        full_name=message.from_user.full_name,
        username=message.from_user.username,
        language_code=message.from_user.language_code,
    )

    if is_new and referrer_id and referrer_id != user_id:
        await referral_service.process_new_referral(
            new_user_telegram_id=user_id,
            referrer_telegram_id=referrer_id,
        )
        await _check_and_send_prize(
            bot=message.bot,
            referrer_telegram_id=referrer_id,
            db=db,
        )

    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()

    # Animatsiya faqat /start (message) uchun
    await _loading_animation(message)

    if not contest:
        await message.answer(
            "🤖 <b>Assalomu alaykum!</b>\n\n"
            "⏳ Hozircha aktiv konkurs yo'q.\n\n"
            "Tez orada yangi konkurs e'lon qilinadi — kuzatib boring! 👀"
        )
        return

    if contest.welcome_message:
        await safe_send_message(message, contest.welcome_message)

    await _show_main_menu(message, db, contest)


async def _check_and_send_prize(
    bot, referrer_telegram_id: int, db: AsyncSession
) -> bool:
    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()
    if not contest or not contest.prize_channel_id:
        return False

    user_repo = UserRepository(db)
    referrer = await user_repo.get_by_telegram_id(referrer_telegram_id)
    if not referrer:
        return False

    if referrer.referral_count == contest.required_referrals:
        await _send_prize_link(bot, referrer_telegram_id, contest)
        return True
    return False


# ── Obunani tekshirish ───────────────────────────────────────────────────────
@router.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    subscription_service = SubscriptionService(db)

    is_subscribed = await subscription_service.check_full_subscription(
        bot=callback.bot, telegram_id=user_id
    )

    if is_subscribed:
        # ✅ FIX #1: callback.answer() ANIMATSIYADAN VA BOSHQA AMALLARDAN OLDIN
        await safe_answer(callback, "✅ Obuna tasdiqlandi!", show_alert=False)

        try:
            await callback.message.delete()
        except Exception:
            pass

        # ✅ FIX #2: Callbackda animatsiya YO'Q — timeout bo'ladi
        # Animatsiya faqat /start message uchun

        contest_repo = ContestRepository(db)
        contest = await contest_repo.get_active_contest()

        if not contest:
            await callback.message.answer(
                "⏳ Hozircha aktiv konkurs yo'q.\n\nTez orada e'lon qilinadi!"
            )
            return

        await _show_main_menu(callback.message, db, contest)
    else:
        # ✅ FIX #1: callback.answer() BIRINCHI
        await safe_answer(
            callback,
            "❌ Siz hali barcha kanallarga a'zo bo'lmagansiz!",
            show_alert=True,
        )


# ── Havolani ulashish ────────────────────────────────────────────────────────
@router.callback_query(F.data == "share_link")
async def share_link_callback(callback: CallbackQuery, db: AsyncSession):
    await safe_answer(callback)  # ✅ BIRINCHI

    user_id = callback.from_user.id
    bot_info = await callback.bot.get_me()
    bot_username = settings.BOT_USERNAME or bot_info.username

    referral_service = ReferralService(db)
    referral_link = await referral_service.get_user_referral_link(
        telegram_id=user_id, bot_username=bot_username
    )

    import urllib.parse

    encoded_link = urllib.parse.quote(referral_link, safe="")
    encoded_text = urllib.parse.quote("Do'stim siz uchun ajoyib taklif! 🎁", safe="")
    share_url = f"https://t.me/share/url?url={encoded_link}&text={encoded_text}"

    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()
    target = contest.required_referrals if contest else 5

    text = (
        f"🔗 <b>Sizning taklif havolangiz:</b>\n\n"
        f"<code>{referral_link}</code>\n\n"
        f"🎯 Maqsad: <b>{target} ta</b> do'st taklif qiling\n"
        f"🎁 Mukofot: Prize kanalga 1 martalik kirish!\n\n"
        f"Havolani do'stlaringizga yuboring! 📤"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📤 Ulashish ↗", url=share_url)],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")],
        ]
    )

    await callback.message.edit_text(
        text, reply_markup=keyboard, disable_web_page_preview=True
    )


# ── Natijam ──────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "my_referrals")
async def my_referrals_callback(callback: CallbackQuery, db: AsyncSession):
    await safe_answer(callback)  # ✅ BIRINCHI

    user_id = callback.from_user.id
    user_repo = UserRepository(db)
    user = await user_repo.get_by_telegram_id(user_id)

    if not user:
        await safe_answer(callback, "Xatolik yuz berdi.", show_alert=True)
        return

    from app.repositories.referral_repo import ReferralRepository

    referral_repo = ReferralRepository(db)
    referrals = await referral_repo.get_user_referrals(user.id)
    referral_count = len(referrals)

    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()
    target = contest.required_referrals if contest else 5

    bar = _progress_bar(referral_count, target)

    text = (
        f"📊 <b>Sizning natijangiz</b>\n\n"
        f"✅ Tasdiqlangan: <b>{referral_count} ta</b>\n\n"
        f"{bar}\n\n"
    )

    if referrals:
        text += "<b>So'nggi taklif qilganlar:</b>\n"
        for i, ref in enumerate(referrals[:10], 1):
            referred_user = ref.referred
            name = referred_user.full_name if referred_user else "Noma'lum"
            text += f"{i}. {name}\n"
        if len(referrals) > 10:
            text += f"\n...va yana {len(referrals) - 10} kishi"
    else:
        text += "Hali hech kim taklif qilmagansiz.\nHavolangizni ulashing! 🔗"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")]
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)


# ── Sovg'am ──────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "my_gifts")
async def my_gifts_callback(callback: CallbackQuery, db: AsyncSession):
    await safe_answer(callback)  # ✅ BIRINCHI

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
        note = "🎁 Mukofot linki siz bajargan paytda yuborilgan."
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

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")]
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)


# ── Loyiha shartlari ─────────────────────────────────────────────────────────
@router.callback_query(F.data == "terms")
async def terms_callback(callback: CallbackQuery):
    await safe_answer(callback)  # ✅ BIRINCHI

    text = (
        "📜 <b>Konkurs Shartlari</b>\n\n"
        "1️⃣ Do'stlaringizni o'z havolangiz orqali taklif qiling.\n"
        "2️⃣ Taklif qilingan do'st majburiy kanallarga a'zo bo'lishi shart.\n"
        "3️⃣ Bir odam faqat bir marta hisoblanadi.\n"
        "4️⃣ Soxta akkauntlar aniqlansa, hisob bekor qilinadi.\n"
        "5️⃣ Shartni bajargan zahoti 1 martalik prize kanal linki yuboriladi.\n"
        "6️⃣ Qayta link olish uchun yana shartni bajarish kerak."
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")]
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)


# ── Yordam ───────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "help")
async def help_cb(callback: CallbackQuery):
    await safe_answer(callback)  # ✅ BIRINCHI

    text = (
        "❓ <b>Yordam</b>\n\n"
        "<b>Buyruqlar:</b>\n"
        "🔹 /start — Botni qayta ishga tushirish\n"
        "🔹 /referral — Mening taklif havolam\n"
        "🔹 /mystats — Mening natijam\n"
        "🔹 /help — Yordam\n\n"
        "📩 Muammolar uchun adminlarga murojaat qiling."
    )
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_main")]
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)


# ── User buyruqlari ──────────────────────────────────────────────────────────
@router.message(Command("referral", "link"))
async def cmd_referral(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    bot_info = await message.bot.get_me()
    bot_username = settings.BOT_USERNAME or bot_info.username

    referral_service = ReferralService(db)
    referral_link = await referral_service.get_user_referral_link(
        telegram_id=user_id, bot_username=bot_username
    )

    import urllib.parse

    encoded_link = urllib.parse.quote(referral_link, safe="")
    encoded_text = urllib.parse.quote("Do'stim siz uchun ajoyib taklif! 🎁", safe="")
    share_url = f"https://t.me/share/url?url={encoded_link}&text={encoded_text}"

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📤 Ulashish ↗", url=share_url)],
        ]
    )
    await message.answer(
        f"🔗 <b>Sizning taklif havolangiz:</b>\n\n<code>{referral_link}</code>",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )


@router.message(Command("mystats", "natija"))
async def cmd_mystats(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    user_repo = UserRepository(db)
    user = await user_repo.get_by_telegram_id(user_id)
    referral_count = user.referral_count if user else 0

    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()
    target = contest.required_referrals if contest else 5
    bar = _progress_bar(referral_count, target)

    await message.answer(
        f"📊 <b>Sizning natijangiz</b>\n\n"
        f"✅ Tasdiqlangan: <b>{referral_count} ta</b>\n\n"
        f"{bar}"
    )


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


# ── Admin /start ──────────────────────────────────────────────────────────────
@router.message(Command("admin"))
async def cmd_admin_panel(message: Message, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return
    await _show_admin_panel(message)


# ── Orqaga ───────────────────────────────────────────────────────────────────
@router.callback_query(F.data == "back_to_main")
async def back_to_main_callback(callback: CallbackQuery, db: AsyncSession):
    await safe_answer(callback)  # ✅ BIRINCHI

    if await is_admin_async(callback.from_user.id, db):
        await callback.message.edit_text(
            "🛠 <b>Admin Panel</b>\n\nQuyidagi bo'limlardan birini tanlang:",
            reply_markup=admin_main_keyboard(),
        )
        return

    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()

    if not contest:
        await callback.message.edit_text(
            "⏳ Hozircha aktiv konkurs yo'q.\n\nTez orada e'lon qilinadi!"
        )
        return

    await _show_main_menu(callback.message, db, contest, edit=True)
