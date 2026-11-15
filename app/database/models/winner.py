from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, func, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class ContestWinner(Base):
    __tablename__ = "contest_winners"
    __table_args__ = (
        UniqueConstraint("contest_id", "user_id", name="uq_contest_winner"),
    )

    contest_id: Mapped[int] = mapped_column(
        ForeignKey("contests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    won_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
