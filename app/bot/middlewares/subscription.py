from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Callable, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from app.services.subscription_service import SubscriptionService
from app.core.config import settings


class SubscriptionMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler: Callable,
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:
        # from_user yo'q bo'lsa (kanal postlari) o'tkazib yuborish
        if not event.from_user:
            return await handler(event, data)

        user_id = event.from_user.id

        # Admin bo'lsa tekshirishsiz o'tkazish
        if settings.is_admin(user_id):
            return await handler(event, data)

        db: AsyncSession = data.get("db")
        if not db:
            return await handler(event, data)

        # check_subscription callbackini tekshirmaslik (cheksiz loop oldini olish)
        if isinstance(event, CallbackQuery) and event.data == "check_subscription":
            return await handler(event, data)

        subscription_service = SubscriptionService(db)
        is_subscribed = await subscription_service.check_full_subscription(
            bot=data["bot"], telegram_id=user_id
        )

        if is_subscribed:
            return await handler(event, data)

        await self._send_subscription_message(event, db, data["bot"])
        return

    async def _send_subscription_message(
        self, event: Message | CallbackQuery, db: AsyncSession, bot
    ):
        """Majburiy obuna xabarini yuborish"""
        subscription_service = SubscriptionService(db)
        required_channels = await subscription_service.get_required_channels()

        text = "👋 <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>\n\n"

        buttons = []
        for channel in required_channels:
            if channel.username:
                link = f"https://t.me/{channel.username.lstrip('@')}"
            else:
                link = f"https://t.me/c/{abs(channel.channel_id)}"

            buttons.append([
                InlineKeyboardButton(text=f"📢 {channel.title}", url=link)
            ])

        buttons.append([
            InlineKeyboardButton(text="✅ Obunani tekshirish", callback_data="check_subscription")
        ])

        keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

        try:
            if isinstance(event, Message):
                await event.answer(
                    text,
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
            elif isinstance(event, CallbackQuery):
                await event.message.edit_text(
                    text,
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
        except Exception:
            pass
