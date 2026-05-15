from sqlalchemy import BigInteger, String, Integer, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..base import Base


class User(Base):
    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    language_code: Mapped[str | None] = mapped_column(String(10), nullable=True)

    # Referral
    referrer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Statistikalar
    referral_count: Mapped[int] = mapped_column(
        Integer, default=0
    )  # Necha kishini taklif qilgan
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    referrer: Mapped["User | None"] = relationship(
        "User", remote_side=[telegram_id], back_populates="referrals", uselist=False
    )
    referrals: Mapped[list["User"]] = relationship(
        "User", back_populates="referrer", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<User {self.telegram_id} | Ref: {self.referral_count}>"
