"""
Chat member updates handler.
Majburiy kanallardagi a'zolik o'zgarishlarini real-time kuzatadi:
1. User majburiy kanallardan biridan chiqib ketsa -> yopiq kanaldan chiqariladi
2. User barcha majburiy kanallarga qayta a'zo bo'lsa -> yopiq kanalga yangi 1 martalik link beriladi
"""
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

    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    logger.info(
        f"ChatMemberUpdated: user={user.id} in chat={chat_id} "
        f"({old_status} -> {new_status})"
    )

    # ── 1. FOYDALANUVCHI KANALDAN CHIQIB KETGANDA ────────────────────────────
    if new_status in ["left", "kicked"]:
        if db_user:
            await user_repo.update_subscription_status(user.id, False)

        was_in_prize = False
        if contest and contest.prize_channel_id:
            # Agar userda prize huquqi bo'lsa yoki yetarli referali bo'lsa
            if db_user and (db_user.has_prize_access or db_user.referral_count >= contest.required_referrals):
                await kick_user_from_prize_channel(bot, contest.prize_channel_id, user.id)
                await user_repo.update_prize_access(user.id, False)
                was_in_prize = True
            else:
                try:
                    await kick_user_from_prize_channel(bot, contest.prize_channel_id, user.id)
                except Exception:
                    pass

        # Foydalanuvchiga bot orqali ogohlantirish yuboramiz
        try:
            channel_title = channel.title or "majburiy kanal"
            channel_link = channel.invite_link or (
                f"https://t.me/{channel.username.lstrip('@')}" if channel.username else None
            )
            buttons = []
            if channel_link:
                buttons.append([InlineKeyboardButton(text=f"📢 {channel_title}", url=channel_link)])
            buttons.append([
                InlineKeyboardButton(
                    text="✅ Qayta a'zo bo'ldim — Tekshirish",
                    callback_data="check_subscription",
                )
            ])
            keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

            if was_in_prize:
                msg_text = (
                    f"⚠️ <b>Diqqat!</b>\n\n"
                    f"Siz <b>{channel_title}</b> kanalidan chiqib ketganingiz sababli "
                    f"<b>yopiq kanaldan chiqarildingiz!</b>\n\n"
                    f"Qayta kirish uchun barcha kanallarga a'zo bo'ling va tekshirish tugmasini bosing:"
                )
            else:
                msg_text = (
                    f"⚠️ <b>Diqqat!</b>\n\n"
                    f"Siz majburiy kanal (<b>{channel_title}</b>)dan chiqib ketdingiz.\n\n"
                    f"Botdan foydalanish uchun kanalga qayta a'zo bo'ling:"
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

            if contest and contest.prize_channel_id:
                fresh_user = await user_repo.get_by_telegram_id(user.id)
                if fresh_user and fresh_user.referral_count >= contest.required_referrals:
                    if not fresh_user.has_prize_access:
                        sent = await send_prize_link(
                            bot=bot,
                            user_id=user.id,
                            contest=contest,
                            is_resubscribed=True,
                        )
                        if sent:
                            await user_repo.update_prize_access(user.id, True)
