"""
User → Adminlarga xabar yuborish.

/contact yoki "✉️ Admin" tugmasi orqali user adminlarga xabar yuboradi.
Barcha adminlarga (settings.ADMIN_IDS + DB adminlar) xabar boradi.
Admin reply qila oladi — reply user ID inline buttondan olinadi.
"""
import logging

from aiogram import Router, F, Bot
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.admin_repo import AdminRepository
from app.bot.handlers.user.utils import safe_answer

logger = logging.getLogger(__name__)
router = Router()


class ContactAdminStates(StatesGroup):
    waiting_message = State()


@router.message(Command("contact"))
@router.callback_query(F.data == "contact_admin")
async def start_contact(event: Message | CallbackQuery, state: FSMContext, db: AsyncSession):
    if isinstance(event, CallbackQuery):
        await safe_answer(event)
        msg = event.message
    else:
        msg = event

    await msg.answer(
        "✉️ <b>Adminlarga xabar yuborish</b>\n\n"
        "Xabaringizni yozing (matn, rasm, video — istalgan format):\n\n"
        "/cancel — bekor qilish"
    )
    await state.set_state(ContactAdminStates.waiting_message)


@router.message(ContactAdminStates.waiting_message)
async def send_to_admins(message: Message, state: FSMContext, bot: Bot, db: AsyncSession):
    await state.clear()

    user = message.from_user
    user_info = (
        f"👤 <b>Foydalanuvchi:</b> {user.full_name}\n"
        f"🆔 ID: <code>{user.id}</code>\n"
        f"📛 Username: {'@' + user.username if user.username else '—'}"
    )

    # Barcha adminlar (settings + DB)
    admin_repo = AdminRepository(db)
    db_admins = await admin_repo.get_all_admins()
    db_admin_ids = [a.telegram_id for a in db_admins]
    all_admin_ids = list(set(list(settings.ADMIN_IDS) + db_admin_ids))

    # Inline button: reply uchun user_id
    reply_keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"↩️ Javob berish → {user.full_name}",
            callback_data=f"admin_reply:{user.id}",
        )
    ]])

    sent = 0
    for admin_id in all_admin_ids:
        try:
            # Avval user info yuboramiz
            await bot.send_message(
                chat_id=admin_id,
                text=f"📩 <b>Yangi xabar</b>\n\n{user_info}",
                parse_mode="HTML",
                reply_markup=reply_keyboard,
            )
            # Keyin xabarning o'zini forward qilamiz
            await bot.forward_message(
                chat_id=admin_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            sent += 1
        except Exception as e:
            logger.error(f"Admin {admin_id} ga xabar yuborilmadi: {e}")

    if sent > 0:
        await message.answer(
            "✅ Xabaringiz adminlarga yuborildi!\n"
            "Tez orada javob berishadi."
        )
    else:
        await message.answer(
            "❌ Xabar yuborishda xatolik yuz berdi. Keyinroq urinib ko'ring."
        )


# ── Admin reply callback ─────────────────────────────────────────────────────
class AdminReplyStates(StatesGroup):
    waiting_reply = State()


@router.callback_query(F.data.startswith("admin_reply:"))
async def admin_reply_start(callback: CallbackQuery, state: FSMContext, db: AsyncSession):
    from app.bot.handlers.admin.base import is_admin_async
    if not await is_admin_async(callback.from_user.id, db):
        await callback.answer("❌ Ruxsat yo'q", show_alert=True)
        return

    user_id = int(callback.data.split(":")[1])
    await state.update_data(reply_to_user_id=user_id)
    await callback.message.answer(
        f"✍️ <b>User {user_id} ga javob yozasiz.</b>\n\n"
        "Javobingizni yuboring (matn, rasm va h.k.):\n\n"
        "/cancel — bekor qilish"
    )
    await state.set_state(AdminReplyStates.waiting_reply)
    await safe_answer(callback)


@router.message(AdminReplyStates.waiting_reply)
async def admin_send_reply(message: Message, state: FSMContext, bot: Bot, db: AsyncSession):
    from app.bot.handlers.admin.base import is_admin_async
    if not await is_admin_async(message.from_user.id, db):
        return

    data = await state.get_data()
    user_id = data.get("reply_to_user_id")
    await state.clear()

    if not user_id:
        await message.answer("❌ Xatolik: user ID topilmadi.")
        return

    admin_name = message.from_user.full_name or "Admin"
    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"📨 <b>Admin javobi ({admin_name}):</b>",
            parse_mode="HTML",
        )
        await bot.copy_message(
            chat_id=user_id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        await message.answer("✅ Javob yuborildi!")
    except Exception as e:
        await message.answer(f"❌ Yuborishda xato: {e}")
