"""
Umumiy yordamchi funksiyalar — barcha user handlerlar uchun
"""
import logging
import re as _re
import html as _html_module

from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

logger = logging.getLogger(__name__)

# Telegram qo'llab-quvvatlaydigan HTML teglar
_ALLOWED_TAGS = {
    "b", "strong", "i", "em", "u", "ins", "s", "strike", "del",
    "code", "pre", "a", "tg-spoiler", "tg-emoji", "blockquote", "br",
}


def _has_unsupported_html(text: str) -> bool:
    tags = _re.findall(r"</?([\w][\w\d-]*)", text)
    return any(t.lower() not in _ALLOWED_TAGS for t in tags)


async def safe_send_message(message: Message, text: str) -> None:
    """HTML tekshirib xavfsiz yuborish"""
    if "<" in text and _has_unsupported_html(text):
        logger.warning("welcome_message: noto'g'ri HTML — plain text sifatida yuborilmoqda")
        await message.answer(text, parse_mode=None, disable_web_page_preview=True)
    else:
        await message.answer(text, disable_web_page_preview=True)


async def safe_answer(
    callback: CallbackQuery, text: str = "", show_alert: bool = False
) -> None:
    """callback.answer() xatolikni yutib yuboradi (30s limit)"""
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramBadRequest as e:
        logger.warning(f"callback.answer() xatoligi (user={callback.from_user.id}): {e}")
    except Exception as e:
        logger.warning(f"callback.answer() noma'lum xatolik: {e}")


def progress_bar(current: int, total: int) -> str:
    if total <= 0:
        total = 5
    filled = min(int(current / total * 5), 5)
    empty = 5 - filled
    pct = min(int(current / total * 100), 100)
    bar = "🟩" * filled + "⬜" * empty
    return f"{bar}\n{current}/{total} ({pct}%)"
