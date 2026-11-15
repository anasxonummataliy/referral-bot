import asyncio
import time
import logging
from typing import Sequence
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from app.repositories.channel_repo import ChannelRepository
from app.repositories.user_repo import UserRepository
from app.database.models import Channel

logger = logging.getLogger(__name__)

# Kesh: (channel_id, user_id) -> (is_member, expire_timestamp)
_SUB_CACHE: dict[tuple[int, int], tuple[bool, float]] = {}
_CACHE_TTL = 25.0  # 25 soniya


async def _check_single_channel_member(
    bot: Bot, channel: Channel, user_id: int, bypass_cache: bool = False
) -> bool:
    """
    Bitta kanal bo'yicha a'zolikni tekshirish.
    Xatoliklar xavfsiz boshqariladi:
    - 429 (RetryAfter) -> kutib qayta urinadi
    - Forbidden/boshqa sozlama xatolari -> foydalanuvchini jazolamay True qaytaradi
    - Participant invalid/not found -> kanalda yo'q (False)
    """
    cache_key = (channel.channel_id, user_id)
    now = time.monotonic()
    if not bypass_cache and cache_key in _SUB_CACHE:
        is_mem, exp = _SUB_CACHE[cache_key]
        if now < exp:
            return is_mem

    retries = 2
    while retries >= 0:
        try:
            member = await bot.get_chat_member(
                chat_id=channel.channel_id, user_id=user_id
            )
            status = getattr(member, "status", None)
            if status in ["creator", "administrator", "member"]:
                is_mem = True
            elif status == "restricted":
                is_mem = bool(getattr(member, "is_member", True))
            else:
                is_mem = False

            _SUB_CACHE[cache_key] = (is_mem, now + _CACHE_TTL)
            return is_mem
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after)
            retries -= 1
        except TelegramForbiddenError as e:
            # Bot kanaldan chiqarilgan yoki admin huquqi yo'q — foydalanuvchini jazolamaymiz!
            logger.error(
                f"Kanal sozlamasi xato (bot admin emas yoki chiqarilgan) {channel.channel_id} ({channel.title}): {e}"
            )
            return True
        except TelegramBadRequest as e:
            err_msg = str(e).lower()
            if any(x in err_msg for x in ["participant_id_invalid", "user_not_participant", "user not found"]):
                _SUB_CACHE[cache_key] = (False, now + _CACHE_TTL)
                return False
            # Boshqa Telegram xatoliklari (chat topilmadi, kanal yopiq va h.k.) — foydalanuvchini jazolamaymiz
            logger.error(f"Kanal tekshirishda xatolik {channel.channel_id} ({channel.title}): {e}")
            return True
        except Exception as e:
            logger.error(
                f"get_chat_member kutilmagan xatolik {channel.channel_id} ({channel.title}, user={user_id}): {e}"
            )
            return True
    return False


class SubscriptionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.channel_repo = ChannelRepository(db)
        self.user_repo = UserRepository(db)

    async def get_required_channels(self) -> Sequence[Channel]:
        return await self.channel_repo.get_required_channels()

    async def get_unsubscribed_channels(
        self, bot: Bot, telegram_id: int, bypass_cache: bool = False
    ) -> list[Channel]:
        """
        Foydalanuvchi obuna bo'lmagan majburiy kanallar ro'yxatini qaytaradi.
        Tekshiruv parallel (asyncio.gather) orqali bajariladi.
        """
        required_channels = await self.get_required_channels()
        if not required_channels:
            return []

        # Barcha kanallarni parallel tekshirish
        tasks = [
            _check_single_channel_member(bot, ch, telegram_id, bypass_cache=bypass_cache)
            for ch in required_channels
        ]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        unsubscribed = [
            ch for ch, is_mem in zip(required_channels, results) if not is_mem
        ]
        return unsubscribed

    async def check_full_subscription(
        self, bot: Bot, telegram_id: int, bypass_cache: bool = False
    ) -> bool:
        """Foydalanuvchi barcha majburiy kanallarga obuna bo'lganligini tekshiradi"""
        unsubscribed = await self.get_unsubscribed_channels(
            bot, telegram_id, bypass_cache=bypass_cache
        )
        is_sub = len(unsubscribed) == 0
        await self.user_repo.update_subscription_status(telegram_id, is_sub)
        return is_sub
