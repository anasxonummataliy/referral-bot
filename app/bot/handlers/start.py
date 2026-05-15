# bot/handlers/start.py
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.utils.deep_linking import decode_payload
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from services.subscription_service import SubscriptionService
from services.referral_service import ReferralService
from repositories.user_repo import UserRepository

router = Router()


@router.message(CommandStart(deep_link=True))
async def cmd_start(message: Message, db: AsyncSession):
    user_id = message.from_user.id

    # Deeplinkdan payload ni olish (aiogram kutubxonasi orqali)
    args = message.text.split()[1] if len(message.text.split()) > 1 else None
    referrer_id = None

    if args:
        try:
            # Aiogram decode qiladi
            payload = decode_payload(args)
            if payload.isdigit():
                referrer_id = int(payload)
        except:
            # Agar oddiy raqam bo'lsa ham qabul qilish
            if args.isdigit():
                referrer_id = int(args)

    user_repo = UserRepository(db)
    referral_service = ReferralService(db)
    subscription_service = SubscriptionService(db)

    # Foydalanuvchini yaratish / olish
    user, is_new = await user_repo.get_or_create(
        telegram_id=user_id,
        full_name=message.from_user.full_name,
        username=message.from_user.username,
        language_code=message.from_user.language_code,
    )

    # Referralni qayta ishlash
    if is_new and referrer_id and referrer_id != user_id:
        await referral_service.process_new_referral(
            new_user_telegram_id=user_id, referrer_telegram_id=referrer_id
        )

    # Majburiy obuna tekshirish
    is_subscribed = await subscription_service.check_full_subscription(
        bot=message.bot, telegram_id=user_id
    )

    if not is_subscribed:
        return

    # Deeplink orqali referral link yaratish
    referral_link = await referral_service.get_user_referral_link(
        telegram_id=user_id, bot_username=settings.BOT_USERNAME
    )

    text = f"""
👋 <b>Xush kelibsiz, {message.from_user.first_name}!</b>

🔗 <b>Sizning shaxsiy referral linkingiz:</b>

<code>{referral_link}</code>

Do'stlaringizni taklif qiling va ko'proq imkoniyatlarga ega bo'ling!
"""

    await message.answer(text, disable_web_page_preview=True)


# Oddiy /start
@router.message(F.text == "/start")
async def cmd_start_simple(message: Message, db: AsyncSession):
    await cmd_start(message, db)
