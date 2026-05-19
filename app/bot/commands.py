"""
Bot commandlarini o'rnatish — user va admin uchun alohida scope.

Telegram BotCommandScope:
  - BotCommandScopeDefault          → barcha userlar (user commandlari)
  - BotCommandScopeChat(chat_id)    → faqat shu chat (admin commandlari)

Ishlatish:
  await setup_bot_commands(bot, admin_ids=[123456, 789012])
"""
import logging

from aiogram import Bot
from aiogram.types import (
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeChat,
)

logger = logging.getLogger(__name__)

# ── User commandlari (barcha foydalanuvchilar ko'radi) ────────────────────────
USER_COMMANDS = [
    BotCommand(command="start",    description="🏠 Bosh menyu"),
    BotCommand(command="referral", description="🔗 Mening taklif havolam"),
    BotCommand(command="link",     description="🔗 Referral link"),
    BotCommand(command="mystats",  description="📊 Mening natijam"),
    BotCommand(command="natija",   description="📈 Mening natijam"),
    BotCommand(command="contact",  description="✉️ Adminlarga yozish"),
    BotCommand(command="help",     description="❓ Yordam"),
]

# ── Admin commandlari (faqat adminlar ko'radi) ────────────────────────────────
ADMIN_COMMANDS = [
    BotCommand(command="start",       description="🏠 Bosh menyu"),
    BotCommand(command="admin",       description="🛡️ Admin panel"),
    BotCommand(command="contest",     description="🏆 Konkursni boshqarish"),
    BotCommand(command="broadcast",   description="📢 Xabar yuborish"),
    BotCommand(command="stats",       description="📊 Statistika"),
    BotCommand(command="statistics",  description="📊 Batafsil statistika"),
    BotCommand(command="channels",    description="📡 Kanallarni ko'rish"),
    BotCommand(command="channel",     description="📡 Kanallarni boshqarish"),
    BotCommand(command="addchannel",  description="➕ Kanal qo'shish"),
    BotCommand(command="giftchannel", description="🎁 Sovrin kanalini boshqarish"),
    BotCommand(command="referral",    description="🔗 Mening taklif havolam"),
    BotCommand(command="link",        description="🔗 Referral link"),
    BotCommand(command="mystats",     description="📈 Mening natijam"),
    BotCommand(command="natija",      description="📈 Mening natijam"),
    BotCommand(command="topref",      description="🏅 Top referrer'lar"),
    BotCommand(command="finduser",    description="🔍 Foydalanuvchi qidirish"),
    BotCommand(command="admins",      description="🔑 Adminlarni boshqarish"),
    BotCommand(command="contact",     description="✉️ Adminlarga yozish"),
    BotCommand(command="help",        description="❓ Yordam"),
    BotCommand(command="cancel",      description="❌ Amalni bekor qilish"),
]


async def setup_bot_commands(bot: Bot, admin_ids: list[int]) -> None:
    """
    Barcha foydalanuvchilar uchun user commandlarini,
    har bir admin uchun admin commandlarini o'rnatish.
    """
    # 1. Barcha userlar uchun default (user) commandlar
    try:
        await bot.set_my_commands(
            commands=USER_COMMANDS,
            scope=BotCommandScopeDefault(),
        )
        logger.info("✅ User commandlari o'rnatildi (default scope)")
    except Exception as e:
        logger.error(f"User commandlarini o'rnatishda xatolik: {e}")

    # 2. Har bir admin uchun alohida admin commandlar
    for admin_id in admin_ids:
        try:
            await bot.set_my_commands(
                commands=ADMIN_COMMANDS,
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
            logger.info(f"✅ Admin commandlari o'rnatildi: {admin_id}")
        except Exception as e:
            logger.warning(f"Admin {admin_id} uchun commandlar o'rnatilmadi: {e}")
