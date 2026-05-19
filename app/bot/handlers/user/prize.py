"""
Prize link yaratish va yuborish.

MUHIM — Bir martalik link va webhook:
- create_chat_invite_link() — bu Telegram API chaqiruvi, polling/webhook bilan bog'liq EMAS
- member_limit=1 → faqat 1 kishi kiradi (Telegram serveri tomonidan kafolatlangan)
- Bot prize kanalda ADMIN va "Invite Links" huquqiga ega bo'lishi SHART

Agar link yaratilmayotgan bo'lsa — bot kanalda admin emas yoki huquq yo'q.
"""
import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.contest_repo import ContestRepository
from app.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)


async def send_prize_link(bot: Bot, user_id: int, contest) -> bool:
    """
    1 martalik invite link yaratib yuborish.
    Returns True — muvaffaqiyatli, False — xato.
    """
    if not contest or not contest.prize_channel_id:
        logger.warning(f"send_prize_link: contest yoki channel_id yo'q (user={user_id})")
        return False

    try:
        invite = await bot.create_chat_invite_link(
            chat_id=contest.prize_channel_id,
            member_limit=1,              # Faqat 1 kishi kiradi
            creates_join_request=False,  # To'g'ridan kiradi
        )
    except Exception as e:
        logger.error(
            f"create_chat_invite_link XATO (user={user_id}, "
            f"channel={contest.prize_channel_id}): {e}"
        )
        return False

    channel_title = contest.prize_channel_title or "Sovrin kanal"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"🎁 {channel_title} — Kirish",
            url=invite.invite_link,
        )
    ]])

    prize_text = (
        "🏆 <b>Tabriklaymiz!</b>\n\n"
        f"Siz <b>{contest.required_referrals} ta</b> do'st taklif qildingiz "
        "va sovrinni yutib oldingiz! 🎉\n\n"
        "⬇️ Quyidagi tugmani bosib kanalga kiring:\n\n"
        "⚠️ <b>Diqqat:</b> Bu havola faqat <b>1 marta</b> ishlaydi!\n"
        "Uni boshqa birovga bermang — kirish huquqi faqat <b>sizga</b>."
    )

    photo_id = getattr(contest, "welcome_photo_file_id", None)

    try:
        if photo_id:
            await bot.send_photo(
                chat_id=user_id,
                photo=photo_id,
                caption=prize_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        else:
            await bot.send_message(
                chat_id=user_id,
                text=prize_text,
                reply_markup=keyboard,
                parse_mode="HTML",
            )
        logger.info(f"✅ Prize link yuborildi: user={user_id}, contest={contest.id}")
        return True
    except Exception as e:
        logger.error(f"send_message XATO (user={user_id}): {e}")
        return False


async def check_and_send_prize(
    bot: Bot, referrer_telegram_id: int, db: AsyncSession
) -> bool:
    """
    Referrer shartni bajardimi? — tekshirish va prize yuborish.
    == tekshiruvi: aynan required_referrals ga yetganida (qayta yubormasligi uchun).
    """
    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()
    if not contest or not contest.prize_channel_id:
        return False

    user_repo = UserRepository(db)
    referrer = await user_repo.get_by_telegram_id(referrer_telegram_id)
    if not referrer:
        return False

    if referrer.referral_count == contest.required_referrals:
        return await send_prize_link(bot, referrer_telegram_id, contest)
    return False
