# repositories/channel_repo.py
from typing import Sequence
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Channel
from .base_repo import BaseRepository


class ChannelRepository(BaseRepository[Channel]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Channel)

    async def get_required_channels(self) -> Sequence[Channel]:
        """Faqat majburiy kanallarni olish"""
        stmt = select(Channel).where(
            Channel.is_active == True, Channel.is_required == True
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_all_active(self) -> Sequence[Channel]:
        """Barcha faol kanallarni olish"""
        stmt = select(Channel).where(Channel.is_active == True)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_channel_id(self, channel_id: int) -> Channel | None:
        """Channel ID bo'yicha olish"""
        stmt = select(Channel).where(Channel.channel_id == channel_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def toggle_required(self, channel_id: int, is_required: bool):
        """Majburiy holatni o'zgartirish"""
        stmt = (
            update(Channel)
            .where(Channel.channel_id == channel_id)
            .values(is_required=is_required)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def toggle_active(self, channel_id: int, is_active: bool):
        """Active holatni o'zgartirish"""
        stmt = (
            update(Channel)
            .where(Channel.channel_id == channel_id)
            .values(is_active=is_active)
        )
        await self.session.execute(stmt)
        await self.session.commit()
