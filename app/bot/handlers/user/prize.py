"""
Prize link yaratish, yuborish va kanaldan chiqarish logikasi.

MUHIM:
- create_chat_invite_link() — Telegram API orqali 1 martalik link (member_limit=1)
- Bot prize kanalda ADMIN, "Invite Links" va "Ban Users" huquqiga ega bo'lishi SHART
- Foydalanuvchi majburiy kanallardan biridan chiqib ketsa — yopiq kanaldan chiqariladi
- Barcha kanallarga qayta a'zo bo'lsa — unga yangi 1 martalik link beriladi
"""
import logging

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.contest_repo import ContestRepository
from app.repositories.user_repo import UserRepository

logger = logging.getLogger(__name__)


async def is_user_in_prize_channel(bot: Bot, prize_channel_id: int, user_id: int) -> bool:
    """Foydalanuvchi allaqachon sovg'a kanalida bor-yo'qligini tekshiradi."""
    try:
        member = await bot.get_chat_member(chat_id=prize_channel_id, user_id=user_id)
        if getattr(member, "status", None) in ["creator", "administrator", "member"]:
            return True
        if getattr(member, "status", None) == "restricted" and getattr(member, "is_member", True):
            return True
        return False
    except Exception as e:
        logger.debug(f"is_user_in_prize_channel check (user={user_id}): {e}")
        return False


async def kick_user_from_prize_channel(bot: Bot, prize_channel_id: int, user_id: int) -> bool:
    """
    Foydalanuvchini yopiq kanaldan chiqarib yuborish.
    Telegramda kanaldan chiqarish uchun ban_chat_member va keyin unban_chat_member qilinadi.
    Bu orqali user kanaldan chiqariladi, lekin kelajakda yangi link bilan qayta kira oladi.
    """
    try:
        await bot.ban_chat_member(chat_id=prize_channel_id, user_id=user_id)
        # Ban ro'yxatidan darhol chiqaramiz, shunda yangi invite link olganida kira oladi
        await bot.unban_chat_member(chat_id=prize_channel_id, user_id=user_id, only_if_banned=True)
        logger.info(f"✅ User {user_id} yopiq kanaldan ({prize_channel_id}) chiqarildi.")
        return True
    except Exception as e:
        logger.warning(
            f"Prize kanaldan chiqarishda ogohlantirish (user={user_id}, "
            f"channel={prize_channel_id}): {e}"
        )
        return False


