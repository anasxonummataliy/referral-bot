"""
Sovg'a (maxfiy) kanallarini boshqarish — eski tizim
Admin /giftchannel buyrug'i orqali qo'shadi va o'chiradi
"""
from aiogram import F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.admin.base import admin_router, is_admin_async
from app.repositories.secret_channel_repo import SecretChannelRepository

router = admin_router


class GiftChannelStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_link = State()
    waiting_for_min_referrals = State()


async def _show_gift_channels_menu(message: Message, db: AsyncSession):
    secret_repo = SecretChannelRepository(db)
    channels = await secret_repo.get_all_gift_channels()

    if not channels:
        text = (
            "🎁 <b>Qo'shimcha Sovg'a Kanallar</b>\n\n"
            "Hozircha hech qanday qo'shimcha sovg'a kanal qo'shilmagan.\n\n"
            "<i>Asosiy prize kanal — Konkurs bo'limida boshqariladi.</i>"
        )
    else:
        text = f"🎁 <b>Qo'shimcha Sovg'a Kanallar</b> ({len(channels)} ta)\n\n"
        for ch in channels:
            status = "✅" if ch.is_active else "⏸"
            text += f"{status} <b>{ch.title}</b> — {ch.min_referrals}+ referral\n"

    buttons = []
    for ch in channels:
        buttons.append([
            InlineKeyboardButton(
                text=f"{'✅' if ch.is_active else '⏸'} {ch.title} ({ch.min_referrals} ref)",
                callback_data=f"gift_detail:{ch.id}"
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="➕ Qo'shimcha sovg'a kanal qo'shish", callback_data="add_gift_channel")
    ])
    buttons.append([InlineKeyboardButton(text="🔙 Panel", callback_data="adm_back")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=keyboard, disable_web_page_preview=True)


@router.message(Command("giftchannel"))
async def cmd_gift_channels(message: Message, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return
    await _show_gift_channels_menu(message, db)


@router.callback_query(F.data == "adm_gifts")
async def adm_gifts_cb(callback: CallbackQuery, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return
    await _show_gift_channels_menu(callback.message, db)
    await callback.answer()


@router.callback_query(F.data.startswith("gift_detail:"))
async def gift_channel_detail(callback: CallbackQuery, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return

    channel_id = int(callback.data.split(":")[1])
    secret_repo = SecretChannelRepository(db)
    channel = await secret_repo.get(channel_id)

    if not channel:
        await callback.answer("❌ Kanal topilmadi.", show_alert=True)
        return

    status = "✅ Faol" if channel.is_active else "⏸ Nofaol"
    text = (
        f"🎁 <b>Sovg'a Kanal</b>\n\n"
        f"📛 Nomi: <b>{channel.title}</b>\n"
        f"🔗 Havola: <code>{channel.link}</code>\n"
        f"👥 Minimal referral: <b>{channel.min_referrals}</b>\n"
        f"📊 Holat: {status}"
    )

    toggle_text = "⏸ Nofaol qilish" if channel.is_active else "✅ Faol qilish"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_gift:{channel_id}"),
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"del_gift:{channel_id}"),
        ],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_gift_list")],
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(F.data.startswith("toggle_gift:"))
async def toggle_gift_channel(callback: CallbackQuery, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return
    channel_id = int(callback.data.split(":")[1])
    secret_repo = SecretChannelRepository(db)
    channel = await secret_repo.get(channel_id)
    if not channel:
        await callback.answer("❌ Topilmadi.", show_alert=True)
        return
    new_status = not channel.is_active
    await secret_repo.update(channel_id, is_active=new_status)
    await callback.answer("✅ Yangilandi!", show_alert=False)
    channel = await secret_repo.get(channel_id)
    status = "✅ Faol" if channel.is_active else "⏸ Nofaol"
    toggle_text = "⏸ Nofaol qilish" if channel.is_active else "✅ Faol qilish"
    text = (
        f"🎁 <b>Sovg'a Kanal</b>\n\n"
        f"📛 Nomi: <b>{channel.title}</b>\n"
        f"🔗 Havola: <code>{channel.link}</code>\n"
        f"👥 Minimal referral: <b>{channel.min_referrals}</b>\n"
        f"📊 Holat: {status}"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=toggle_text, callback_data=f"toggle_gift:{channel_id}"),
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"del_gift:{channel_id}"),
        ],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_to_gift_list")],
    ])
    await callback.message.edit_text(text, reply_markup=keyboard, disable_web_page_preview=True)


