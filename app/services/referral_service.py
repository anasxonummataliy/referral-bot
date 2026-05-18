"""
Referral logikasi.

Muhim: process_new_referral oxirida DB ga commit qilinadi,
shuning uchun check_and_send_prize fresh qiymat oladi.
"""
import logging

from aiogram.utils.deep_linking import create_deep_link
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_repo import UserRepository
from app.repositories.referral_repo import ReferralRepository
from app.repositories.secret_channel_repo import SecretChannelRepository

logger = logging.getLogger(__name__)


class ReferralService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.referral_repo = ReferralRepository(db)
        self.secret_repo = SecretChannelRepository(db)

    async def get_user_referral_link(self, telegram_id: int, bot_username: str) -> str:
        """Foydalanuvchining referral deep linkini yaratish."""
        return create_deep_link(
            username=bot_username,
            payload=str(telegram_id),
            encode=True,
            link_type="start",
        )

    async def process_new_referral(
        self, new_user_telegram_id: int, referrer_telegram_id: int
    ) -> bool:
        """
        Yangi foydalanuvchi referral orqali kelganda chaqiriladi.
        
        Tekshiruvlar:
        1. Ikkalasi ham bazada bor
        2. Yangi user allaqachon birovning referrali emas
        3. O'ziga o'zi referral qilmaydi
        
        Returns True — muvaffaqiyatli qayd qilindi.
        """
        new_user = await self.user_repo.get_by_telegram_id(new_user_telegram_id)
        referrer = await self.user_repo.get_by_telegram_id(referrer_telegram_id)

        if not new_user or not referrer:
            logger.warning(
                f"process_new_referral: user(s) topilmadi "
                f"new={new_user_telegram_id} ref={referrer_telegram_id}"
            )
            return False

        if new_user.id == referrer.id:
            return False

        # Yangi user allaqachon boshqa birovning referrali bo'lmasin
        existing = await self.referral_repo.get_by_referred_id(new_user.id)
        if existing:
            logger.info(
                f"process_new_referral: {new_user_telegram_id} allaqachon "
                f"referral sifatida qayd qilingan"
            )
            return False

        # Referral yaratish
        await self.referral_repo.create_referral(
            referrer_id=referrer.id,
            referred_id=new_user.id,
        )

        # referral_count +1 (DB da yangilanadi)
        await self.user_repo.increment_referral_count(referrer_telegram_id)

        logger.info(
            f"✅ Referral qayd: new={new_user_telegram_id} → referrer={referrer_telegram_id}"
        )
        return True

    async def get_user_referral_stats(self, telegram_id: int) -> dict:
        """Foydalanuvchining referral statistikasi."""
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return {"count": 0, "eligible_channels": []}
        eligible_channels = await self.secret_repo.get_eligible_channels(user.referral_count)
        return {
            "count": user.referral_count,
            "eligible_channels": eligible_channels,
        }

    async def get_gift_channels_for_user(self, telegram_id: int):
        """Foydalanuvchi olishi mumkin bo'lgan sovg'a kanallarini qaytaradi."""
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return []
        return await self.secret_repo.get_eligible_channels(user.referral_count)

    async def get_all_gift_channels_info(self):
        """Barcha aktiv sovg'a kanallarini qaytaradi."""
        return await self.secret_repo.get_active_gift_channels()
