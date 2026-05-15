# repositories/secret_channel_repo.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import SecretChannel
from .base_repo import BaseRepository


class SecretChannelRepository(BaseRepository[SecretChannel]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, SecretChannel)

    async def get_active_secret_channel(self):
        """Hozirgi faol maxfiy kanalni olish"""
        stmt = select(SecretChannel).where(SecretChannel.is_active == True).limit(1)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
