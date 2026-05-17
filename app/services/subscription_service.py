from typing import Sequence
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.channel_repo import ChannelRepository
from app.repositories.user_repo import UserRepository
from app.database.models import Channel
from aiogram import Bot


class SubscriptionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.channel_repo = ChannelRepository(db)
        self.user_repo = UserRepository(db)

    async def get_required_channels(self) -> Sequence[Channel]:
        return await self.channel_repo.get_required_channels()

    async def check_full_subscription(self, bot: Bot, telegram_id: int) -> bool:
        """Foydalanuvchi barcha majburiy kanallarga obuna bo'lganligini tekshiradi"""
        required_channels = await self.get_required_channels()

        if not required_channels:
            await self.user_repo.update_subscription_status(telegram_id, True)
            return True

        for channel in required_channels:
            try:
                member = await bot.get_chat_member(
                    chat_id=channel.channel_id, user_id=telegram_id
                )
                if member.status in ["left", "kicked"]:
                    await self.user_repo.update_subscription_status(telegram_id, False)
                    return False
            except Exception:
                await self.user_repo.update_subscription_status(telegram_id, False)
                return False

        await self.user_repo.update_subscription_status(telegram_id, True)
        return True
