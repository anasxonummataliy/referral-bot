from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base


class Referral(Base):
    __tablename__ = "referrals"

    referrer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    referred_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    bonus_given: Mapped[bool] = mapped_column(Boolean, default=False)

    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    referrer: Mapped["User"] = relationship(  # type: ignore
        "User", foreign_keys=[referrer_id]
    )
    referred: Mapped["User"] = relationship(  # type: ignore
        "User", foreign_keys=[referred_id]
    )
