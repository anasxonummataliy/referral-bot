from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.admin import Admin
from app.repositories.base_repo import BaseRepository


class AdminRepository(BaseRepository[Admin]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Admin)

    async def get_by_telegram_id(self, telegram_id: int) -> Admin | None:
        stmt = select(Admin).where(Admin.telegram_id == telegram_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all_admins(self) -> list[Admin]:
        stmt = select(Admin).where(Admin.is_active == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_admin(
        self,
        telegram_id: int,
        username: str | None = None,
        full_name: str | None = None,
    ) -> Admin:
        """Yangi admin qo'shish"""
        existing = await self.get_by_telegram_id(telegram_id)
        if existing:
            # Qayta faollashtirish
            from sqlalchemy import update
            stmt = (
                update(Admin)
                .where(Admin.telegram_id == telegram_id)
                .values(is_active=True, username=username, full_name=full_name)
            )
            await self.session.execute(stmt)
            await self.session.commit()
            return await self.get_by_telegram_id(telegram_id)
        return await self.create(
            telegram_id=telegram_id,
            username=username,
            full_name=full_name,
            is_active=True,
        )

    async def remove_admin(self, telegram_id: int) -> bool:
        """Adminni o'chirish (deactivate)"""
        from sqlalchemy import update
        stmt = (
            update(Admin)
            .where(Admin.telegram_id == telegram_id)
            .values(is_active=False)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0
