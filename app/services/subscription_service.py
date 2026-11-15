import logging
from typing import Sequence
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.channel_repo import ChannelRepository
from app.repositories.user_repo import UserRepository
from app.database.models import Channel
from aiogram import Bot

logger = logging.getLogger(__name__)


class SubscriptionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.channel_repo = ChannelRepository(db)
        self.user_repo = UserRepository(db)

    async def get_required_channels(self) -> Sequence[Channel]:
        return await self.channel_repo.get_required_channels()

    async def get_unsubscribed_channels(
        self, bot: Bot, telegram_id: int
    ) -> list[Channel]:
        """
        Foydalanuvchi obuna bo'lmagan majburiy kanallar ro'yxatini qaytaradi.
        Barcha kanallarga a'zo bo'lsa bo'sh ro'yxat ([]) qaytadi.
        """
        required_channels = await self.get_required_channels()
        if not required_channels:
            return []

        unsubscribed = []
        for channel in required_channels:
            try:
                member = await bot.get_chat_member(
                    chat_id=channel.channel_id, user_id=telegram_id
                )
                if member.status in ["left", "kicked"]:
                    unsubscribed.append(channel)
                elif member.status == "restricted" and not getattr(member, "is_member", True):
                    unsubscribed.append(channel)
            except Exception as e:
                # PARTICIPANT_ID_INVALID yoki boshqa xatolar user kanalda yo'qligini bildiradi
                unsubscribed.append(channel)
                logger.info(
                    f"User {telegram_id} kanalda topilmadi ({channel.channel_id} - {channel.title}): {e}"
                )

        return unsubscribed

    async def check_full_subscription(self, bot: Bot, telegram_id: int) -> bool:
        """Foydalanuvchi barcha majburiy kanallarga obuna bo'lganligini tekshiradi"""
        unsubscribed = await self.get_unsubscribed_channels(bot, telegram_id)
        is_sub = len(unsubscribed) == 0
        await self.user_repo.update_subscription_status(telegram_id, is_sub)
        return is_sub
