from typing import Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import SecretChannel
from app.repositories.base_repo import BaseRepository


class SecretChannelRepository(BaseRepository[SecretChannel]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, SecretChannel)

    async def get_active_gift_channels(self) -> Sequence[SecretChannel]:
        """Foydalanuvchi uchun faol sovg'a kanallarini olish"""
        stmt = (
            select(SecretChannel)
            .where(SecretChannel.is_active == True)
            .order_by(SecretChannel.min_referrals.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_all_gift_channels(self) -> Sequence[SecretChannel]:
        """Admin uchun barcha sovg'a kanallarini olish"""
        stmt = select(SecretChannel).order_by(SecretChannel.created_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_eligible_channels(self, referral_count: int) -> Sequence[SecretChannel]:
        """Foydalanuvchining referral soniga mos kanallarni olish"""
        stmt = (
            select(SecretChannel)
            .where(
                SecretChannel.is_active == True,
                SecretChannel.min_referrals <= referral_count,
            )
            .order_by(SecretChannel.min_referrals.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
