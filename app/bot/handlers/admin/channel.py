"""
Majburiy kanallar boshqaruvi
• Public/Private/Yashirin — har qanday kanal qabul qilinadi
• Yashirin kanal invite_link bilan saqlanadi
"""
import re

from aiogram import F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.admin.base import admin_router, is_admin_async, admin_main_keyboard
from app.repositories.channel_repo import ChannelRepository

router = admin_router


class AddChannelStates(StatesGroup):
    waiting_for_channel = State()
    waiting_for_invite_link = State()  # Yashirin kanal uchun


# ── Kanallar ro'yxati ────────────────────────────────────────────────────────
@router.message(Command("channels"))
async def cmd_channels(message: Message, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return
    await _show_channels_list(message, db)


@router.callback_query(F.data == "adm_channels")
async def adm_channels_callback(callback: CallbackQuery, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return
    await _show_channels_list_edit(callback, db)


async def _show_channels_list(message: Message, db: AsyncSession):
    channel_repo = ChannelRepository(db)
    channels = await channel_repo.get_all_channels()

    if not channels:
        text = "📋 <b>Majburiy Kanallar</b>\n\nHech qanday kanal qo'shilmagan."
    else:
        text = f"📋 <b>Majburiy Kanallar</b> ({len(channels)} ta)\n\n"
        for ch in channels:
            status = "✅" if ch.is_required else "⏸"
            uname = f"@{ch.username}" if ch.username else "🔒 Yashirin"
            text += f"{status} <b>{ch.title}</b> ({uname})\n"

    buttons = []
    for ch in channels:
        lock = "🔒 " if not ch.username else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 {lock}{ch.title}",
                callback_data=f"del_channel:{ch.id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_channel_start")])
    buttons.append([InlineKeyboardButton(text="🔙 Panel", callback_data="adm_back")])

    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


async def _show_channels_list_edit(callback: CallbackQuery, db: AsyncSession):
    channel_repo = ChannelRepository(db)
    channels = await channel_repo.get_all_channels()

    if not channels:
        text = "📋 <b>Majburiy Kanallar</b>\n\nHech qanday kanal qo'shilmagan."
    else:
        text = f"📋 <b>Majburiy Kanallar</b> ({len(channels)} ta)\n\n"
        for ch in channels:
            status = "✅" if ch.is_required else "⏸"
            uname = f"@{ch.username}" if ch.username else "🔒 Yashirin"
            text += f"{status} <b>{ch.title}</b> ({uname})\n"

    buttons = []
    for ch in channels:
        lock = "🔒 " if not ch.username else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 {lock}{ch.title}",
                callback_data=f"del_channel:{ch.id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="add_channel_start")])
    buttons.append([InlineKeyboardButton(text="🔙 Panel", callback_data="adm_back")])

    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()


# ── Kanal qo'shish — UNIVERSAL (public va private) ───────────────────────────
@router.message(Command("addchannel"))
async def cmd_addchannel(message: Message, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return
    await _start_add_channel(message, state)


@router.callback_query(F.data == "add_channel_start")
async def add_channel_start(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return
    await _start_add_channel(callback.message, state)
    await callback.answer()


async def _start_add_channel(message: Message, state: FSMContext):
    await message.answer(
        "➕ <b>Kanal Qo'shish</b>\n\n"
        "Quyidagilardan birini yuboring:\n\n"
        "📢 <b>Ochiq kanal:</b>\n"
        "• <code>@username</code>\n"
        "• <code>https://t.me/kanal_nomi</code>\n\n"
        "🔒 <b>Yashirin kanal:</b>\n"
        "• <code>-1001234567890</code> (kanal ID)\n"
        "• <code>https://t.me/+AbCdEf123456</code> (invite link)\n\n"
        "⚠️ Bot kanalda <b>admin</b> bo'lishi shart!\n\n"
        "/cancel — bekor qilish"
    )
    await state.set_state(AddChannelStates.waiting_for_channel)


@router.message(AddChannelStates.waiting_for_channel)
async def process_add_channel(message: Message, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return

    text = message.text.strip()
    identifier = None
    invite_link = None
    is_private = False

    # Invite link (yashirin kanal) — https://t.me/+ yoki https://t.me/joinchat
    if "t.me/+" in text or "t.me/joinchat" in text:
        invite_link = text if text.startswith("http") else f"https://{text}"
        # Bot bu kanalga invite link orqali kira olmaydi, kanal ID kerak
        await state.update_data(invite_link=invite_link)
        await message.answer(
            "🔒 <b>Yashirin kanal — Kanal ID ham kerak</b>\n\n"
            "Kanal ID sini yuboring:\n"
            "<code>-1001234567890</code>\n\n"
            "ID ni olish: @userinfobot ga kanaldan biror xabar forward qiling."
        )
        await state.set_state(AddChannelStates.waiting_for_invite_link)
        return

    # @username
    elif text.startswith("@"):
        identifier = text

    # https://t.me/username (oddiy link)
    elif re.match(r"https?://t\.me/[a-zA-Z0-9_]+$", text):
        match = re.search(r"t\.me/([a-zA-Z0-9_]+)", text)
        if match:
            identifier = f"@{match.group(1)}"

    # Kanal ID
    elif re.match(r"^-?100\d+$", text):
        identifier = int(text)
        is_private = True

    else:
        await message.answer(
            "❌ Format noto'g'ri.\n\n"
            "Qabul qilinadigan formatlar:\n"
            "• <code>@kanal_username</code>\n"
            "• <code>https://t.me/kanal</code>\n"
            "• <code>https://t.me/+InviteHash</code>\n"
            "• <code>-1001234567890</code>"
        )
        return

    try:
        chat = await message.bot.get_chat(identifier)
    except Exception as e:
        await message.answer(
            f"❌ Kanal topilmadi:\n<code>{e}</code>\n\n"
            "Botni kanalga admin qilib, qaytadan urinib ko'ring!"
        )
        return

    if chat.type not in ("channel", "supergroup"):
        await message.answer("❌ Bu kanal yoki supergroup emas!")
        return

    channel_repo = ChannelRepository(db)
    existing = await channel_repo.get_by_channel_id(chat.id)
    if existing:
        await message.answer(
            f"⚠️ <b>{chat.title}</b> allaqachon bazada mavjud.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📋 Kanallar", callback_data="adm_channels")]
            ])
        )
        await state.clear()
        return

    # Yashirin kanal bo'lsa invite_link avtomatik olamiz (bot admin bo'lsa)
    auto_invite = None
    if not chat.username:
        try:
            link_obj = await message.bot.create_chat_invite_link(chat.id)
            auto_invite = link_obj.invite_link
        except Exception:
            pass  # Agar olmasa, keyinroq qo'shiladi

    channel = await channel_repo.create(
        channel_id=chat.id,
        username=chat.username,
        title=chat.title or "Nomsiz Kanal",
        is_active=True,
        is_required=True,
        description=getattr(chat, "description", None),
        invite_link=auto_invite,
    )

    is_secret = not channel.username
    await message.answer(
        f"✅ <b>Kanal muvaffaqiyatli qo'shildi!</b>\n\n"
        f"📛 Nomi: <b>{channel.title}</b>\n"
        f"{'🔒 Yashirin kanal' if is_secret else f'🔗 @{channel.username}'}\n"
        f"🆔 ID: <code>{channel.channel_id}</code>"
        + (f"\n🔗 Invite: <code>{auto_invite}</code>" if auto_invite else ""),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Kanallar", callback_data="adm_channels")]
        ])
    )
    await state.clear()


