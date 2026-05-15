# bot/handlers/admin/channels.py
from aiogram import F
from aiogram.types import Message
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession
import re

from .base import admin_router, is_admin
from repositories.channel_repo import ChannelRepository


router = admin_router


@router.message(Command("addchannel"))
async def cmd_addchannel(message: Message):
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "➕ <b>Yangi kanal qo'shish</b>\n\n"
        "Quyidagilardan birini yuboring:\n"
        "• @username\n"
        "• https://t.me/kinobaza_uz\n"
        "• https://t.me/+AAAA12345678 (yashirin link)\n"
        "• -1001234567890 (ID)"
    )


@router.message(F.text)
async def process_add_channel(message: Message, db: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    text = message.text.strip()

    channel_id = None
    username = None

    try:
        # 1. Oddiy @username
        if text.startswith("@"):
            username = text

        # 2. t.me/ link (oddiy yoki yashirin)
        elif "t.me/" in text:
            match = re.search(r"t\.me/(?:\+|c/)?([a-zA-Z0-9_]+)", text)
            if match:
                value = match.group(1)
                if value.startswith("+") or len(value) > 20:  # yashirin link
                    # Yashirin link uchun to'g'ridan-to'g'ri get_chat ishlatish mumkin emas
                    await message.answer(
                        "❌ Yashirin link (t.me/+) orqali qo'shish hozircha qo'llab-quvvatlanmaydi.\n\n"
                        "Iltimos, kanal ID sini yuboring yoki botni kanalga admin qilib, @username bilan sinab ko'ring."
                    )
                    return
                else:
                    username = f"@{value}"

        # 3. To'g'ridan-to'g'ri kanal ID (-100...)
        elif text.startswith("-100") and text[1:].isdigit():
            channel_id = int(text)

        # 4. Faqat raqamlar (ID)
        elif text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
            channel_id = int(text)

        else:
            await message.answer(
                "❌ Noto'g'ri format. Yuqoridagi misollardan birini yuboring."
            )
            return

        # ==================== Kanal ma'lumotlarini olish ====================
        bot = message.bot
        chat = None

        if username:
            chat = await bot.get_chat(username)
        elif channel_id:
            chat = await bot.get_chat(channel_id)

        if not chat or chat.type not in ["channel", "supergroup"]:
            await message.answer("❌ Bu kanal emas yoki bot kanalga admin emas.")
            return

        channel_repo = ChannelRepository(db)

        # Allaqqachon mavjudligini tekshirish
        existing = await channel_repo.get_by_channel_id(chat.id)
        if existing:
            await message.answer("⚠️ Bu kanal allaqachon bazada mavjud.")
            return

        # Kanalni saqlash
        channel = await channel_repo.create(
            channel_id=chat.id,
            username=chat.username,
            title=chat.title or "Nomsiz Kanal",
            is_active=True,
            is_required=True,
            description=getattr(chat, "description", None),
        )

        await message.answer(
            f"✅ <b>Kanal muvaffaqiyatli qo'shildi!</b>\n\n"
            f"📛 Nomi: <b>{channel.title}</b>\n"
            f"🔗 Username: @{channel.username or 'yo‘q (yashirin)'}\n"
            f"🆔 ID: <code>{channel.channel_id}</code>"
        )

    except Exception as e:
        await message.answer(
            f"❌ Xatolik yuz berdi:\n<code>{str(e)}</code>\n\n"
            f"Botni kanalga administrator qilganingizga ishonch hosil qiling!"
        )


# ==================== REMOVE CHANNEL ====================


@router.message(Command("removechannel"))
async def cmd_removechannel(message: Message):
    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "🗑 <b>Kanalni o'chirish</b>\n\n"
        "Kanalning <b>@username</b> sini, <b>ID</b> sini yoki <b>linkini</b> yuboring.\n\n"
        "Misollar:\n"
        "• @kinobaza_uz\n"
        "• -1001234567890\n"
        "• https://t.me/kinobaza_uz"
    )


@router.message(F.text)
async def process_remove_channel(message: Message, db: AsyncSession):
    if not is_admin(message.from_user.id):
        return

    text = message.text.strip()
    channel_repo = ChannelRepository(db)

    try:
        chat = None
        channel_id = None

        # 1. @username yoki oddiy link
        if text.startswith("@") or "t.me/" in text:
            # Linkdan username ni tozalash
            if "t.me/" in text:
                username_part = text.split("t.me/")[-1].split("/")[0].split("?")[0]
                text = (
                    f"@{username_part}" if not username_part.startswith("+") else text
                )

            chat = await message.bot.get_chat(text)
            channel_id = chat.id

        # 2. To'g'ridan-to'g'ri ID
        elif text.startswith("-100") or (text.startswith("-") and text[1:].isdigit()):
            channel_id = int(text)

        else:
            await message.answer(
                "❌ Noto'g'ri format. @username, ID yoki link yuboring."
            )
            return

        # Bazadan kanalni topish
        channel = await channel_repo.get_by_channel_id(channel_id)

        if not channel:
            await message.answer("❌ Bu kanal bazada topilmadi.")
            return

        # O'chirish
        success = await channel_repo.delete(channel.id)

        if success:
            await message.answer(
                f"🗑 <b>Kanal muvaffaqiyatli o'chirildi!</b>\n\n"
                f"📛 Nomi: <b>{channel.title}</b>\n"
                f"🆔 ID: <code>{channel.channel_id}</code>\n"
                f"🔗 Username: @{channel.username or 'yo‘q'}"
            )
        else:
            await message.answer("❌ Kanalni o'chirishda xatolik yuz berdi.")

    except Exception as e:
        await message.answer(
            f"❌ Xatolik yuz berdi:\n<code>{str(e)}</code>\n\n"
            f"Botni kanalga admin qilganingizga va ma'lumotni to'g'ri yuborganingizga ishonch hosil qiling."
        )
