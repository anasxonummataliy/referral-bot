from typing import TypeVar, Generic, Type, Any, Sequence
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.base import Base

# Generic type for models
ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Barcha repository lar uchun asosiy klass
    """

    def __init__(self, session: AsyncSession, model: Type[ModelType]):
        self.session = session
        self.model = model

    # ====================== CREATE ======================
    async def create(self, **kwargs) -> ModelType:
        """Yangi obyekt yaratish"""
        db_obj = self.model(**kwargs)
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    # ====================== GET ======================
    async def get(self, id: int) -> ModelType | None:
        """ID bo'yicha olish"""
        return await self.session.get(self.model, id)

    async def get_by_telegram_id(self, telegram_id: int) -> ModelType | None:
        """Telegram ID bo'yicha olish (User uchun qulay)"""
        stmt = select(self.model).where(self.model.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    # ====================== LIST ======================
    async def get_all(self, skip: int = 0, limit: int = 100) -> Sequence[ModelType]:
        """Barchasini olish"""
        stmt = select(self.model).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    # ====================== UPDATE ======================
    async def update(self, id: int, **kwargs) -> ModelType | None:
        """ID bo'yicha yangilash"""
        stmt = (
            update(self.model)
            .where(self.model.id == id)
            .values(**kwargs)
            .returning(self.model)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one_or_none()

    async def update_by_telegram_id(
        self, telegram_id: int, **kwargs
    ) -> ModelType | None:
        """Telegram ID bo'yicha yangilash"""
        stmt = (
            update(self.model)
            .where(self.model.telegram_id == telegram_id)
            .values(**kwargs)
            .returning(self.model)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one_or_none()

    # ====================== DELETE ======================
    async def delete(self, id: int) -> bool:
        """ID bo'yicha o'chirish"""
        stmt = delete(self.model).where(self.model.id == id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    # ====================== COUNT ======================
    async def count(self) -> int:
        """Umumiy sonini olish"""
        stmt = select(self.model)
        result = await self.session.execute(stmt)
        return len(result.scalars().all())  # oddiyroq usul