@router.message(AddChannelStates.waiting_for_invite_link)
async def process_channel_with_invite(message: Message, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return

    data = await state.get_data()
    invite_link = data.get("invite_link")
    text = message.text.strip()

    if not re.match(r"^-?100\d+$", text):
        await message.answer("❌ Faqat kanal ID yuboring (masalan: <code>-1001234567890</code>):")
        return

    channel_id = int(text)

    try:
        chat = await message.bot.get_chat(channel_id)
    except Exception as e:
        await message.answer(f"❌ Kanal topilmadi:\n<code>{e}</code>")
        await state.clear()
        return

    channel_repo = ChannelRepository(db)
    existing = await channel_repo.get_by_channel_id(chat.id)
    if existing:
        await message.answer("⚠️ Bu kanal allaqachon bazada mavjud.")
        await state.clear()
        return

    channel = await channel_repo.create(
        channel_id=chat.id,
        username=None,
        title=chat.title or "Yashirin Kanal",
        is_active=True,
        is_required=True,
        description=None,
        invite_link=invite_link,
    )

    await state.clear()
    await message.answer(
        f"✅ <b>Yashirin kanal qo'shildi!</b>\n\n"
        f"📛 Nomi: <b>{channel.title}</b>\n"
        f"🔒 Yashirin kanal\n"
        f"🆔 ID: <code>{channel.channel_id}</code>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📋 Kanallar", callback_data="adm_channels")]
        ])
    )


# ── Kanal o'chirish ──────────────────────────────────────────────────────────
@router.callback_query(F.data.startswith("del_channel:"))
async def delete_channel_callback(callback: CallbackQuery, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return

    channel_id = int(callback.data.split(":")[1])
    channel_repo = ChannelRepository(db)
    channel = await channel_repo.get(channel_id)

    if not channel:
        await callback.answer("❌ Kanal topilmadi.", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Ha, o'chirish", callback_data=f"confirm_del_channel:{channel_id}"),
            InlineKeyboardButton(text="❌ Bekor", callback_data="adm_channels"),
        ]
    ])
    await callback.message.answer(
        f"⚠️ <b>Rostdan ham o'chirmoqchimisiz?</b>\n\n📛 <b>{channel.title}</b>",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del_channel:"))
async def confirm_delete_channel(callback: CallbackQuery, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return

    channel_id = int(callback.data.split(":")[1])
    channel_repo = ChannelRepository(db)
    channel = await channel_repo.get(channel_id)

    if not channel:
        await callback.answer("❌ Topilmadi.", show_alert=True)
        return

    title = channel.title
    await channel_repo.delete(channel_id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Kanallar", callback_data="adm_channels")]
    ])
    await callback.message.edit_text(f"🗑 <b>{title}</b> o'chirildi.", reply_markup=keyboard)
    await callback.answer()
