from aiogram import Router
from .start import router as start
from .admin import admin_router

all_handler = Router()

all_handler.include_routers(admin_router, start)
