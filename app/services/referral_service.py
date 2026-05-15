# services/referral_service.py
from aiogram.utils.deep_linking import create_deep_link
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.secret_channel_repo import SecretChannelRepository
from repositories.user_repo import UserRepository
from repositories.referral_repo import ReferralRepository


class ReferralService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.referral_repo = ReferralRepository(db)

    async def get_user_referral_link(self, telegram_id: int, bot_username: str) -> str:
        """
        Aiogramning rasmiy deep_linking kutubxonasi orqali link yaratish
        """
        return create_deep_link(
            bot_username=bot_username,
            payload=str(telegram_id),
            encode=True,
        )

    async def check_and_give_secret_channel(self, telegram_id: int, bot) -> str | None:
        """Foydalanuvchi yetarli referralga ega bo'lsa maxfiy kanal linkini qaytaradi"""
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user or user.referral_count < 10:
            return None

        secret_repo = SecretChannelRepository(self.db)
        secret_channel = await secret_repo.get_active_secret_channel()

        if not secret_channel:
            return None

        if secret_channel.username:
            return f"https://t.me/{secret_channel.username.lstrip('@')}"
        else:
            return f"https://t.me/c/{abs(secret_channel.channel_id)}"
