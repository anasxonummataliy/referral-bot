# bot/handlers/admin/base.py
from aiogram import Router
from app.core.config import settings

admin_router = Router(name="admin")


def is_admin(user_id: int) -> bool:
    """Admin tekshiruvi"""
    return user_id in settings.ADMIN_IDS
