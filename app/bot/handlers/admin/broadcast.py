import asyncio
from aiogram import F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.admin.base import admin_router, is_admin, admin_main_keyboard
from app.repositories.user_repo import UserRepository

router = admin_router


class BroadcastStates(StatesGroup):
    waiting_for_message = State()
    confirm = State()


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await _start_broadcast(message, state)


@router.callback_query(F.data == "adm_broadcast")
async def adm_broadcast_cb(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await _start_broadcast(callback.message, state)
    await callback.answer()


async def _start_broadcast(message: Message, state: FSMContext):
    await message.answer(
        "📢 <b>Broadcast</b>\n\n"
        "Foydalanuvchilarga yubormoqchi bo'lgan xabarni yuboring\n"
        "(matn, rasm, video va boshqalar).\n\n"
        "Bekor qilish: /cancel"
    )
    await state.set_state(BroadcastStates.waiting_for_message)


@router.message(BroadcastStates.waiting_for_message)
async def process_broadcast_message(
    message: Message, state: FSMContext, db: AsyncSession
):
    if not is_admin(message.from_user.id):
        return

    user_repo = UserRepository(db)
    total = await user_repo.count()

    await state.update_data(
        broadcast_message_id=message.message_id,
        broadcast_chat_id=message.chat.id,
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Yuborish", callback_data="broadcast_confirm"
                ),
                InlineKeyboardButton(text="❌ Bekor", callback_data="broadcast_cancel"),
            ]
        ]
    )
    await message.answer(
        f"❓ <b>Tasdiqlaysizmi?</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{total}</b>\n\n"
        f"Yuborish uchun tugmani bosing:",
        reply_markup=keyboard,
    )
    await state.set_state(BroadcastStates.confirm)


@router.callback_query(F.data == "broadcast_confirm")
async def confirm_broadcast_cb(
    callback: CallbackQuery, state: FSMContext, db: AsyncSession
):
    if not is_admin(callback.from_user.id):
        return

    data = await state.get_data()
    source_message_id = data.get("broadcast_message_id")
    source_chat_id = data.get("broadcast_chat_id")

    if not source_message_id:
        await callback.message.answer("❌ Xatolik. Qaytadan boshlang.")
        await state.clear()
        return

    user_repo = UserRepository(db)
    all_users = await user_repo.get_all_users()

    success = 0
    failed = 0

    status_msg = await callback.message.answer(
        f"📤 Broadcast boshlandi...\nJami: {len(all_users)} ta"
    )

    for user in all_users:
        try:
            await callback.bot.copy_message(
                chat_id=user.telegram_id,
                from_chat_id=source_chat_id,
                message_id=source_message_id,
            )
            success += 1
        except Exception:
            failed += 1

        if (success + failed) % 50 == 0:
            await asyncio.sleep(0.5)

    await status_msg.edit_text(
        f"✅ <b>Broadcast tugadi!</b>\n\n"
        f"✅ Muvaffaqiyatli: <b>{success}</b>\n"
        f"❌ Muvaffaqiyatsiz: <b>{failed}</b>"
    )
    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "broadcast_cancel")
async def cancel_broadcast_cb(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    await callback.message.edit_text(
        "❌ Broadcast bekor qilindi.",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Panel", callback_data="adm_back")]
            ]
        ),
    )
    await callback.answer()


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Amal bekor qilindi.")


@router.message(Command("topref"))
async def cmd_top_referrers(message: Message, db: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    user_repo = UserRepository(db)
    top_users = await user_repo.get_top_referrers(limit=10)

    if not top_users:
        await message.answer("📊 Hali hech kim referral qilmagan.")
        return

    text = "🏆 <b>Top referralchilar</b>\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for i, user in enumerate(top_users):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        username = f"@{user.username}" if user.username else user.full_name
        text += f"{medal} {username} — <b>{user.referral_count}</b> referral\n"

    await message.answer(text)


@router.message(Command("finduser"))
async def cmd_finduser(message: Message, db: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    args = message.text.split()
    if len(args) < 2:
        await message.answer(
            "🔍 <b>Foydalanuvchi qidirish</b>\n\n"
            "Ishlatish: <code>/finduser [telegram_id]</code>"
        )
        return

    try:
        search_id = int(args[1])
        user_repo = UserRepository(db)
        user = await user_repo.get_by_telegram_id(search_id)

        if not user:
            await message.answer("❌ Foydalanuvchi topilmadi.")
            return

        text = (
            f"👤 <b>Foydalanuvchi ma'lumotlari</b>\n\n"
            f"🆔 ID: <code>{user.telegram_id}</code>\n"
            f"👤 Ism: <b>{user.full_name}</b>\n"
            f"📛 Username: {'@' + user.username if user.username else 'yo\'q'}\n"
            f"👥 Referrallar: <b>{user.referral_count}</b>\n"
            f"✅ Obuna: {'Ha' if user.is_subscribed else 'Yo\'q'}"
        )
        await message.answer(text)

    except ValueError:
        await message.answer("❌ Noto'g'ri ID format.")
