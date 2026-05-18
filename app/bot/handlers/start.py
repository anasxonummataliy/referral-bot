"""
ESKIRGAN — bu fayl endi ishlatilmaydi.
Barcha logika app/bot/handlers/user/ papkasiga ko'chirildi:

  user/start.py        — /start, check_subscription, back_to_main
  user/share.py        — share_link, /referral
  user/stats.py        — my_referrals, my_gifts, /mystats
  user/info.py         — terms, help, /help
  user/prize.py        — prize link yaratish va yuborish
  user/referral_notify.py — yangi referral bildirishnomasi
  user/keyboards.py    — barcha inline keyboard
  user/utils.py        — umumiy yordamchi funksiyalar

Bu fayl faqat import compatibility uchun saqlanadi.
"""

# Eski importlar uchun (agar biror joyda ishlatilgan bo'lsa)
from app.bot.handlers.user.start import router, set_bot_commands, show_main_menu
from app.bot.handlers.user.utils import safe_answer, safe_send_message, progress_bar
