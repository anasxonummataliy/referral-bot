from aiogram import Router
from app.bot.handlers.user import user_router
from app.bot.handlers.admin import admin_router

all_handler = Router()

# Admin router birinchi (yuqori priority)
all_handler.include_routers(admin_router, user_router)
