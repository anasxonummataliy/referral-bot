"""
Prize link yaratish va yuborish.

Muhim:
- Bot prize kanalda ADMIN bo'lishi shart (Invite Links huquqi bilan)
- member_limit=1 → faqat 1 kishi kiradi (Telegram tomonidan kafolatlangan)
- expires_date=None → muddat cheklanmagan (ammo 1 marta ishlatilgach bekor bo'ladi)
- Webhook muhitida bu to'g'ri ishlaydi — Telegram API tomonidan boshqariladi
"""
import logging
from datetime import datetime, timedelta, timezone

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.contest_repo import ContestRepository
from app.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)


async def send_prize_link(bot: Bot, user_id: int, contest) -> None:
    """
    1 martalik invite link yaratib, inline button orqali yuborish.

    Talablar:
    - Bot prize kanalda ADMIN (Invite Links huquqi bilan)
    - contest.prize_channel_id to'g'ri bo'lishi kerak
    """
    if not contest or not contest.prize_channel_id:
        logger.warning(
            f"send_prize_link: contest yoki prize_channel_id yo'q (user={user_id})"
        )
        return

    try:
        # 1 martalik link — faqat 1 kishi kiradi, webhook bilan ham ishlaydi
        invite = await bot.create_chat_invite_link(
            chat_id=contest.prize_channel_id,
            member_limit=1,               # Faqat 1 kishi
            creates_join_request=False,   # To'g'ridan kiradi
            # expire_date ni o'rnatmaymiz — link ishlatilguncha amal qiladi
        )

        channel_title = contest.prize_channel_title or "Sovrin Kanal"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=f"🎁 {channel_title} — Kirish",
                url=invite.invite_link,
            )
        ]])

        await bot.send_message(
            chat_id=user_id,
            text=(
                f"🏆 <b>Tabriklaymiz!</b>\n\n"
                f"Siz <b>{contest.required_referrals} ta</b> do'st taklif qildingiz "
                f"va sovrinni yutib oldingiz! 🎉\n\n"
                f"⬇️ Quyidagi tugmani bosib kanalga kiring:\n\n"
                f"⚠️ <b>Diqqat:</b> Bu havola faqat <b>1 marta</b> ishlaydi!\n"
                f"Uni boshqa birovga bermang — kirish huquqi faqat <b>sizga</b>."
            ),
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        logger.info(f"✅ Prize link yuborildi: user={user_id}, contest={contest.id}")

    except Exception as e:
        logger.error(
            f"❌ Prize link xatolik (user={user_id}, channel={contest.prize_channel_id}): {e}"
        )
        # Xatolik bo'lsa adminlarga xabar yuborish mumkin (kelajakda)


async def check_and_send_prize(
    bot: Bot, referrer_telegram_id: int, db: AsyncSession
) -> bool:
    """
    Referrer shartni bajardimi tekshirish.
    Aynan required_referrals ga yetganda (== tekshiruvi) bir martalik prize link yuborish.
    """
    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()
    if not contest or not contest.prize_channel_id:
        return False

    user_repo = UserRepository(db)
    referrer = await user_repo.get_by_telegram_id(referrer_telegram_id)
    if not referrer:
        return False

    # == tekshiruvi: qayta-qayta yuborilmasligi uchun
    if referrer.referral_count == contest.required_referrals:
        await send_prize_link(bot, referrer_telegram_id, contest)
        return True
    return False
