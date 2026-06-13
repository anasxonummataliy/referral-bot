from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):

    BOT_TOKEN: str
    BOT_USERNAME: Optional[str] = None
    ADMIN: list[int] = []

    # SQLite
    DB_PATH: str = "/app/data/referral_bot.db"

    WEBHOOK_HOST: str
    WEBHOOK_PATH: str = "/webhook"

    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    def is_admin(self, user_id: int) -> bool:
        """Admin tekshiruvi"""
        return user_id in self.ADMIN

    @property
    def ADMIN_IDS(self) -> list[int]:
        return self.ADMIN

    @property
    def DATABASE_URL(self) -> str:
        return f"sqlite+aiosqlite:///{self.DB_PATH}"

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return f"sqlite:///{self.DB_PATH}"


settings = Settings()
