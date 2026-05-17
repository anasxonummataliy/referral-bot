from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from app.database.session import AsyncSessionLocal


class DatabaseMiddleware(BaseMiddleware):
    """Har bir update uchun database session yaratadi"""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with AsyncSessionLocal() as session:
            data["db"] = session
            try:
                return await handler(event, data)
            finally:
                await session.close()
