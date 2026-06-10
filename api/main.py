# api/main.py
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager

from app.bot.main import bot, dp
from app.core.config import settings
from app.database.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await bot.set_webhook(url=f"{settings.WEBHOOK_HOST}{settings.WEBHOOK_PATH}", drop_pending_updates=True)
    print(f"✅ Webhook sozlandi: {settings.WEBHOOK_HOST}{settings.WEBHOOK_PATH}")
    yield
    print("⛔ Bot to‘xtamoqda...")
    await bot.session.close()


app = FastAPI(lifespan=lifespan, title="Referral Bot")


@app.post(settings.WEBHOOK_PATH)
async def webhook(request: Request):
    """Aiogram webhook"""
    data = await request.json()
    await dp.feed_raw_update(bot, data)
    return {"status": "ok"}


# Health check
@app.get("/")
async def health():
    return {"status": "running", "bot": settings.BOT_USERNAME}
