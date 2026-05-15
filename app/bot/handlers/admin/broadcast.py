# bot/handlers/admin/broadcast.py
from aiogram import F, Router
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from .base import admin_router, is_admin
from repositories.user_repo import UserRepository

router = admin_router


class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    confirm = State()


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "📢 <b>Broadcast xabar yuborish</b>\n\n"
        "Endi foydalanuvchilarga yubormoqchi bo‘lgan xabarni yuboring "
        "(matn, rasm, video, h.k.).\n\n"
        "Bekor qilish uchun: /cancel"
    )
    await state.set_state(BroadcastStates.waiting_for_message)


@router.message(BroadcastStates.waiting_for_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    # Xabarni saqlab qo'yamiz
    await state.update_data(broadcast_message=message)

    text = (
        "❓ <b>Xabarni tasdiqlaysizmi?</b>\n\n"
        f"Foydalanuvchilar soni: <b>{await get_user_count(message.bot)}</b>\n\n"
        "✅ Yuborish uchun: <b>Ha</b>\n"
        "❌ Bekor qilish uchun: <b>Yo‘q</b> yoki /cancel"
    )

    await message.answer(text)
    await state.set_state(BroadcastStates.confirm)


@router.message(BroadcastStates.confirm, F.text.lower().in_(["ha", "yes", "✅"]))
async def confirm_broadcast(message: Message, state: FSMContext, db: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    broadcast_msg: Message = data.get("broadcast_message")

    if not broadcast_msg:
        await message.answer("Xatolik yuz berdi.")
        await state.clear()
        return

    user_repo = UserRepository(db)
    all_users = await user_repo.get_all()  # yoki limit bilan olish tavsiya qilinadi

    success = 0
    failed = 0

    await message.answer(
        f"📤 Broadcast boshlandi... Jami {len(all_users)} ta foydalanuvchiga yuborilmoqda."
    )

    for user in all_users:
        try:
            await broadcast_msg.copy_to(
                chat_id=user.telegram_id,
                caption=broadcast_msg.caption,
                parse_mode=broadcast_msg.parse_mode,
            )
            success += 1
        except Exception:
            failed += 1

    await message.answer(
        f"✅ <b>Broadcast tugadi!</b>\n\n"
        f"✅ Muvaffaqiyatli: <b>{success}</b>\n"
        f"❌ Muvaffaqiyatsiz: <b>{failed}</b>"
    )

    await state.clear()


@router.message(BroadcastStates.confirm)
async def cancel_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await message.answer("❌ Broadcast bekor qilindi.")
    await state.clear()


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("❌ Amal bekor qilindi.")


# Yordamchi funksiya
async def get_user_count(bot) -> int:
    # Agar kerak bo'lsa, real vaqtida hisoblash mumkin
    return 0  # hozircha placeholder, keyinroq UserRepository orqali qilamiz
