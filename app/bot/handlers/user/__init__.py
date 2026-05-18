"""
User handlers — barcha modullarni birlashtirish
"""
from aiogram import Router

from app.bot.handlers.user.start import router as start_router
from app.bot.handlers.user.share import router as share_router
from app.bot.handlers.user.stats import router as stats_router
from app.bot.handlers.user.info import router as info_router

user_router = Router()
user_router.include_router(start_router)
user_router.include_router(share_router)
user_router.include_router(stats_router)
user_router.include_router(info_router)

__all__ = ["user_router"]
