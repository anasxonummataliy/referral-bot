from aiogram.types import Message
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.admin.base import admin_router, is_admin_async
from app.repositories.user_repo import UserRepository

router = admin_router


@router.message(Command("topref"))
async def cmd_top_referrers(message: Message, db: AsyncSession):
    if not await is_admin_async(message.from_user.id, db):
        return

    user_repo = UserRepository(db)
    top_users = await user_repo.get_top_referrers(limit=10)

    if not top_users:
        await message.answer("📊 Hali hech kim referral qilmagan.")
        return

    text = "🏆 <b>Top referralchilar</b>\n\n"
    medals = ["🥇", "🥈", "🥉"] + ["4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

    for i, user in enumerate(top_users):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        username = f"@{user.username}" if user.username else user.full_name
        text += f"{medal} {username} — <b>{user.referral_count}</b> referral\n"

    await message.answer(text)