async def send_prize_link(
    bot: Bot,
    user_id: int,
    contest,
    is_resubscribed: bool = False,
    ref_count: int | None = None,
    db: AsyncSession | None = None,
) -> bool:
    """
    1 martalik invite link yaratib yuborish.
    Returns True — muvaffaqiyatli, False — xato.
    """
    if not contest or not contest.prize_channel_id:
        logger.warning(f"send_prize_link: contest yoki prize_channel_id yo'q (user={user_id})")
        return False

    # 0. Foydalanuvchi allaqachon sovg'a kanalida bo'lsa — unga havola berilmaydi!
    in_prize = await is_user_in_prize_channel(bot, contest.prize_channel_id, user_id)
    if in_prize:
        logger.info(
            f"User {user_id} allaqachon prize kanalda ({contest.prize_channel_id}). Sovg'a havolasi berilmadi."
        )
        if db:
            user_repo = UserRepository(db)
            await user_repo.update_prize_access(user_id, True)
        return False

    # Atomik tekshirish: sovg'a huquqini claim qilamiz (poygalarni oldini oladi)
    user_repo = UserRepository(db) if db else None
    if user_repo and not is_resubscribed:
        claimed = await user_repo.claim_prize_access(user_id)
        if not claimed:
            logger.info(f"User {user_id} uchun sovg'a havolasi allaqachon claim qilingan.")
            return False

    # Avval foydalanuvchini unban qilamiz (agar ilgari ban qilingan bo'lsa)
    try:
        await bot.unban_chat_member(
            chat_id=contest.prize_channel_id,
            user_id=user_id,
            only_if_banned=True,
        )
    except Exception:
        pass

    invite_url = None
    try:
        invite = await bot.create_chat_invite_link(
            chat_id=contest.prize_channel_id,
            member_limit=1,              # Qat'iy faqat 1 kishi kiradi
            creates_join_request=False,  # To'g'ridan kiradi
            name=f"User {user_id}",
        )
        invite_url = invite.invite_link
    except Exception as e:
        logger.error(
            f"create_chat_invite_link XATO (user={user_id}, "
            f"channel={contest.prize_channel_id}): {e}"
        )

    channel_title = contest.prize_channel_title or "Sovrin kanal"

    if not invite_url:
        logger.error(f"Sovg'a havolasi yaratilmadi (user={user_id}, channel={contest.prize_channel_id})")
        if user_repo and not is_resubscribed:
            await user_repo.update_prize_access(user_id, False)

        from app.core.config import settings
        for adm_id in settings.ADMIN_IDS:
            try:
                await bot.send_message(
                    adm_id,
                    f"⚠️ <b>Diqqat!</b> Bot sovg'a kanaliga ({contest.prize_channel_id}) "
                    f"1 martalik havola yarata olmadi!\nBot kanalda admin ekanligini va "
                    f"«Invite Users via Link» huquqi borligini tekshiring.",
                )
            except Exception:
                pass
        return False

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"👑 {channel_title} — Kirish 🚀",
            url=invite_url,
        )
    ]])

    target = contest.required_referrals if contest else 1
    if ref_count is None and db:
        user_repo = UserRepository(db)
        user = await user_repo.get_by_telegram_id(user_id)
        ref_count = user.referral_count if user else 0
    elif ref_count is None:
        ref_count = target

    from app.bot.handlers.user.utils import progress_bar
    bar = progress_bar(ref_count, target)

    stats_block = (
        f"\n\n📊 <b>Sizning natijangiz</b>\n\n"
        f"✅ Tasdiqlangan: <b>{ref_count} ta</b>\n\n"
        f"{bar}"
    )

    if is_resubscribed:
        prize_text = (
            "✅ <b>Obuna tasdiqlandi!</b>\n\n"
            f"<b>{channel_title}</b> kanaliga 1 martalik havolangiz:\n\n"
            "⚠️ <i>Diqqat: Bu havola faqat 1 marta ishlaydi! Uni boshqaga bermang.</i>"
            f"{stats_block}"
        )
    else:
        prize_text = (
            "🎉 <b>Tabriklaymiz! Siz barcha shartlarni bajardingiz!</b>\n\n"
            f"<b>{channel_title}</b> kanaliga 1 martalik havolangiz:\n\n"
            "⚠️ <i>Diqqat: Bu havola faqat 1 marta ishlaydi! Uni boshqaga bermang.</i>"
            f"{stats_block}"
        )

    try:
        await bot.send_message(
            chat_id=user_id,
            text=prize_text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
        logger.info(f"✅ Prize xabari yuborildi: user={user_id}, contest={contest.id}")

        if db:
            try:
                from app.database.models import ContestWinner
                winner = ContestWinner(contest_id=contest.id, user_id=user_id)
                db.add(winner)
                await db.commit()
            except Exception:
                pass

        return True
    except Exception as e:
        logger.error(f"send_message XATO (user={user_id}): {e}")
        if user_repo and not is_resubscribed:
            await user_repo.update_prize_access(user_id, False)
        return False


async def check_and_send_prize(
    bot: Bot,
    referrer_telegram_id: int,
    db: AsyncSession,
    is_resubscribed: bool = False,
    force: bool = False,
) -> bool:
    """
    Referrer shartni bajargan bo'lsa prize yuborish.
    Shartlar:
    1. Aktiv konkurs va prize_channel_id mavjud
    2. referral_count >= contest.required_referrals
    3. Referrer barcha majburiy kanallarga a'zo bo'lishi shart
    4. Agar allaqachon link olgan bo'lsa va chiqib ketmagan bo'lsa (has_prize_access=True) va force=False bo'lsa,
       takroran yuborilmaydi.
    """
    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()
    if not contest or not contest.prize_channel_id:
        return False

    user_repo = UserRepository(db)
    referrer = await user_repo.get_by_telegram_id(referrer_telegram_id)
    if not referrer:
        return False

    # Referral soni yetarlimi?
    if referrer.referral_count < contest.required_referrals:
        return False

    # Majburiy kanallarga obunani tekshiramiz
    from app.services.subscription_service import SubscriptionService
    sub_service = SubscriptionService(db)
    is_subscribed = await sub_service.check_full_subscription(bot, referrer_telegram_id)

    if not is_subscribed:
        # Obuna bo'lmasa — prize kanaldan ham chiqaramiz
        if referrer.has_prize_access:
            await kick_user_from_prize_channel(bot, contest.prize_channel_id, referrer_telegram_id)
            await user_repo.update_prize_access(referrer_telegram_id, False)
        return False

    # Foydalanuvchi allaqachon sovg'a kanalida bo'lsa — unga havola berilmaydi!
    in_prize = await is_user_in_prize_channel(bot, contest.prize_channel_id, referrer_telegram_id)
    if in_prize:
        logger.info(
            f"User {referrer_telegram_id} allaqachon prize kanalda ({contest.prize_channel_id}). Sovg'a havolasi berilmadi."
        )
        await user_repo.update_prize_access(referrer_telegram_id, True)
        return False

    # Agar allaqachon prize berilgan bo'lsa va force=False bo'lsa
    if referrer.has_prize_access and not force and not is_resubscribed:
        return False

    # 1 martalik link yuborish
    sent = await send_prize_link(
        bot=bot,
        user_id=referrer_telegram_id,
        contest=contest,
        is_resubscribed=is_resubscribed,
        db=db,
    )
    if sent:
        await user_repo.update_prize_access(referrer_telegram_id, True)
    return sent
