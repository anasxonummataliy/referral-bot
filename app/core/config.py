import os
import json
from typing import Optional, Any
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    BOT_TOKEN: str
    BOT_USERNAME: Optional[str] = None
    ADMIN: list[int] = []

    # SQLite
    DB_PATH: str = "/app/data/referral_bot.db" if os.path.exists("/app") or os.path.exists("/.dockerenv") else "data/referral_bot.db"

    WEBHOOK_HOST: Optional[str] = None
    WEBHOOK_PATH: str = "/webhook"

    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator("ADMIN", mode="before")
    @classmethod
    def parse_admin(cls, v: Any) -> list[int]:
        if isinstance(v, int):
            return [v]
        if isinstance(v, (list, tuple)):
            return [int(x) for x in v]
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            if v.startswith("[") and v.endswith("]"):
                try:
                    parsed = json.loads(v)
                    return [int(x) for x in parsed]
                except Exception:
                    pass
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return []

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
