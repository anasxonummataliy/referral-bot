import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request

from app.bot.commands import setup_bot_commands
from app.bot.main import bot, dp
from app.core.config import settings
from app.database.session import init_db

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    bot_info = await bot.get_me()
    if not settings.BOT_USERNAME:
        settings.BOT_USERNAME = bot_info.username
    print(f"🤖 Bot ishga tushdi: @{bot_info.username} ({bot_info.id})")
    try:
        await setup_bot_commands(bot, admin_ids=settings.ADMIN_IDS)
    except Exception as e:
        print(f"⚠️ Commandlarni o'rnatishda xatolik: {e}")
    await bot.set_webhook(
        url=f"{settings.WEBHOOK_HOST}{settings.WEBHOOK_PATH}",
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query", "chat_member", "my_chat_member"],
    )
    print(f"✅ Webhook sozlandi: {settings.WEBHOOK_HOST}{settings.WEBHOOK_PATH}")
    yield
    print("⛔ Bot to‘xtamoqda...")
    await bot.session.close()


app = FastAPI(lifespan=lifespan, title="Referral Bot")


@app.post(settings.WEBHOOK_PATH)
async def webhook(request: Request):
    """Aiogram webhook"""
    data = await request.json()
    try:
        await dp.feed_raw_update(bot, data)
    except Exception as e:
        logger.exception("Webhook update processing error: %s", e)
    return {"status": "ok"}


# Health check
@app.get("/")
async def health():
    return {"status": "running", "bot": settings.BOT_USERNAME}
