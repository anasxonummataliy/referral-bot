import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# SQLite papkasini avtomatik yaratish
if settings.DB_PATH and not settings.DB_PATH.startswith(":memory:"):
    db_dir = os.path.dirname(os.path.abspath(settings.DB_PATH))
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

# Async Engine (SQLite uchun pool sozlamalari yo'q)
engine = create_async_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# Async Session Factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Har bir request uchun yangi session"""
    
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db():
    """Jadvallarni yaratish"""
    # Barcha modellarni import qilish
    from app.database.models import User, Referral, Channel, SecretChannel, Contest, Admin  # noqa
    from app.database.base import Base
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN has_prize_access BOOLEAN DEFAULT 0"))
        except Exception:
            pass


async def drop_db():
    from app.database.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
