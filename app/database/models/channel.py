from sqlalchemy import BigInteger, String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column
from ..base import Base


class Channel(Base):
    __tablename__ = "channels"

    channel_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    username: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # @username
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)  # Majburiy yoki yo'q
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)  # Majburiy obuna

    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self):
        return f"<Channel {self.title} | Required: {self.is_required}>"
