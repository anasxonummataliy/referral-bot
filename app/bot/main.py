"""
Bot instance va Dispatcher.

on_startup:
  - setup_bot_commands — user va admin commandlarini o'rnatadi
  - Bu webhook va polling ikkalasida ham ishlaydi
"""
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Bot va Dispatcher ─────────────────────────────────────────────────────────
bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML),
)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ── Middlewares ───────────────────────────────────────────────────────────────
from app.bot.middlewares.database import DatabaseMiddleware
from app.bot.middlewares.subscription import SubscriptionMiddleware

dp.update.outer_middleware(DatabaseMiddleware())
dp.message.middleware(SubscriptionMiddleware())
dp.callback_query.middleware(SubscriptionMiddleware())

# ── Handlers ──────────────────────────────────────────────────────────────────
from app.bot.handlers import all_handler

dp.include_router(all_handler)


# ── on_startup — commandlarni o'rnatish ──────────────────────────────────────
@dp.startup()
async def on_startup(bot: Bot) -> None:
    """
    Bot ishga tushganda avtomatik chaqiriladi.
    User va admin commandlarini Telegram'ga ro'yxatdan o'tkazadi.
    """
    from app.bot.commands import setup_bot_commands
    from app.repositories.admin_repo import AdminRepository
    from app.database.session import AsyncSessionLocal as async_session_maker

    try:
        async with async_session_maker() as session:
            admin_repo = AdminRepository(session)
            db_admin_ids = [a.telegram_id for a in await admin_repo.get_all_admins()]

        all_admin_ids = list(set(settings.ADMIN_IDS + db_admin_ids))
        await setup_bot_commands(bot, admin_ids=all_admin_ids)
        logger.info(f"✅ Bot commandlari o'rnatildi. Adminlar: {all_admin_ids}")
    except Exception as e:
        logger.warning(f"on_startup setup_bot_commands xatolik: {e}")
        # Faqat .env adminlari bilan urinib ko'ramiz
        try:
            from app.bot.commands import setup_bot_commands
            await setup_bot_commands(bot, admin_ids=settings.ADMIN_IDS)
        except Exception as e2:
            logger.error(f"on_startup fallback ham xato: {e2}")


__all__ = ["bot", "dp"]
