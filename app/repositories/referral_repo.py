# repositories/referral_repo.py
from typing import Sequence
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Referral
from app.database.models.user import User
from .base_repo import BaseRepository


class ReferralRepository(BaseRepository[Referral]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Referral)

    async def create_referral(
        self, referrer_id: int, referred_id: int, source: str | None = None
    ) -> Referral:
        """Yangi referral yozuvini yaratish"""
        referral = await self.create(
            referrer_id=referrer_id,
            referred_id=referred_id,
            source=source,
            bonus_given=False,
        )
        return referral

    async def get_by_referred_id(self, referred_id: int) -> Referral | None:
        """Taklif qilingan foydalanuvchi bo'yicha referral ma'lumotini olish"""
        stmt = select(Referral).where(Referral.referred_id == referred_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_referrals(self, referrer_id: int) -> Sequence[Referral]:
        """Biror foydalanuvchining barcha referral larini olish"""
        stmt = (
            select(Referral)
            .where(Referral.referrer_id == referrer_id)
            .options(selectinload(Referral.referred))
            .order_by(Referral.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def has_referred(self, referrer_id: int, referred_id: int) -> bool:
        """Bu foydalanuvchi oldin ham referral bo'lganmi?"""
        stmt = select(Referral).where(
            and_(
                Referral.referrer_id == referrer_id, Referral.referred_id == referred_id
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def mark_bonus_given(self, referral_id: int):
        """Bonus berilgan deb belgilash"""
        await self.update(referral_id, bonus_given=True)
