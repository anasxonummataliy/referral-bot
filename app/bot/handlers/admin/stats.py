from aiogram import F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.admin.base import admin_router, is_admin_async, admin_main_keyboard
from app.repositories.user_repo import UserRepository
from app.repositories.channel_repo import ChannelRepository
from app.repositories.secret_channel_repo import SecretChannelRepository
from app.repositories.contest_repo import ContestRepository

router = admin_router


@router.callback_query(F.data == "adm_stats")
async def adm_stats_callback(callback: CallbackQuery, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return

    user_repo = UserRepository(db)
    channel_repo = ChannelRepository(db)
    contest_repo = ContestRepository(db)

    total_users = await user_repo.count()
    active_channels = await channel_repo.get_required_channels()
    contest = await contest_repo.get_active_contest()

    contest_info = (
        f"🏆 Aktiv konkurs: <b>{contest.title}</b> ({contest.required_referrals} ref)"
        if contest else
        "🏆 Aktiv konkurs: <i>yo'q</i>"
    )

    text = (
        f"📊 <b>Bot Statistikasi</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users}</b>\n"
        f"📢 Majburiy kanallar: <b>{len(active_channels)}</b>\n"
        f"{contest_info}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_back")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.message(Command("stats", "statistics"))
async def cmd_stats(message: Message, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return

    user_repo = UserRepository(db)
    channel_repo = ChannelRepository(db)
    contest_repo = ContestRepository(db)

    total_users = await user_repo.count()
    active_channels = await channel_repo.get_required_channels()
    contest = await contest_repo.get_active_contest()

    contest_info = (
        f"🏆 Aktiv konkurs: <b>{contest.title}</b> ({contest.required_referrals} ref)"
        if contest else
        "🏆 Aktiv konkurs: <i>yo'q</i>"
    )

    text = (
        f"📊 <b>Bot Statistikasi</b>\n\n"
        f"👥 Jami foydalanuvchilar: <b>{total_users}</b>\n"
        f"📢 Majburiy kanallar: <b>{len(active_channels)}</b>\n"
        f"{contest_info}\n\n"
        f"<b>Admin buyruqlari:</b>\n"
        f"/admin — Admin panel\n"
        f"/contest — Konkurs boshqaruvi\n"
        f"/channels — Kanallar boshqaruvi\n"
        f"/addchannel — Kanal qo'shish\n"
        f"/giftchannel — Sovg'a kanallar\n"
        f"/broadcast — Xabar yuborish\n"
        f"/admins — Adminlar boshqaruvi\n"
        f"/topref — Top referralchilar\n"
        f"/cancel — Amalni bekor qilish"
    )
    await message.answer(text)


@router.callback_query(F.data == "adm_back")
async def adm_back(callback: CallbackQuery, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return
    text = "🛠 <b>Admin Panel</b>\n\nQuyidagi bo'limlardan birini tanlang:"
    await callback.message.edit_text(text, reply_markup=admin_main_keyboard())
    await callback.answer()


@router.callback_query(F.data == "adm_users")
async def adm_users_callback(callback: CallbackQuery, db: AsyncSession):
    if not await is_admin_async(callback.from_user.id, db):
        return

    user_repo = UserRepository(db)
    top_users = await user_repo.get_top_referrers(limit=10)

    text = "🏆 <b>Top referralchilar</b>\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    if not top_users:
        text += "Hali hech kim referral qilmagan."
    else:
        for i, user in enumerate(top_users):
            medal = medals[i] if i < len(medals) else f"{i+1}."
            username = f"@{user.username}" if user.username else user.full_name
            text += f"{medal} {username} — <b>{user.referral_count}</b> referral\n"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="adm_back")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()
