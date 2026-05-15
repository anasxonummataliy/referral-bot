# bot/handlers/admin/users.py
from aiogram import F
from aiogram.types import Message
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from .base import admin_router, is_admin
from repositories.user_repo import UserRepository

router = admin_router


@router.message(Command("finduser"))
async def cmd_finduser(message: Message):
    if not is_admin(message.from_user.id):
        return
    await message.answer("🔍 Telegram ID yuboring:")


@router.message(F.text.regexp(r"^\d+$"))
async def process_find_user(message: Message, db: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    try:
        user_id = int(message.text)
        repo = UserRepository(db)
        user = await repo.get_by_telegram_id(user_id)

        if not user:
            await message.answer("❌ Foydalanuvchi topilmadi.")
            return

        text = f"""
👤 <b>Foydalanuvchi ma'lumotlari</b>

ID: <code>{user.telegram_id}</code>
Ism: {user.full_name}
Username: @{user.username or 'yo‘q'}
Referral soni: <b>{user.referral_count}</b>
Obuna: {"✅ Ha" if user.is_subscribed else "❌ Yo‘q"}
        """
        await message.answer(text)
    except:
        pass
