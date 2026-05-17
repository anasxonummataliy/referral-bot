from aiogram.utils.deep_linking import create_deep_link
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import user
from app.repositories.secret_channel_repo import SecretChannelRepository
from app.repositories.user_repo import UserRepository
from app.repositories.referral_repo import ReferralRepository


class ReferralService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.referral_repo = ReferralRepository(db)
        self.secret_repo = SecretChannelRepository(db)

    async def get_user_referral_link(self, telegram_id: int, bot_username: str) -> str:
        """Foydalanuvchining referral linkini yaratish"""
        return create_deep_link(
            username=bot_username,
            payload=str(telegram_id),
            encode=True,
            link_type="start",
        )

    async def process_new_referral(
        self, new_user_telegram_id: int, referrer_telegram_id: int
    ) -> bool:
        """Yangi foydalanuvchi referral orqali kelganda ishga tushadi"""
        # Foydalanuvchilarni olish
        new_user = await self.user_repo.get_by_telegram_id(new_user_telegram_id)
        referrer = await self.user_repo.get_by_telegram_id(referrer_telegram_id)

        if not new_user or not referrer:
            return False

        # Allaqachon referral bor-yo'qligini tekshirish
        existing = await self.referral_repo.get_by_referred_id(new_user.id)
        if existing:
            return False

        # Referral yozuvini yaratish
        await self.referral_repo.create_referral(
            referrer_id=referrer.id,
            referred_id=new_user.id,
        )

        # Referrer hisoblash sonini +1
        await self.user_repo.increment_referral_count(referrer_telegram_id)

        return True

    async def get_user_referral_stats(self, telegram_id: int) -> dict:
        """Foydalanuvchining referral statistikasini olish"""
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return {"count": 0, "eligible_channels": []}

        eligible_channels = await self.secret_repo.get_eligible_channels(
            user.referral_count
        )

        return {
            "count": user.referral_count,
            "eligible_channels": eligible_channels,
        }

    async def get_gift_channels_for_user(self, telegram_id: int):
        """Foydalanuvchi olishi mumkin bo'lgan sovg'a kanallarini qaytaradi"""
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return []
        return await self.secret_repo.get_eligible_channels(user.referral_count)

    async def get_all_gift_channels_info(self):
        """Barcha sovg'a kanallarini qaytaradi (faol bo'lganlar)"""
        return await self.secret_repo.get_active_gift_channels()
