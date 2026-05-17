from sqlalchemy import BigInteger, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base


class Admin(Base):
    """
    Qo'shimcha adminlar. Asosiy admin .env dan olinadi,
    keyinchalik boshqa adminlar shu jadvalga qo'shiladi.
    """
    __tablename__ = "admins"

    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    def __repr__(self):
        return f"<Admin {self.telegram_id} | {self.username}>"
