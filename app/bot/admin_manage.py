"""
Admin boshqaruvi
• Yangi admin qo'shish (TG ID yoki @username)
• Admin o'chirish
"""
from aiogram import F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.admin.base import (
    admin_router, is_admin_async, add_to_cache, remove_from_cache
)
from app.repositories.admin_repo import AdminRepository
from app.core.config import settings

router = admin_router


class AdminManageStates(StatesGroup):
    waiting_new_admin = State()
    waiting_remove_admin = State()


# ── Admin ro'yxati ───────────────────────────────────────────────────────────
async def _show_admins_menu(target, db: AsyncSession, edit: bool = False):
    admin_repo = AdminRepository(db)
    db_admins = await admin_repo.get_all_admins()

    text = "🔑 <b>Adminlar</b>\n\n"
    text += "📌 <b>Asosiy adminlar (.env):</b>\n"
    for aid in settings.ADMIN_IDS:
        text += f"  • <code>{aid}</code>\n"

    if db_admins:
        text += "\n👥 <b>Qo'shilgan adminlar:</b>\n"
        for a in db_admins:
            uname = f"@{a.username}" if a.username else a.full_name or "—"
            text += f"  • {uname} <code>{a.telegram_id}</code>\n"
    else:
        text += "\n👥 <b>Qo'shilgan adminlar:</b> <i>yo'q</i>\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Admin qo'shish", callback_data="admin_add")],
        [InlineKeyboardButton(text="🗑 Admin o'chirish", callback_data="admin_remove")],
        [InlineKeyboardButton(text="🔙 Panel", callback_data="adm_back")],
    ])

    if edit and hasattr(target, 'message'):
        try:
            await target.message.edit_text(text, reply_markup=keyboard)
        except Exception:
            await target.message.answer(text, reply_markup=keyboard)
    elif edit:
        try:
            await target.edit_text(text, reply_markup=keyboard)
        except Exception:
            await target.answer(text, reply_markup=keyboard)
    else:
        msg = target.message if hasattr(target, 'message') else target
        await msg.answer(text, reply_markup=keyboard)


@router.message(Command("admins"))
async def cmd_admins(message: Message, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return
    await _show_admins_menu(message, db)


@router.callback_query(F.data == "adm_admins")
async def adm_admins_cb(callback: CallbackQuery, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return
    await _show_admins_menu(callback, db, edit=True)
    await callback.answer()


# ── Admin qo'shish ───────────────────────────────────────────────────────────
@router.callback_query(F.data == "admin_add")
async def admin_add_start(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return
    await callback.message.answer(
        "➕ <b>Yangi Admin Qo'shish</b>\n\n"
        "Telegram ID yoki @username yuboring:\n\n"
        "<i>Masalan:</i>\n"
        "• <code>123456789</code>\n"
        "• <code>@username</code>\n\n"
        "/cancel — bekor qilish"
    )
    await state.set_state(AdminManageStates.waiting_new_admin)
    await callback.answer()


@router.message(AdminManageStates.waiting_new_admin)
async def admin_add_process(message: Message, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return

    text = message.text.strip()
    user_id = None
    username = None
    full_name = None

    try:
        if text.startswith("@"):
            # Username orqali
            try:
                chat = await message.bot.get_chat(text)
                user_id = chat.id
                username = chat.username
                full_name = getattr(chat, 'full_name', None) or getattr(chat, 'title', None)
            except Exception:
                await message.answer(
                    f"❌ <code>{text}</code> foydalanuvchisi topilmadi.\n\n"
                    "Ular botni ishga tushirgan bo'lishi kerak."
                )
                return
        elif text.lstrip("-").isdigit():
            user_id = int(text)
            # Bazadan ismni olishga harakat
            from app.repositories.user_repo import UserRepository
            user_repo = UserRepository(db)
            existing_user = await user_repo.get_by_telegram_id(user_id)
            if existing_user:
                username = existing_user.username
                full_name = existing_user.full_name
        else:
            await message.answer("❌ Noto'g'ri format. Telegram ID yoki @username yuboring:")
            return

        # .env adminlarini qayta qo'shib bo'lmaydi
        if user_id in settings.ADMIN_IDS:
            await message.answer("⚠️ Bu foydalanuvchi allaqachon asosiy admin (.env)!")
            await state.clear()
            return

        admin_repo = AdminRepository(db)
        admin = await admin_repo.add_admin(
            telegram_id=user_id,
            username=username,
            full_name=full_name,
        )
        add_to_cache(user_id)

        # Yangi adminga ham commandlarni o'rnatish
        try:
            from app.bot.commands import ADMIN_COMMANDS
            from aiogram.types import BotCommandScopeChat
            await message.bot.set_my_commands(
                commands=ADMIN_COMMANDS,
                scope=BotCommandScopeChat(chat_id=user_id),
            )
        except Exception as cmd_err:
            import logging
            logging.getLogger(__name__).warning(f"Admin command o'rnatilmadi {user_id}: {cmd_err}")

        display = f"@{username}" if username else full_name or str(user_id)
        await state.clear()
        await message.answer(
            f"✅ <b>{display}</b> admin sifatida qo'shildi!\n\n"
            f"🆔 ID: <code>{user_id}</code>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Adminlar", callback_data="adm_admins")]
            ])
        )

    except Exception as e:
        await message.answer(f"❌ Xatolik: <code>{e}</code>")
        await state.clear()


# ── Admin o'chirish ──────────────────────────────────────────────────────────
@router.callback_query(F.data == "admin_remove")
async def admin_remove_start(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return

    admin_repo = AdminRepository(db)
    db_admins = await admin_repo.get_all_admins()

    if not db_admins:
        await callback.answer("Hozircha qo'shilgan admin yo'q.", show_alert=True)
        return

    buttons = []
    for a in db_admins:
        display = f"@{a.username}" if a.username else a.full_name or str(a.telegram_id)
        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 {display}",
                callback_data=f"admin_del:{a.telegram_id}"
            )
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_admins")])

    await callback.message.edit_text(
        "🗑 <b>Qaysi adminni o'chirish?</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin_del:"))
async def admin_delete_confirm(callback: CallbackQuery, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return

    target_id = int(callback.data.split(":")[1])

    # .env adminini o'chirib bo'lmaydi
    if target_id in settings.ADMIN_IDS:
        await callback.answer("❌ Asosiy admin (.env) o'chirib bo'lmaydi!", show_alert=True)
        return

    admin_repo = AdminRepository(db)
    await admin_repo.remove_admin(target_id)
    remove_from_cache(target_id)

    await callback.message.edit_text(
        f"✅ Admin <code>{target_id}</code> o'chirildi.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Adminlar", callback_data="adm_admins")]
        ])
    )
    await callback.answer()
