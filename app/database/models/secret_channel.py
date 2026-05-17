from sqlalchemy import BigInteger, String, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class SecretChannel(Base):
    __tablename__ = "secret_channels"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    link: Mapped[str] = mapped_column(String(500), nullable=False)  # To'liq havola

    min_referrals: Mapped[int] = mapped_column(Integer, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self):
        return f"<SecretChannel {self.title} | Min: {self.min_referrals}>"
