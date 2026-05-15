# models/secret_channel.py
from sqlalchemy import String, Boolean, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base


class SecretChannel(Base):
    __tablename__ = "secret_channels"

    channel_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    min_referrals: Mapped[int] = mapped_column(
        Integer, default=10
    )  # qancha referral bilan ochiladi
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self):
        return f"<SecretChannel {self.title} | Min: {self.min_referrals}>"
