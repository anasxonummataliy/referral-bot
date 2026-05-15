# middlewares/subscription.py
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from services.subscription_service import SubscriptionService
from core.config import settings


class SubscriptionMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler: Callable,
        event: Message | CallbackQuery,
        data: Dict[str, Any],
    ) -> Any:

        user_id = event.from_user.id

        # ==================== ADMIN TEKSHIRISH ====================
        if settings.is_admin(user_id):
            return await handler(
                event, data
            )  # Admin bo'lsa to'g'ridan-to'g'ri o'tkazib yuboramiz

        # ==================== ODDIY FOYDALANUVCHI ====================
        db: AsyncSession = data.get("db")
        if not db:
            return await handler(event, data)

        subscription_service = SubscriptionService(db)

        is_subscribed = await subscription_service.check_full_subscription(
            bot=data["bot"], telegram_id=user_id
        )

        if is_subscribed:
            return await handler(event, data)
        else:
            await self.send_subscription_message(event, data)
            return  # handler to'xtatiladi

    async def send_subscription_message(
        self, event: Message | CallbackQuery, data: Dict
    ):
        """Majburiy obuna xabarini yuborish"""
        bot = data["bot"]
        required_channels = await SubscriptionService(
            data["db"]
        ).get_required_channels()

        text = (
            "👋 <b>Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:</b>\n\n"
        )

        keyboard = []
        for channel in required_channels:
            if channel.username:
                link = f"https://t.me/{channel.username.lstrip('@')}"
                keyboard.append([{"text": f"📢 {channel.title}", "url": link}])
            else:
                keyboard.append(
                    [
                        {
                            "text": f"📢 {channel.title}",
                            "url": f"https://t.me/c/{channel.channel_id}",
                        }
                    ]
                )

        keyboard.append(
            [{"text": "✅ Obunani tekshirish", "callback_data": "check_subscription"}]
        )

        try:
            if isinstance(event, Message):
                await event.answer(
                    text,
                    reply_markup={"inline_keyboard": keyboard},
                    disable_web_page_preview=True,
                )
            elif isinstance(event, CallbackQuery):
                await event.message.edit_text(
                    text,
                    reply_markup={"inline_keyboard": keyboard},
                    disable_web_page_preview=True,
                )
        except:
            # Agar xabar allaqachon yuborilgan bo'lsa
            pass
