"""Configuration tests for environment and settings"""
import pytest
from app.core.config import Settings


class TestSettings:
    """Test Settings configuration"""

    def test_settings_defaults(self):
        """Test default settings values"""
        settings = Settings(
            BOT_TOKEN="test_token",
            DB_NAME="test_db",
            DB_USER="test_user",
            WEBHOOK_HOST="http://localhost:8000",
        )
        
        assert settings.BOT_TOKEN == "test_token"
        assert settings.DB_PORT == 5435
        assert settings.REDIS_PORT == 6379
        assert settings.REDIS_DB == 0
        assert settings.WEBHOOK_PATH == "/webhook"
        assert settings.ENVIRONMENT == "development"

    def test_database_url_construction(self):
        """Test DATABASE_URL property"""
        settings = Settings(
            BOT_TOKEN="test_token",
            DB_HOST="localhost",
            DB_PORT=5432,
            DB_NAME="referral_bot",
            DB_USER="user",
            DB_PASSWORD="password",
            WEBHOOK_HOST="http://localhost:8000",
        )
        
        expected_url = "postgresql+asyncpg://user:password@localhost:5432/referral_bot"
        assert settings.DATABASE_URL == expected_url

    def test_redis_url_with_password(self):
        """Test REDIS_URL with password"""
        settings = Settings(
            BOT_TOKEN="test_token",
            DB_NAME="test_db",
            DB_USER="test_user",
            REDIS_HOST="localhost",
            REDIS_PORT=6379,
            REDIS_PASSWORD="redis_pass",
            WEBHOOK_HOST="http://localhost:8000",
        )
        
        expected = "redis://:redis_pass@localhost:6379/0"
        assert settings.REDIS_URL == expected

    def test_redis_url_without_password(self):
        """Test REDIS_URL without password"""
        settings = Settings(
            BOT_TOKEN="test_token",
            DB_NAME="test_db",
            DB_USER="test_user",
            REDIS_HOST="localhost",
            REDIS_PORT=6379,
            WEBHOOK_HOST="http://localhost:8000",
        )
        
        expected = "redis://localhost:6379/0"
        assert settings.REDIS_URL == expected

    def test_redis_url_none_when_no_host(self):
        """Test REDIS_URL is None when REDIS_HOST not set"""
        settings = Settings(
            BOT_TOKEN="test_token",
            DB_NAME="test_db",
            DB_USER="test_user",
            WEBHOOK_HOST="http://localhost:8000",
        )
        
        assert settings.REDIS_URL is None

    def test_is_admin_check(self):
        """Test admin permission check"""
        settings = Settings(
            BOT_TOKEN="test_token",
            DB_NAME="test_db",
            DB_USER="test_user",
            ADMIN=[123456, 789012],
            WEBHOOK_HOST="http://localhost:8000",
        )
        
        assert settings.is_admin(123456) is True
        assert settings.is_admin(789012) is True
        assert settings.is_admin(111111) is False

    def test_admin_ids_property(self):
        """Test ADMIN_IDS property"""
        settings = Settings(
            BOT_TOKEN="test_token",
            DB_NAME="test_db",
            DB_USER="test_user",
            ADMIN=[123456, 789012, 555555],
            WEBHOOK_HOST="http://localhost:8000",
        )
        
        assert len(settings.ADMIN_IDS) == 3
        assert 123456 in settings.ADMIN_IDS
        assert 789012 in settings.ADMIN_IDS
        assert 555555 in settings.ADMIN_IDS
