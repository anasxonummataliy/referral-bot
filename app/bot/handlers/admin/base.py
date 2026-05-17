from aiogram import Router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings

admin_router = Router(name="admin")

# ── DB-dagi adminlar cache ───────────────────────────────────────────────────
_db_admin_ids: set[int] = set()


def is_admin(user_id: int) -> bool:
    """.env dan VA db dan adminlikni tekshiradi"""
    return user_id in settings.ADMIN_IDS or user_id in _db_admin_ids


async def is_admin_async(user_id: int, db: AsyncSession) -> bool:
    """DB dan real-time tekshirish"""
    if user_id in settings.ADMIN_IDS:
        return True
    from app.repositories.admin_repo import AdminRepository
    admin_repo = AdminRepository(db)
    admin = await admin_repo.get_by_telegram_id(user_id)
    if admin and admin.is_active:
        _db_admin_ids.add(user_id)
        return True
    return False


def add_to_cache(user_id: int) -> None:
    _db_admin_ids.add(user_id)


def remove_from_cache(user_id: int) -> None:
    _db_admin_ids.discard(user_id)


def admin_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🏆 Konkurs", callback_data="adm_contest"),
            InlineKeyboardButton(text="🎁 Prize kanal", callback_data="adm_prize"),
        ],
        [
            InlineKeyboardButton(text="📢 Kanallar", callback_data="adm_channels"),
            InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="adm_users"),
        ],
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data="adm_stats"),
            InlineKeyboardButton(text="📤 Broadcast", callback_data="adm_broadcast"),
        ],
        [
            InlineKeyboardButton(text="🔑 Adminlar", callback_data="adm_admins"),
        ],
    ])
