# repositories/user_repo.py
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import User
from .base_repo import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, User)

    async def get_or_create(self, telegram_id: int, **kwargs) -> tuple[User, bool]:
        """Foydalanuvchini topish yoki yaratish"""
        user = await self.get_by_telegram_id(telegram_id)

        if user:
            return user, False

        user = await self.create(
            telegram_id=telegram_id,
            full_name=kwargs.get("full_name", ""),
            username=kwargs.get("username"),
            language_code=kwargs.get("language_code"),
            referrer_id=kwargs.get("referrer_id"),
        )
        return user, True

    async def increment_referral_count(self, telegram_id: int) -> User | None:
        """Referral sonini +1 qilish"""
        stmt = (
            update(User)
            .where(User.telegram_id == telegram_id)
            .values(referral_count=User.referral_count + 1)
            .returning(User)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one_or_none()

    # ====================== SUBSCRIPTION ======================
    async def update_subscription_status(self, telegram_id: int, is_subscribed: bool):
        """Majburiy obuna holatini yangilash"""
        return await self.update_by_telegram_id(
            telegram_id=telegram_id, is_subscribed=is_subscribed
        )

    # ====================== WITH REFERRER ======================
    async def get_with_referrer(self, telegram_id: int) -> User | None:
        """Referrer bilan birga olish"""
        stmt = (
            select(User)
            .where(User.telegram_id == telegram_id)
            .options(selectinload(User.referrer))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ====================== TOP REFERRERS ======================
    async def get_top_referrers(self, limit: int = 10):
        """Eng ko‘p referral qilganlarni olish"""
        stmt = select(User).order_by(User.referral_count.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()
