"""
Chat member updates handler.
Majburiy kanallardagi a'zolik o'zgarishlarini real-time kuzatadi:
1. User majburiy kanallardan biridan chiqib ketsa -> yopiq kanaldan chiqariladi
2. User barcha majburiy kanallarga qayta a'zo bo'lsa -> yopiq kanalga yangi 1 martalik link beriladi
"""
import html
import logging

from aiogram import Router, Bot
from aiogram.types import ChatMemberUpdated, InlineKeyboardMarkup, InlineKeyboardButton
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.channel_repo import ChannelRepository
from app.repositories.contest_repo import ContestRepository
from app.repositories.user_repo import UserRepository
from app.services.subscription_service import SubscriptionService
from app.bot.handlers.user.prize import kick_user_from_prize_channel, send_prize_link

logger = logging.getLogger(__name__)

router = Router(name="chat_member_updates")


@router.chat_member()
async def on_chat_member_updated(
    event: ChatMemberUpdated,
    bot: Bot,
    db: AsyncSession,
) -> None:
    user = event.new_chat_member.user
    if user.is_bot:
        return

    chat_id = event.chat.id
    channel_repo = ChannelRepository(db)
    channel = await channel_repo.get_by_channel_id(chat_id)

    # Agar bu kanal bizning majburiy kanalimiz bo'lmasa — e'tiborsiz qoldiramiz
    if not channel or not channel.is_active or not channel.is_required:
        return

    contest_repo = ContestRepository(db)
    contest = await contest_repo.get_active_contest()

    # Agar bu kanal prize kanalning o'zi bo'lsa — e'tiborsiz qoldiramiz
    if contest and contest.prize_channel_id == chat_id:
        return

    user_repo = UserRepository(db)
    db_user = await user_repo.get_by_telegram_id(user.id)

    # Agar bu foydalanuvchi botda mavjud bo'lmasa — bot foydalanuvchisi emas (oddiy kanal obunachisi)
    # Ularga xabar yuborib ham bo'lmaydi, yopiq kanal bilan ham aloqasi yo'q.
    if not db_user:
        return

    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    logger.info(
        f"ChatMemberUpdated: user={user.id} in chat={chat_id} "
        f"({old_status} -> {new_status})"
    )

    # ── 1. FOYDALANUVCHI KANALDAN CHIQIB KETGANDA ────────────────────────────
    if new_status in ["left", "kicked"]:
        await user_repo.update_subscription_status(user.id, False)

        # Agar bu foydalanuvchi orqali referrer bonus olgan bo'lsa,
        # kanalni tark etganda referrerning balli kamaytiriladi (revoking bonus):
        from app.repositories.referral_repo import ReferralRepository
        referral_repo = ReferralRepository(db)
        ref = await referral_repo.get_by_referred_id(db_user.id)
        if ref and ref.bonus_given:
            revoked = await referral_repo.revoke_bonus(ref.id)
            if revoked:
                referrer = await user_repo.get(ref.referrer_id)
                if referrer and referrer.referral_count > 0:
                    await user_repo.decrement_referral_count(referrer.telegram_id)
                    logger.info(
                        f"📉 Referral balli bekor qilindi (-1): referred={db_user.telegram_id} "
                        f"kanaldan chiqdi → referrer={referrer.telegram_id}"
                    )

        was_in_prize = False
        if contest and contest.prize_channel_id:
            # Faqat userda prize huquqi bo'lsa yoki yetarli referali bo'lsa yopiq kanaldan chiqariladi
            if db_user.has_prize_access or db_user.referral_count >= contest.required_referrals:
                await kick_user_from_prize_channel(bot, contest.prize_channel_id, user.id)
                await user_repo.update_prize_access(user.id, False)
                was_in_prize = True

        # Foydalanuvchiga bot orqali ogohlantirish yuboramiz
        try:
            raw_title = channel.title or "majburiy kanal"
            safe_title = html.escape(raw_title)
            channel_link = channel.invite_link or (
                f"https://t.me/{channel.username.lstrip('@')}" if channel.username else None
            )
            buttons = []
            if channel_link:
                buttons.append([InlineKeyboardButton(text=f"📢 {raw_title} ↗️", url=channel_link)])
            buttons.append([InlineKeyboardButton(text="✅ Qayta a'zo bo'ldim", callback_data="check_subscription")])
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

            if was_in_prize:
                msg_text = (
                    f"⚠️ <b>Diqqat!</b>\n\n"
                    f"Siz <b>{safe_title}</b> kanalidan chiqib ketganingiz sababli "
                    f"<b>yopiq kanaldan chiqarildingiz!</b>\n\n"
                    f"Qayta kirish uchun kanalga qayta a'zo bo'ling va <b>«✅ Qayta a'zo bo'ldim»</b> tugmasini bosing:"
                )
            else:
                msg_text = (
                    f"⚠️ <b>Diqqat!</b>\n\n"
                    f"Siz majburiy kanal (<b>{safe_title}</b>)dan chiqib ketdingiz.\n\n"
                    f"Botdan foydalanish uchun kanalga qayta a'zo bo'ling va <b>«✅ Qayta a'zo bo'ldim»</b> tugmasini bosing:"
                )

            await bot.send_message(
                chat_id=user.id,
                text=msg_text,
                reply_markup=keyboard,
            )
        except Exception as e:
            logger.warning(f"Chiqarilgan userga ({user.id}) xabar yuborishda xato: {e}")

    # ── 2. FOYDALANUVCHI KANALGA QO'SHILGANDA / QAYTGANDA ────────────────────
    elif new_status in ["member", "administrator", "creator"]:
        sub_service = SubscriptionService(db)
        is_all_sub = await sub_service.check_full_subscription(bot, user.id)

        if is_all_sub:
            if db_user:
                await user_repo.update_subscription_status(user.id, True)

            # Yangi referral bo'lsa uni tasdiqlaymiz (+1 hisoblanadi)
            from app.services.referral_service import ReferralService
            ref_service = ReferralService(db)
            await ref_service.confirm_referral(user.id, bot)

            prize_sent = False
            if contest and contest.prize_channel_id:
                fresh_user = await user_repo.get_by_telegram_id(user.id)
                if fresh_user and fresh_user.referral_count >= contest.required_referrals:
                    from app.bot.handlers.user.prize import is_user_in_prize_channel
                    in_prize = await is_user_in_prize_channel(bot, contest.prize_channel_id, user.id)
                    if in_prize:
                        await user_repo.update_prize_access(user.id, True)
                    elif not fresh_user.has_prize_access:
                        sent = await send_prize_link(
                            bot=bot,
                            user_id=user.id,
                            contest=contest,
                            is_resubscribed=True,
                            ref_count=fresh_user.referral_count,
                            db=db,
                        )
                        if sent:
                            await user_repo.update_prize_access(user.id, True)
                            prize_sent = True

            # Agar prize link yuborilmagan bo'lsa — foydalanuvchiga avtomatik asosiy menyuni chiqaramiz
            if not prize_sent and contest:
                try:
                    fresh_user = await user_repo.get_by_telegram_id(user.id)
                    ref_count = fresh_user.referral_count if fresh_user else 0
                    target = contest.required_referrals if contest else 5
                    from app.bot.handlers.user.utils import progress_bar
                    from app.core.config import settings
                    from app.bot.handlers.user.share import build_share_url
                    from app.bot.handlers.user.keyboards import main_menu_keyboard

                    bar = progress_bar(ref_count, target)
                    bot_info = await bot.get_me()
                    bot_username = settings.BOT_USERNAME or bot_info.username

                    referral_link = await ref_service.get_user_referral_link(
                        telegram_id=user.id, bot_username=bot_username
                    )
                    share_url = build_share_url(referral_link, contest)
                    keyboard = main_menu_keyboard(share_url=share_url)

                    text = (
                        "✅ <b>Obuna avtomatik tasdiqlandi!</b>\n\n"
                        f"🎯 <b>Konkurs sharti:</b> {target} ta do'st taklif qilish\n\n"
                        f"📊 <b>Natijangiz:</b> {ref_count} / {target} ta do'st\n"
                        f"{bar}\n\n"
                        f"🔗 <b>Taklif havolangiz:</b>\n"
                        f"<code>{referral_link}</code>"
                    )
                    await bot.send_message(
                        chat_id=user.id,
                        text=text,
                        reply_markup=keyboard,
                        disable_web_page_preview=True,
                    )
                except Exception as e:
                    logger.warning(f"Kanalga qaytgan userga ({user.id}) avtomatik menyu yuborishda xato: {e}")
