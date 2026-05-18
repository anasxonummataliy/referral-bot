"""
Subscription middleware — foydalanuvchi barcha kanallarga obuna bo'lganligini tekshiradi.
Admin, /start va check_subscription callbacki bundan mustasno.
"""
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Callable, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from app.services.subscription_service import SubscriptionService
from app.core.config import settings


# Middleware ishlamaydigan callbacklar
_SKIP_CALLBACKS = {"check_subscription"}

# Middleware ishlamaydigan commandlar
_SKIP_COMMANDS = {"/start"}


class SubscriptionMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler: Callable,
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        if not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id

        # Admin — tekshirishsiz o'tkazish
        if settings.is_admin(user_id):
            return await handler(event, data)

        db: AsyncSession = data.get("db")
        if not db:
            return await handler(event, data)

        # /start va check_subscription — o'tkazish (ular o'zi tekshiradi)
        if isinstance(event, Message):
            text = (event.text or "").strip()
            if text.startswith("/start"):
                return await handler(event, data)

        if isinstance(event, CallbackQuery) and event.data in _SKIP_CALLBACKS:
            return await handler(event, data)

        sub_service = SubscriptionService(db)
        is_subscribed = await sub_service.check_full_subscription(
            bot=data["bot"], telegram_id=user_id
        )

        if is_subscribed:
            return await handler(event, data)

        await self._send_subscription_message(event, db, data["bot"])
        return

    async def _send_subscription_message(
        self, event: Message | CallbackQuery, db: AsyncSession, bot
    ):
        """Majburiy obuna xabarini yuborish."""
        from app.repositories.contest_repo import ContestRepository

        sub_service = SubscriptionService(db)
        channels = await sub_service.get_required_channels()

        contest_repo = ContestRepository(db)
        contest = await contest_repo.get_active_contest()

        # Konkurs matni
        if contest and contest.welcome_message:
            import re
            contest_block = re.sub(r"<[^>]+>", "", contest.welcome_message).strip()
            text = (
                f"{contest.welcome_message.strip()}\n\n"
                f"━━━━━━━━━━━━━━━━━━━\n\n"
                f"📌 <b>Konursda qatnashishdan avval quyidagi kanallarga a'zo bo'ling:</b>\n\n"
                f"A'zo bo'lgach <b>✅ A'zo bo'ldim — tekshirish</b> tugmasini bosing."
            )
        elif contest:
            text = (
                f"🏆 <b>{contest.title}</b>\n\n"
                f"━━━━━━━━━━━━━━━━━━━\n\n"
                f"📌 <b>Konursda qatnashishdan avval quyidagi kanallarga a'zo bo'ling:</b>\n\n"
                f"A'zo bo'lgach <b>✅ A'zo bo'ldim — tekshirish</b> tugmasini bosing."
            )
        else:
            text = (
                f"👋 <b>Assalomu alaykum!</b>\n\n"
                f"📌 Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:\n\n"
                f"A'zo bo'lgach <b>✅ A'zo bo'ldim — tekshirish</b> tugmasini bosing."
            )

        buttons = []
        for ch in channels:
            if ch.username:
                link = f"https://t.me/{ch.username.lstrip('@')}"
                icon = "📢"
            else:
                link = f"https://t.me/c/{abs(ch.channel_id)}"
                icon = "🔒"
            buttons.append([
                InlineKeyboardButton(text=f"{icon} {ch.title}", url=link)
            ])

        buttons.append([
            InlineKeyboardButton(
                text="✅ A'zo bo'ldim — tekshirish",
                callback_data="check_subscription",
            )
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        try:
            if isinstance(event, Message):
                await event.answer(
                    text, reply_markup=keyboard, disable_web_page_preview=True
                )
            elif isinstance(event, CallbackQuery):
                try:
                    await event.message.edit_text(
                        text, reply_markup=keyboard, disable_web_page_preview=True
                    )
                except Exception:
                    await event.message.answer(
                        text, reply_markup=keyboard, disable_web_page_preview=True
                    )
        except Exception:
            pass
