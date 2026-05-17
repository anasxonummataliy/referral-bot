from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.core.config import settings

# Bot va Dispatcher
bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

# FSM uchun storage (Redis o'rnatilgan bo'lsa RedisStorage ishlatish mumkin)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ==================== MIDDLEWARES ====================
from app.bot.middlewares.database import DatabaseMiddleware
from app.bot.middlewares.subscription import SubscriptionMiddleware

# 1. Database middleware — barcha handlerlardan OLDIN ishlaydi
dp.update.outer_middleware(DatabaseMiddleware())

# 2. Subscription middleware — faqat message va callback uchun
dp.message.middleware(SubscriptionMiddleware())
dp.callback_query.middleware(SubscriptionMiddleware())

# ==================== HANDLERS ====================
from app.bot.handlers import all_handler

dp.include_router(all_handler)


__all__ = ["bot", "dp"]
