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
        # DB da obuna holatini yangilaymiz
        await user_repo.update_subscription_status(user.id, False)

        # Agar aktiv konkurs va prize kanal bo'lsa
        if contest and contest.prize_channel_id:
            # Agar userda prize huquqi bo'lgan bo'lsa yoki yetarli referral to'plagan bo'lsa
            if db_user.has_prize_access or db_user.referral_count >= contest.required_referrals:
                # Yopiq kanaldan chiqarib yuboramiz
                await kick_user_from_prize_channel(bot, contest.prize_channel_id, user.id)
                await user_repo.update_prize_access(user.id, False)

                # Foydalanuvchiga bot orqali ogohlantirish yuboramiz
                try:
                    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(
                            text="⚡️ Qayta a'zo bo'ldim — Tekshirish ✅",
                            callback_data="check_subscription",
                        )
                    ]])
                    channel_title = channel.title or "majburiy kanal"
                    await bot.send_message(
                        chat_id=user.id,
                        text=(
                            "⚠️ <b>Diqqat! Obuna bekor qilindi</b> ❗️\n\n"
                            f"Siz majburiy obuna kanallaridan biridan (<b>{channel_title}</b>) "
                            "chiqib ketganingiz sababli <b>yopiq kanaldan chiqarildingiz!</b> 🔒\n\n"
                            "✨ Yopiq kanalga qayta 1 martalik link olish uchun barcha majburiy kanallarga qayta a'zo bo'ling "
                            "va quyidagi tugmani bosing:"
                        ),
                        reply_markup=keyboard,
                    )
                except Exception as e:
                    logger.warning(f"Chiqarilgan userga ({user.id}) xabar yuborishda xato: {e}")

    # ── 2. FOYDALANUVCHI KANALGA QO'SHILGANDA / QAYTGANDA ────────────────────
    elif new_status in ["member", "administrator", "creator"]:
        # Barcha majburiy kanallarga obuna bo'ldimi tekshiramiz
        sub_service = SubscriptionService(db)
        is_all_sub = await sub_service.check_full_subscription(bot, user.id)

        if is_all_sub and contest and contest.prize_channel_id:
            # Referral shartini bajarganmi?
            fresh_user = await user_repo.get_by_telegram_id(user.id)
            if fresh_user and fresh_user.referral_count >= contest.required_referrals:
                # Agar hozirda kirish huquqi faol bo'lmasa (chiqarilgan yoki hali olmagan bo'lsa)
                if not fresh_user.has_prize_access:
                    sent = await send_prize_link(
                        bot=bot,
                        user_id=user.id,
                        contest=contest,
                        is_resubscribed=True,
                    )
                    if sent:
                        await user_repo.update_prize_access(user.id, True)
