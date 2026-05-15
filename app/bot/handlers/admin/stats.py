# bot/handlers/admin/stats.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from .base import admin_router, is_admin
from repositories.user_repo import UserRepository

router = admin_router


@router.message(Command("stats", "statistics"))
async def cmd_stats(message: Message, db: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    user_repo = UserRepository(db)

    total_users = await user_repo.count()
    # Kelajakda referral bo'yicha statistika qo'shiladi

    text = f"""
📊 <b>Bot Statistika</b>

👥 Jami foydalanuvchilar: <b>{total_users}</b>
    """
    await message.answer(text)
