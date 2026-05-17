from aiogram import Router
from .start import router as start_router
from .admin import admin_router

all_handler = Router()

# Admin router birinchi (priority yuqori)
all_handler.include_routers(admin_router, start_router)
