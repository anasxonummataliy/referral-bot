# services/subscription_service.py
from typing import Sequence
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.channel_repo import ChannelRepository
from app.repositories.user_repo import UserRepository
from app.database.models import Channel
from aiogram import Bot


class SubscriptionService:
    """Majburiy obuna xizmati"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.channel_repo = ChannelRepository(db)
        self.user_repo = UserRepository(db)

    async def get_required_channels(self) -> Sequence[Channel]:
        """Faqat majburiy kanallarni qaytaradi"""
        return await self.channel_repo.get_required_channels()

    async def check_full_subscription(self, bot: Bot, telegram_id: int) -> bool:
        """
        Foydalanuvchi barcha majburiy kanallarga obuna bo'lganligini tekshiradi
        va natijani DB ga saqlaydi.
        """
        required_channels = await self.get_required_channels()

        # Agar majburiy kanal bo'lmasa
        if not required_channels:
            await self.mark_user_as_subscribed(telegram_id)
            return True

        # Barcha majburiy kanallarni tekshirish
        for channel in required_channels:
            try:
                member = await bot.get_chat_member(
                    chat_id=channel.channel_id, user_id=telegram_id
                )

                # "left", "kicked" holatlarida obuna yo'q hisoblanadi
                if member.status in ["left", "kicked"]:
                    await self.mark_user_as_not_subscribed(telegram_id)
                    return False

            except Exception:
                # Kanal topilmadi yoki boshqa xato bo'lsa (masalan, bot admin emas)
                # Xavfsizroq bo'lish uchun False qaytaramiz
                await self.mark_user_as_not_subscribed(telegram_id)
                return False

        # Agar barcha kanallarga obuna bo'lsa
        await self.mark_user_as_subscribed(telegram_id)
        return True

    async def mark_user_as_subscribed(self, telegram_id: int):
        """Foydalanuvchini obuna bo'ldi deb belgilash"""
        await self.user_repo.update_subscription_status(telegram_id, True)

    async def mark_user_as_not_subscribed(self, telegram_id: int):
        """Foydalanuvchini obuna bo'lmagan deb belgilash"""
        await self.user_repo.update_subscription_status(telegram_id, False)
