import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

from app.bot.commands import setup_bot_commands
from app.bot.main import bot, dp
from app.core.config import settings
from app.database.session import init_db

logger = logging.getLogger(__name__)

_polling_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _polling_task
    await init_db()

    # Webhookni tozalaymiz (pending updates o'chirilmaydi: drop_pending_updates=False)
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        print("✅ Webhook o'chirildi, Polling rejimiga o'tildi.")
    except Exception as e:
        logger.warning(f"delete_webhook xatolik: {e}")

    bot_info = await bot.get_me()
    if not settings.BOT_USERNAME:
        settings.BOT_USERNAME = bot_info.username
    print(f"🤖 Bot ishga tushdi (POLLING): @{bot_info.username} ({bot_info.id})")

    try:
        await setup_bot_commands(bot, admin_ids=settings.ADMIN_IDS)
    except Exception as e:
        logger.warning(f"⚠️ Commandlarni o'rnatishda xatolik: {e}")

    # Pollingni alohida asyncio task sifatida boshlaymiz
    _polling_task = asyncio.create_task(
        dp.start_polling(
            bot,
            allowed_updates=["message", "callback_query", "chat_member", "my_chat_member"],
            drop_pending_updates=False,
        )
    )

    yield

    print("⛔ Bot to'xtamoqda...")
    if _polling_task:
        _polling_task.cancel()
        try:
            await _polling_task
        except asyncio.CancelledError:
            pass
    await bot.session.close()


app = FastAPI(lifespan=lifespan, title="Referral Bot")


@app.post(settings.WEBHOOK_PATH)
async def webhook(request: Request):
    """Aiogram webhook endpoint"""
    try:
        data = await request.json()
        await dp.feed_raw_update(bot, data)
    except Exception as e:
        logger.exception("Webhook update processing error: %s", e)
    return {"status": "ok"}


# Health check
@app.get("/")
async def health():
    return {
        "status": "running",
        "mode": "polling",
        "bot": settings.BOT_USERNAME,
    }