@router.callback_query(F.data.startswith("del_gift:"))
async def delete_gift_channel(callback: CallbackQuery, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return
    channel_id = int(callback.data.split(":")[1])
    secret_repo = SecretChannelRepository(db)
    channel = await secret_repo.get(channel_id)
    if not channel:
        await callback.answer("❌ Topilmadi.", show_alert=True)
        return
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Ha", callback_data=f"confirm_del_gift:{channel_id}"),
        InlineKeyboardButton(text="❌ Bekor", callback_data=f"gift_detail:{channel_id}"),
    ]])
    await callback.message.edit_text(
        f"⚠️ <b>O'chirishni tasdiqlaysizmi?</b>\n\n🎁 <b>{channel.title}</b>",
        reply_markup=keyboard,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_del_gift:"))
async def confirm_delete_gift(callback: CallbackQuery, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return
    channel_id = int(callback.data.split(":")[1])
    secret_repo = SecretChannelRepository(db)
    channel = await secret_repo.get(channel_id)
    if not channel:
        await callback.answer("❌ Topilmadi.", show_alert=True)
        return
    title = channel.title
    await secret_repo.delete(channel_id)
    await callback.message.edit_text(
        f"🗑 <b>{title}</b> o'chirildi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔙 Ro'yxat", callback_data="back_to_gift_list")
        ]])
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_gift_list")
async def back_to_gift_list(callback: CallbackQuery, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return
    await _show_gift_channels_menu(callback.message, db)
    await callback.answer()


@router.callback_query(F.data == "add_gift_channel")
async def start_add_gift_channel(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return
    await callback.message.answer(
        "➕ <b>Qo'shimcha sovg'a kanal qo'shish</b>\n\n"
        "<b>1-qadam:</b> Kanal nomini yuboring:\n\n"
        "Bekor qilish: /cancel"
    )
    await state.set_state(GiftChannelStates.waiting_for_title)
    await callback.answer()


@router.message(GiftChannelStates.waiting_for_title)
async def process_gift_title(message: Message, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return
    title = message.text.strip()
    if len(title) < 2:
        await message.answer("❌ Nom juda qisqa:")
        return
    await state.update_data(title=title)
    await message.answer(
        f"✅ Nomi: <b>{title}</b>\n\n"
        f"<b>2-qadam:</b> Kanal havolasini yuboring:\n"
        f"(masalan: https://t.me/+AbCdEf123456)"
    )
    await state.set_state(GiftChannelStates.waiting_for_link)


@router.message(GiftChannelStates.waiting_for_link)
async def process_gift_link(message: Message, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return
    link = message.text.strip()
    if not (link.startswith("https://") or link.startswith("http://") or link.startswith("t.me/")):
        await message.answer("❌ Noto'g'ri havola formati.")
        return
    await state.update_data(link=link)
    await message.answer(
        f"✅ Havola saqlandi.\n\n"
        f"<b>3-qadam:</b> Minimal referral sonini kiriting:\n"
        f"(masalan: 10)"
    )
    await state.set_state(GiftChannelStates.waiting_for_min_referrals)


@router.message(GiftChannelStates.waiting_for_min_referrals)
async def process_gift_min_referrals(message: Message, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return
    text = message.text.strip()
    if not text.isdigit() or int(text) < 1:
        await message.answer("❌ Faqat musbat son kiriting:")
        return
    min_referrals = int(text)
    data = await state.get_data()
    secret_repo = SecretChannelRepository(db)
    channel = await secret_repo.create(
        title=data["title"],
        link=data["link"],
        min_referrals=min_referrals,
        is_active=True,
    )
    await state.clear()
    await message.answer(
        f"✅ <b>Sovg'a kanal qo'shildi!</b>\n\n"
        f"📛 Nomi: <b>{channel.title}</b>\n"
        f"👥 Minimal referral: <b>{channel.min_referrals}</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📋 Ro'yxat", callback_data="back_to_gift_list")
        ]]),
        disable_web_page_preview=True,
    )
