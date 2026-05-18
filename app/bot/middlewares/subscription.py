"""
Subscription middleware.

Qoidalar:
- /start command → o'tkazib yuboradi (start handler o'zi tekshiradi)
- check_subscription callback → o'tkazib yuboradi (u ham o'zi tekshiradi)
- Admin → o'tkazib yuboradi
- Qolgan hammasi → obuna tekshiruvi

Obuna yo'q bo'lsa — konkurs matni + kanallar bitta postda.
"""
import re
import logging
from typing import Callable, Dict, Any

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.subscription_service import SubscriptionService
from app.core.config import settings

logger = logging.getLogger(__name__)

_SKIP_CALLBACKS = {"check_subscription"}


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

        # Admin — tekshirishsiz
        if settings.is_admin(user_id):
            return await handler(event, data)

        db: AsyncSession = data.get("db")
        if not db:
            return await handler(event, data)

        # /start — start handler o'zi tekshiradi
        if isinstance(event, Message):
            text = (event.text or "").strip()
            if text.startswith("/start"):
                return await handler(event, data)

        # check_subscription — handler o'zi tekshiradi
        if isinstance(event, CallbackQuery) and event.data in _SKIP_CALLBACKS:
            return await handler(event, data)

        sub_service = SubscriptionService(db)
        is_subscribed = await sub_service.check_full_subscription(
            bot=data["bot"], telegram_id=user_id
        )

        if is_subscribed:
            return await handler(event, data)

        # Obuna yo'q — konkurs matni + kanallar
        await self._send_subscription_prompt(event, db)
        return

    async def _send_subscription_prompt(
        self,
        event: Message | CallbackQuery,
        db: AsyncSession,
    ) -> None:
        from app.repositories.contest_repo import ContestRepository

        sub_service = SubscriptionService(db)
        channels = await sub_service.get_required_channels()

        contest_repo = ContestRepository(db)
        contest = await contest_repo.get_active_contest()

        # Matn
        if contest and contest.welcome_message:
            text = (
                f"{contest.welcome_message.strip()}\n\n"
                "━━━━━━━━━━━━━━━━━━━\n\n"
                "📌 <b>Konursda qatnashishdan avval quyidagi kanallarga a'zo bo'ling:</b>"
            )
        elif contest:
            text = (
                f"🏆 <b>{contest.title}</b>\n\n"
                "━━━━━━━━━━━━━━━━━━━\n\n"
                "📌 <b>Konursda qatnashishdan avval quyidagi kanallarga a'zo bo'ling:</b>"
            )
        else:
            text = (
                "👋 <b>Assalomu alaykum!</b>\n\n"
                "📌 <b>Botdan foydalanish uchun quyidagi kanallarga a'zo bo'ling:</b>"
            )

        # Keyboard
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
        except Exception as e:
            logger.error(f"_send_subscription_prompt xato: {e}")
