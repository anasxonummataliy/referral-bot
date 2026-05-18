"""
Yangi referral kelganda referrerga bildirishnoma yuborish.
"""
import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.deep_linking import create_deep_link
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.repositories.contest_repo import ContestRepository
from app.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)


async def notify_referrer(
    bot: Bot,
    referrer_telegram_id: int,
    new_user_name: str,
    db: AsyncSession,
) -> None:
    """
    Referrerga yangi do'st qo'shilgani haqida xabar yuborish.
    Xabar tarkibi: admin matni (agar bo'lsa) + avtomatik natija + taklif tugmasi.
    """
    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()

    user_repo = UserRepository(db)
    referrer = await user_repo.get_by_telegram_id(referrer_telegram_id)
    if not referrer:
        return

    ref_count = referrer.referral_count
    target = contest.required_referrals if contest else 5
    remaining = max(0, target - ref_count)
    prize_name = (contest.prize_channel_title or "Prize Kanal") if contest else "Prize Kanal"

    # ── Matn ─────────────────────────────────────────────────────────────────
    parts = []

    # 1. Admin tomonidan yozilgan maxsus matn (agar mavjud bo'lsa)
    if contest and getattr(contest, "referral_message", None):
        parts.append(contest.referral_message.strip())
        parts.append("")

    # 2. Avtomatik bildirishnoma
    parts.append(f"🎉 <b>{new_user_name}</b> sizning havolangiz orqali qo'shildi!")
    parts.append("")

    if contest:
        parts.append(f"🏆 <b>{contest.title}</b>")
        parts.append(f"📊 Natijangiz: <b>{ref_count} / {target}</b>")
        parts.append("")

        if remaining > 0:
            parts.append(
                f"🎯 Yana <b>{remaining} ta</b> do'st taklif qiling "
                f"→ <b>{prize_name}</b> yutib olasiz!"
            )
        else:
            parts.append(
                f"✅ Tabriklaymiz! Shartni bajardingiz — "
                f"<b>{prize_name}</b> havolasi yuborilmoqda..."
            )

    full_text = "\n".join(parts)

    # ── Keyboard — referrerning o'z deeplinki ────────────────────────────────
    bot_info = await bot.get_me()
    bot_username = settings.BOT_USERNAME or bot_info.username

    # Referrerning deeplink havolasi (yangi do'st bu havola orqali kirsa +1 bo'ladi)
    referral_link = create_deep_link(
        username=bot_username,
        payload=str(referrer_telegram_id),
        encode=True,
        link_type="start",
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔗 Yana do'st taklif qilish ↗",
            url=f"https://t.me/share/url?url={referral_link}",
        )],
    ])

    try:
        await bot.send_message(
            chat_id=referrer_telegram_id,
            text=full_text,
            reply_markup=keyboard,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        logger.info(
            f"Referral notify yuborildi: referrer={referrer_telegram_id}, new_user={new_user_name}"
        )
    except Exception as e:
        logger.error(
            f"Referral notify xatolik (referrer={referrer_telegram_id}): {e}"
        )
