from typing import TypeVar, Generic, Type, Sequence
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, session: AsyncSession, model: Type[ModelType]):
        self.session = session
        self.model = model

    async def create(self, **kwargs) -> ModelType:
        db_obj = self.model(**kwargs)
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def get(self, id: int) -> ModelType | None:
        return await self.session.get(self.model, id)

    async def get_by_telegram_id(self, telegram_id: int) -> ModelType | None:
        stmt = select(self.model).where(self.model.telegram_id == telegram_id)  # type: ignore
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int | None = None) -> Sequence[ModelType]:
        stmt = select(self.model).offset(skip)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, id: int, **kwargs) -> ModelType | None:
        stmt = (
            update(self.model)
            .where(self.model.id == id)  # type: ignore
            .values(**kwargs)
            .returning(self.model)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one_or_none()

    async def update_by_telegram_id(self, telegram_id: int, **kwargs) -> ModelType | None:
        stmt = (
            update(self.model)
            .where(self.model.telegram_id == telegram_id)  # type: ignore
            .values(**kwargs)
            .returning(self.model)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one_or_none()

    async def delete(self, id: int) -> bool:
        stmt = delete(self.model).where(self.model.id == id)  # type: ignore
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model)
        result = await self.session.execute(stmt)
        return result.scalar_one()
