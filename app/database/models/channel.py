from sqlalchemy import BigInteger, String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class Channel(Base):
    __tablename__ = "channels"

    channel_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    invite_link: Mapped[str | None] = mapped_column(String(500), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self):
        return f"<Channel {self.title} | Required: {self.is_required}>"
