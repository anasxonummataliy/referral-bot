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
            encode=False,
            link_type="start",
        )

    async def process_new_referral(
        self,
        new_user_telegram_id: int,
        referrer_telegram_id: int,
        give_bonus: bool = False,
    ) -> bool:
        """
        Yangi foydalanuvchi referral orqali kelganda chaqiriladi.
        
        give_bonus=False (standart): referral yozuvi bonus_given=False bilan saqlanadi.
        Referrerga +1 faqat yangi user barcha majburiy kanallarga qo'shilgach
        confirm_referral() orqali beriladi!
        
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

        if new_user.referrer_id is not None:
            return False

        # Yangi user allaqachon boshqa birovning referrali bo'lmasin
        existing = await self.referral_repo.get_by_referred_id(new_user.id)
        if existing:
            logger.info(
                f"process_new_referral: {new_user_telegram_id} allaqachon "
                f"referral sifatida qayd qilingan"
            )
            return False

        # Referral yaratish (bonus_given=give_bonus)
        referral = await self.referral_repo.create_referral(
            referrer_id=referrer.id,
            referred_id=new_user.id,
        )

        # Yangi userning referrer_id sini yangilaymiz
        await self.user_repo.update(new_user.id, referrer_id=referrer.id)

        if give_bonus:
            await self.referral_repo.mark_bonus_given(referral.id)
            await self.user_repo.increment_referral_count(referrer_telegram_id)

        logger.info(
            f"✅ Referral qayd: new={new_user_telegram_id} → referrer={referrer_telegram_id} (bonus={give_bonus})"
        )
        return True

    async def confirm_referral(self, referred_telegram_id: int, bot) -> bool:
        """
        Taklif qilingan foydalanuvchi majburiy kanallarga a'zo bo'lgach chaqiriladi.
        Hali bonus berilmagan bo'lsa (bonus_given=False):
        1. bonus_given = True qilinadi
        2. Referrerning referral_count +1 qilinadi
        3. Referrerga bildirishnoma yuboriladi (notify_referrer)
        4. Referrer shartni bajargan bo'lsa prize link yuboriladi (check_and_send_prize)
        """
        referred_user = await self.user_repo.get_by_telegram_id(referred_telegram_id)
        if not referred_user:
            return False

        referral = await self.referral_repo.get_by_referred_id(referred_user.id)
        if not referral or referral.bonus_given:
            return False

        referrer = await self.user_repo.get(referral.referrer_id)
        if not referrer:
            return False

        # 1. Bonus berildi deb belgilaymiz
        await self.referral_repo.mark_bonus_given(referral.id)

        # 2. Referrerning referral_count +1 (DB da yangilanadi)
        await self.user_repo.increment_referral_count(referrer.telegram_id)

        # 3. Referrerga bildirishnoma
        try:
            from app.bot.handlers.user.referral_notify import notify_referrer
            await notify_referrer(
                bot=bot,
                referrer_telegram_id=referrer.telegram_id,
                new_user_name=referred_user.full_name or "Do'st",
                db=self.db,
            )
        except Exception as e:
            logger.error(f"notify_referrer xatolik: {e}")

        # 4. Referrer sovg'a shartini bajargan bo'lsa prize link
        try:
            from app.bot.handlers.user.prize import check_and_send_prize
            await check_and_send_prize(
                bot=bot,
                referrer_telegram_id=referrer.telegram_id,
                db=self.db,
            )
        except Exception as e:
            logger.error(f"check_and_send_prize xatolik: {e}")

        logger.info(
            f"🎉 Referral tasdiqlandi (+1): referred={referred_telegram_id} → referrer={referrer.telegram_id}"
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
