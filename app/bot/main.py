# bot/main.py
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.core.config import settings

bot = Bot(
    token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# Handlerslarni ro'yxatdan o'tkazish
from app.bot.handlers import all_handler
from app.bot.middlewares import SubscriptionMiddleware

dp.update.middleware(SubscriptionMiddleware)
dp.include_router(all_handler)


__all__ = ["bot", "dp"]
