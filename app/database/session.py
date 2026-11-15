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

from sqlalchemy import event


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragmas(conn, _):
    """SQLite WAL rejimi va timeout sozlamalari ('database is locked' xatosini oldini olish)"""
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=15000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


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
    from app.database.models import User, Referral, Channel, SecretChannel, Contest, Admin, ContestWinner  # noqa
    from app.database.base import Base
    from sqlalchemy import text

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN has_prize_access BOOLEAN DEFAULT 0"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE contests ADD COLUMN prize_channel_invite_link VARCHAR(255)"))
        except Exception:
            pass
        try:
            await conn.execute(text("ALTER TABLE referrals ADD COLUMN contest_id INTEGER REFERENCES contests(id)"))
        except Exception:
            pass


async def drop_db():
    from app.database.base import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
