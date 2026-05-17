from typing import Sequence
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Channel
from app.repositories.base_repo import BaseRepository


class ChannelRepository(BaseRepository[Channel]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Channel)

    async def get_required_channels(self) -> Sequence[Channel]:
        stmt = select(Channel).where(
            Channel.is_active == True, Channel.is_required == True
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_all_active(self) -> Sequence[Channel]:
        stmt = select(Channel).where(Channel.is_active == True)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_all_channels(self) -> Sequence[Channel]:
        stmt = select(Channel).order_by(Channel.created_at.desc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_channel_id(self, channel_id: int) -> Channel | None:
        stmt = select(Channel).where(Channel.channel_id == channel_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def toggle_required(self, channel_id: int, is_required: bool):
        stmt = (
            update(Channel)
            .where(Channel.channel_id == channel_id)
            .values(is_required=is_required)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def toggle_active(self, channel_id: int, is_active: bool):
        stmt = (
            update(Channel)
            .where(Channel.channel_id == channel_id)
            .values(is_active=is_active)
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def create(
        self,
        channel_id: int,
        title: str,
        username: str | None = None,
        is_active: bool = True,
        is_required: bool = True,
        description: str | None = None,
        invite_link: str | None = None,
    ) -> Channel:
        channel = Channel(
            channel_id=channel_id,
            username=username,
            title=title,
            is_active=is_active,
            is_required=is_required,
            description=description,
            invite_link=invite_link,
        )
        self.session.add(channel)
        await self.session.commit()
        await self.session.refresh(channel)
        return channel
