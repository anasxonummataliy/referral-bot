"""
Konkurs boshqaruvi — admin panel
• Bitta aktiv konkurs
• Kirish xabari (majburiy kanallardan OLDIN)
• Prize kanal + 1 martalik invite link
"""
import re
import html as _html

from aiogram import F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.admin.base import admin_router, is_admin_async, admin_main_keyboard
from app.repositories.contest_repo import ContestRepository

router = admin_router


# ── FSM holatlari ────────────────────────────────────────────────────────────
class ContestStates(StatesGroup):
    waiting_title = State()
    waiting_welcome = State()
    waiting_required_refs = State()


class PrizeChannelStates(StatesGroup):
    waiting_channel = State()


# ── Konkurs menyusi ──────────────────────────────────────────────────────────
async def _show_contest_menu(target, db: AsyncSession, edit: bool = False):
    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()

    if contest:
        prize_info = (
            f"🎁 Prize kanal: <b>{contest.prize_channel_title}</b>"
            if contest.prize_channel_id
            else "🎁 Prize kanal: <i>qo'shilmagan</i>"
        )
        # welcome_message ni HTML escape qilamiz — ichida noto'g'ri teglar bo'lishi mumkin
        welcome_preview = _html.escape(contest.welcome_message) if contest.welcome_message else None
        text = (
            "🏆 <b>Aktiv Konkurs</b>\n\n"
            f"📛 Nom: <b>{contest.title}</b>\n"
            f"👥 Kerakli referral: <b>{contest.required_referrals} ta</b>\n"
            f"{prize_info}\n\n"
            "━━━━━━━━━━━━━━━━━━━\n"
            "📝 <b>Kirish xabari:</b>\n"
            f"{welcome_preview or '<i>belgilanmagan</i>'}"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Kirish xabari", callback_data="contest_edit_msg"),
                InlineKeyboardButton(text="🔢 Ref soni", callback_data="contest_edit_refs"),
            ],
            [
                InlineKeyboardButton(text="📣 Referral xabari", callback_data="contest_edit_referral_msg"),
            ],
            [
                InlineKeyboardButton(text="🎁 Prize kanal qo'shish", callback_data="contest_set_prize"),
            ],
            [
                InlineKeyboardButton(text="🗑 Konkursni tugatish", callback_data="contest_end"),
            ],
            [InlineKeyboardButton(text="🔙 Panel", callback_data="adm_back")],
        ])
    else:
        text = (
            "🏆 <b>Konkurs</b>\n\n"
            "⚠️ Hozircha hech qanday aktiv konkurs yo'q.\n\n"
            "Yangi konkurs yarating — foydalanuvchilar /start bosganida "
            "avtomatik ko'rinadi."
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Yangi konkurs yaratish", callback_data="contest_create")],
            [InlineKeyboardButton(text="🔙 Panel", callback_data="adm_back")],
        ])

    if edit and hasattr(target, 'message'):
        try:
            await target.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)
        except Exception:
            await target.message.answer(text, reply_markup=keyboard, disable_web_page_preview=True)
    elif edit:
        try:
            await target.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)
        except Exception:
            await target.answer(text, reply_markup=keyboard, disable_web_page_preview=True)
    else:
        msg = target.message if hasattr(target, 'message') else target
        await msg.answer(text, reply_markup=keyboard, disable_web_page_preview=True)


