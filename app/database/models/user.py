from sqlalchemy import BigInteger, String, Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


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
    referral_count: Mapped[int] = mapped_column(Integer, default=0)

    # Majburiy obuna holati
    is_subscribed: Mapped[bool] = mapped_column(Boolean, default=False)

    # Qo'shimcha
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    referrer: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[referrer_id],
        back_populates="referrals",
        remote_side="User.id",
    )
    referrals: Mapped[list["User"]] = relationship(
        "User",
        foreign_keys="User.referrer_id",
        back_populates="referrer",
    )

    def __repr__(self):
        return f"<User {self.telegram_id} | Refs: {self.referral_count} | Sub: {self.is_subscribed}>"
