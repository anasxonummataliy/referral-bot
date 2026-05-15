from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from core.config import settings


# Async Engine yaratish
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=20,
)

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


# Dependency (aiogram routerlarda ishlatish uchun)
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Har bir request uchun yangi session yaratadi"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# Barcha modellarni import qilish va tablelarni yaratish uchun
async def init_db():
    """Jadvallarni yaratish (birinchi marta ishga tushirganda)"""
    from database.base import Base  # Barcha modellaringiz Base dan meros olgan

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Optional: Tablelarni o'chirish (test uchun)
async def drop_db():
    from database.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