@router.message(Command("contest"))
async def cmd_contest(message: Message, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return
    await _show_contest_menu(message, db)


@router.callback_query(F.data == "adm_contest")
async def adm_contest_cb(callback: CallbackQuery, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        await callback.answer()
        return
    await callback.answer()  # ✅ BIRINCHI
    await _show_contest_menu(callback, db, edit=True)


# ── Konkurs yaratish ─────────────────────────────────────────────────────────
@router.callback_query(F.data == "contest_create")
async def contest_create_start(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return
    await callback.message.answer(
        "🏆 <b>Yangi Konkurs — 1-qadam</b>\n\n"
        "Konkurs nomini yuboring:\n"
        "<i>Masalan: Yozgi Konkurs 2025</i>\n\n"
        "/cancel — bekor qilish"
    )
    await state.set_state(ContestStates.waiting_title)
    await callback.answer()


@router.message(ContestStates.waiting_title)
async def contest_title(message: Message, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return
    title = message.text.strip()
    if len(title) < 2:
        await message.answer("❌ Nom juda qisqa. Qaytadan kiriting:")
        return
    await state.update_data(title=title)
    await message.answer(
        f"✅ Nom: <b>{title}</b>\n\n"
        "📝 <b>2-qadam:</b> Kirish xabarini yuboring\n\n"
        "Bu xabar foydalanuvchi /start bosganida <b>birinchi</b> ko'rinadi "
        "(majburiy kanallardan ham oldin).\n\n"
        "📸 <b>Rasm yuborish mumkin</b> — caption (matn) ham qo'shing yoki shunchaki rasm yuboring.\n"
        "HTML teglari ishlaydi: <b>bold</b>, <i>italic</i>, <code>code</code>\n\n"
        "/skip — xabarsiz davom etish"
    )
    await state.set_state(ContestStates.waiting_welcome)


@router.message(ContestStates.waiting_welcome)
async def contest_welcome(message: Message, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return

    welcome = None
    photo_file_id = None

    if message.text and message.text.strip() != "/skip":
        welcome = message.text.strip()
    elif message.photo:
        # Rasm + caption (ixtiyoriy)
        photo_file_id = message.photo[-1].file_id
        if message.caption and message.caption.strip() != "/skip":
            welcome = message.caption.strip()
    elif message.text and message.text.strip() == "/skip":
        pass  # welcome va photo_file_id = None qoladi

    await state.update_data(welcome=welcome, photo_file_id=photo_file_id)
    await message.answer(
        "✅ Xabar saqlandi!\n\n"
        "🔢 <b>3-qadam:</b> Nechta referral qilganda prize kanal berilsin?\n\n"
        "Raqam yuboring (masalan: <b>5</b>):"
    )
    await state.set_state(ContestStates.waiting_required_refs)


@router.message(ContestStates.waiting_required_refs)
async def contest_refs(message: Message, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return

    text = message.text.strip()
    if not text.isdigit() or int(text) < 1:
        await message.answer("❌ Faqat musbat son kiriting:")
        return

    required_refs = int(text)
    data = await state.get_data()

    contest_repo = ContestRepository(db)
    contest = await contest_repo.create_contest(
        title=data["title"],
        welcome_message=data.get("welcome"),
        welcome_photo_file_id=data.get("photo_file_id"),
        required_referrals=required_refs,
    )

    await state.clear()
    await message.answer(
        f"🎉 <b>Konkurs muvaffaqiyatli yaratildi!</b>\n\n"
        f"📛 Nom: <b>{contest.title}</b>\n"
        f"👥 Kerakli referral: <b>{contest.required_referrals} ta</b>\n\n"
        f"⚠️ Prize kanalini ham qo'shing! Admin paneldagi "
        f"<b>🎁 Prize kanal</b> bo'limidan qo'shing.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎁 Prize kanal qo'shish", callback_data="contest_set_prize")],
            [InlineKeyboardButton(text="🔙 Konkurs menyusi", callback_data="adm_contest")],
        ])
    )


# ── Kirish xabarini o'zgartirish ─────────────────────────────────────────────
class EditContestStates(StatesGroup):
    waiting_new_msg = State()
    waiting_new_refs = State()


@router.callback_query(F.data == "contest_edit_msg")
async def contest_edit_msg_start(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return
    await callback.message.answer(
        "✏️ <b>Yangi kirish xabarini yuboring:</b>\n\n"
        "HTML teglari: <b>bold</b>, <i>italic</i>, <code>code</code>\n"
        "/skip — xabarsiz"
    )
    await state.set_state(EditContestStates.waiting_new_msg)
    await callback.answer()


@router.message(EditContestStates.waiting_new_msg)
async def contest_save_new_msg(message: Message, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return
    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()
    if not contest:
        await message.answer("❌ Aktiv konkurs topilmadi.")
        await state.clear()
        return

    new_msg = None
    new_photo = None

    if message.text and message.text.strip() != "/skip":
        new_msg = message.text.strip()
    elif message.photo:
        new_photo = message.photo[-1].file_id
        if message.caption and message.caption.strip() != "/skip":
            new_msg = message.caption.strip()
    # /skip → ikkalasi ham None

    await contest_repo.update(contest.id, welcome_message=new_msg, welcome_photo_file_id=new_photo)
    await state.clear()
    await message.answer(
        "✅ Kirish xabari yangilandi!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Konkurs", callback_data="adm_contest")]
        ])
    )


