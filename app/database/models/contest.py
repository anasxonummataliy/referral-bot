from sqlalchemy import BigInteger, String, Boolean, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class Contest(Base):
    """
    Konkurs modeli. Bir vaqtda faqat bitta aktiv konkurs bo'ladi.
    """
    __tablename__ = "contests"

    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # Boshlanish xabari (majburiy kanallardan OLDIN chiqadi)
    welcome_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Nechtadan referral qilsa prize_channel linki beriladi
    required_referrals: Mapped[int] = mapped_column(Integer, default=5)

    # Prize kanal (yashirin, bot admin)
    prize_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    prize_channel_title: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Konkurs holati
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self):
        return f"<Contest '{self.title}' | Active: {self.is_active} | Req: {self.required_referrals}>"
