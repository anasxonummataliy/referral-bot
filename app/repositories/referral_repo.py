from typing import Sequence
from sqlalchemy import select, and_, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Referral
from app.repositories.base_repo import BaseRepository


class ReferralRepository(BaseRepository[Referral]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Referral)

    async def create_referral(
        self, referrer_id: int, referred_id: int, contest_id: int | None = None
    ) -> Referral:
        """Yangi referral yozuvini yaratish (user.id bilan)"""
        referral = await self.create(
            referrer_id=referrer_id,
            referred_id=referred_id,
            contest_id=contest_id,
            bonus_given=False,
        )
        return referral

    async def get_by_referred_id(self, referred_id: int) -> Referral | None:
        """Taklif qilingan foydalanuvchi ID bo'yicha (user.id)"""
        stmt = select(Referral).where(Referral.referred_id == referred_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_referrals(
        self, referrer_id: int, only_confirmed: bool = True, contest_id: int | None = None
    ) -> Sequence[Referral]:
        """Biror foydalanuvchining barcha referral larini olish (user.id)"""
        stmt = select(Referral).where(Referral.referrer_id == referrer_id)
        if only_confirmed:
            stmt = stmt.where(Referral.bonus_given == True)
        if contest_id is not None:
            stmt = stmt.where((Referral.contest_id == contest_id) | (Referral.contest_id.is_(None)))
        stmt = stmt.options(selectinload(Referral.referred)).order_by(
            Referral.joined_at.desc()
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def count_user_referrals(
        self, referrer_id: int, contest_id: int | None = None
    ) -> int:
        """Foydalanuvchining faol/tasdiqlangan referallari sonini sanash"""
        stmt = select(func.count(Referral.id)).where(
            Referral.referrer_id == referrer_id,
            Referral.bonus_given.is_(True),
        )
        if contest_id is not None:
            stmt = stmt.where((Referral.contest_id == contest_id) | (Referral.contest_id.is_(None)))
        result = await self.session.execute(stmt)
        return result.scalar() or 0

    async def has_referred(self, referrer_id: int, referred_id: int) -> bool:
        stmt = select(Referral).where(
            and_(
                Referral.referrer_id == referrer_id,
                Referral.referred_id == referred_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def mark_bonus_given(self, referral_id: int):
        await self.update(referral_id, bonus_given=True)

    async def claim_bonus(self, referral_id: int) -> bool:
        """
        Atomik UPDATE: bonus hali berilmagan bo'lsa True qilib beradi.
        Agar boshqa parallel chaqiriq allaqachon sanagan bo'lsa, False qaytaradi.
        """
        stmt = (
            update(Referral)
            .where(Referral.id == referral_id, Referral.bonus_given.is_(False))
            .values(bonus_given=True)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return (res.rowcount or 0) == 1

    async def revoke_bonus(self, referral_id: int) -> bool:
        """
        Atomik UPDATE: agar bonus berilgan bo'lsa, uni bekor qiladi (bonus_given=False).
        """
        stmt = (
            update(Referral)
            .where(Referral.id == referral_id, Referral.bonus_given.is_(True))
            .values(bonus_given=False)
        )
        res = await self.session.execute(stmt)
        await self.session.commit()
        return (res.rowcount or 0) == 1

    async def get_unconfirmed_referrals(self) -> Sequence[Referral]:
        """Tasdiqlanmagan (bonus_given=False) barcha referallarni olish"""
        stmt = select(Referral).where(Referral.bonus_given.is_(False))
        result = await self.session.execute(stmt)
        return result.scalars().all()