@router.callback_query(F.data == "contest_edit_refs")
async def contest_edit_refs_start(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return
    await callback.message.answer(
        "🔢 <b>Yangi referral sonini kiriting:</b>\n"
        "(masalan: 10)"
    )
    await state.set_state(EditContestStates.waiting_new_refs)
    await callback.answer()


@router.message(EditContestStates.waiting_new_refs)
async def contest_save_new_refs(message: Message, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return
    text = message.text.strip()
    if not text.isdigit() or int(text) < 1:
        await message.answer("❌ Faqat musbat son:")
        return
    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()
    if not contest:
        await message.answer("❌ Aktiv konkurs topilmadi.")
        await state.clear()
        return
    await contest_repo.update(contest.id, required_referrals=int(text))
    await state.clear()
    await message.answer(
        f"✅ Referral soni yangilandi: <b>{text} ta</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Konkurs", callback_data="adm_contest")]
        ])
    )


# ── Konkursni tugatish ───────────────────────────────────────────────────────
@router.callback_query(F.data == "contest_end")
async def contest_end_confirm(callback: CallbackQuery, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha, tugatish", callback_data="contest_end_confirm"),
            InlineKeyboardButton(text="❌ Bekor", callback_data="adm_contest"),
        ]
    ])
    await callback.message.edit_text(
        "⚠️ <b>Konkursni tugatmoqchimisiz?</b>\n\n"
        "Foydalanuvchilar /start bosganida «Hozircha konkurs yo'q» "
        "xabari chiqadi.",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data == "contest_end_confirm")
async def contest_end_execute(callback: CallbackQuery, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return
    contest_repo = ContestRepository(db)
    await contest_repo.deactivate_all()
    await callback.message.edit_text(
        "✅ <b>Konkurs tugatildi.</b>\n\n"
        "Foydalanuvchilar endi «Hozircha konkurs yo'q» xabarini ko'radi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Panel", callback_data="adm_back")]
        ])
    )
    await callback.answer()


# ── Prize kanal ──────────────────────────────────────────────────────────────
@router.callback_query(F.data == "adm_prize")
async def adm_prize_cb(callback: CallbackQuery, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return
    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()

    if not contest:
        await callback.answer("❌ Avval konkurs yarating!", show_alert=True)
        return

    if contest.prize_channel_id:
        text = (
            "🎁 <b>Prize Kanal</b>\n\n"
            f"📛 Kanal: <b>{contest.prize_channel_title}</b>\n"
            f"🆔 ID: <code>{contest.prize_channel_id}</code>\n\n"
            "Bot bu kanalda <b>admin</b> bo'lishi va link yaratish "
            "huquqiga ega bo'lishi shart!\n\n"
            "Kanal muvaffaqiyatli qilgan userlarga avtomatik "
            "1 martalik link yuboriladi."
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Kanalga o'zgartirish", callback_data="contest_set_prize")],
            [InlineKeyboardButton(text="🔙 Konkurs", callback_data="adm_contest")],
        ])
    else:
        text = (
            "🎁 <b>Prize Kanal</b>\n\n"
            "⚠️ Prize kanal hali qo'shilmagan.\n\n"
            "Kanal ID sini yuboring. Bot o'sha kanalda "
            "<b>admin</b> bo'lishi shart!"
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="contest_set_prize")],
            [InlineKeyboardButton(text="🔙 Konkurs", callback_data="adm_contest")],
        ])

    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "contest_set_prize")
