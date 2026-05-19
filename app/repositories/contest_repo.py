from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.contest import Contest
from app.repositories.base_repo import BaseRepository


class ContestRepository(BaseRepository[Contest]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Contest)

    async def get_active_contest(self) -> Contest | None:
        """Hozirgi aktiv konkursni olish (faqat bitta bo'ladi)"""
        stmt = select(Contest).where(Contest.is_active == True).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def deactivate_all(self) -> None:
        """Barcha konkurslarni o'chirish (yangi yaratishdan oldin)"""
        stmt = update(Contest).values(is_active=False)
        await self.session.execute(stmt)
        await self.session.commit()

    async def create_contest(
        self,
        title: str,
        welcome_message: str | None,
        required_referrals: int,
        welcome_photo_file_id: str | None = None,
        prize_channel_id: int | None = None,
        prize_channel_title: str | None = None,
    ) -> Contest:
        """Yangi konkurs yaratish (avval barchasi o'chiriladi)"""
        await self.deactivate_all()
        return await self.create(
            title=title,
            welcome_message=welcome_message,
            welcome_photo_file_id=welcome_photo_file_id,
            required_referrals=required_referrals,
            prize_channel_id=prize_channel_id,
            prize_channel_title=prize_channel_title,
            is_active=True,
        )

    async def set_prize_channel(
        self, contest_id: int, channel_id: int, channel_title: str
    ) -> None:
        """Prize kanalini o'rnatish"""
        stmt = (
            update(Contest)
            .where(Contest.id == contest_id)
            .values(prize_channel_id=channel_id, prize_channel_title=channel_title)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def update(self, contest_id: int, **kwargs) -> None:
        """Konkurs maydonlarini yangilash"""
        stmt = (
            update(Contest)
            .where(Contest.id == contest_id)
            .values(**kwargs)
        )
        await self.session.execute(stmt)
        await self.session.commit()