async def contest_set_prize_start(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return
    await callback.message.answer(
        "🎁 <b>Prize Kanal qo'shish</b>\n\n"
        "Kanal ID sini yuboring:\n"
        "<code>-1001234567890</code>\n\n"
        "⚠️ <b>Muhim:</b> Bot bu kanalda admin va "
        "«Invite Links yaratish» huquqiga ega bo'lishi shart!\n\n"
        "/cancel — bekor qilish"
    )
    await state.set_state(PrizeChannelStates.waiting_channel)
    await callback.answer()


@router.message(PrizeChannelStates.waiting_channel)
async def contest_prize_channel_save(message: Message, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return

    text = message.text.strip()

    # ID yoki @username
    channel_id = None
    identifier = None

    if text.startswith("@"):
        identifier = text
    elif text.lstrip("-").isdigit():
        channel_id = int(text)
        identifier = channel_id
    else:
        await message.answer(
            "❌ Noto'g'ri format.\n\n"
            "Kanal ID (<code>-1001234567890</code>) yoki "
            "@username yuboring:"
        )
        return

    try:
        chat = await message.bot.get_chat(identifier)
    except Exception as e:
        await message.answer(
            f"❌ Kanal topilmadi:\n<code>{e}</code>\n\n"
            "Botni kanalga admin qilganingizga ishonch hosil qiling!"
        )
        return

    # Bot admin ekanligini tekshirish
    try:
        bot_member = await message.bot.get_chat_member(chat.id, (await message.bot.get_me()).id)
        if bot_member.status not in ("administrator", "creator"):
            await message.answer(
                "❌ Bot bu kanalda admin emas!\n\n"
                "Botni kanalga admin qiling va qaytadan urinib ko'ring."
            )
            return
    except Exception:
        pass  # Ba'zi kanallarda tekshirish ishlamaydi

    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()
    if not contest:
        await message.answer("❌ Aktiv konkurs topilmadi. Avval konkurs yarating!")
        await state.clear()
        return

    await contest_repo.set_prize_channel(
        contest_id=contest.id,
        channel_id=chat.id,
        channel_title=chat.title or "Prize Kanal",
    )

    await state.clear()
    await message.answer(
        f"✅ <b>Prize kanal qo'shildi!</b>\n\n"
        f"📛 Kanal: <b>{chat.title}</b>\n"
        f"🆔 ID: <code>{chat.id}</code>\n\n"
        f"Endi foydalanuvchilar <b>{contest.required_referrals} ta</b> referral "
        f"qilganda avtomatik 1 martalik link oladi! 🎉",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Konkurs", callback_data="adm_contest")]
        ])
    )


# ── Referral xabari (yangi do'st qo'shilganda boradigan matn) ────────────────
class ReferralMsgStates(StatesGroup):
    waiting_msg = State()


@router.callback_query(F.data == "contest_edit_referral_msg")
async def edit_referral_msg_start(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return
    await callback.answer()
    await callback.message.answer(
        "✏️ <b>Referral xabarini o'zgartirish</b>\n\n"
        "Bu xabar yangi do'st qo'shilganda referrerga yuboriladi.\n"
        "Xabar ostida avtomatik <b>konkurs ma'lumoti</b> va <b>taklif tugmasi</b> qo'shiladi.\n\n"
        "Faqat Telegram HTML teglari: <b>bold</b>, <i>italic</i>, <code>code</code>\n\n"
        "/skip — xabarsiz (faqat konkurs ma'lumoti chiqadi)\n"
        "/cancel — bekor qilish"
    )
    await state.set_state(ReferralMsgStates.waiting_msg)


@router.message(ReferralMsgStates.waiting_msg)
async def save_referral_msg(message: Message, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return
    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()
    if not contest:
        await message.answer("❌ Aktiv konkurs topilmadi.")
        await state.clear()
        return

    txt = (message.text or "").strip()
    new_msg = None if txt == "/skip" else txt
    await contest_repo.update(contest.id, referral_message=new_msg)
    await state.clear()
    await message.answer(
        "✅ Referral xabari yangilandi!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Konkurs", callback_data="adm_contest")]
        ])
    )
