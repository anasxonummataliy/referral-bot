"""Configuration tests for environment and settings"""

from app.core.config import Settings


class TestSettings:
    """Test Settings configuration"""

    def test_settings_defaults(self):
        """Test default settings values"""
        settings = Settings(
            BOT_TOKEN="test_token",
            WEBHOOK_HOST="http://localhost:8011",
        )

        assert settings.BOT_TOKEN == "test_token"
        assert settings.WEBHOOK_PATH == "/webhook"
        assert settings.ENVIRONMENT == "development"

    def test_database_url_sqlite(self):
        """Test DATABASE_URL returns sqlite+aiosqlite URL"""
        settings = Settings(
            BOT_TOKEN="test_token",
            WEBHOOK_HOST="http://localhost:8011",
            DB_PATH="/tmp/test.db",
        )

        assert settings.DATABASE_URL == "sqlite+aiosqlite:////tmp/test.db"

    def test_database_url_default_path(self):
        """Test DATABASE_URL uses default path"""
        settings = Settings(
            BOT_TOKEN="test_token",
            WEBHOOK_HOST="http://localhost:8011",
        )

        assert "sqlite+aiosqlite://" in settings.DATABASE_URL
        assert "referral_bot.db" in settings.DATABASE_URL

    def test_is_admin_check(self):
        """Test admin permission check"""
        settings = Settings(
            BOT_TOKEN="test_token",
            ADMIN=[123456, 789012],
            WEBHOOK_HOST="http://localhost:8011",
        )

        assert settings.is_admin(123456) is True
        assert settings.is_admin(789012) is True
        assert settings.is_admin(111111) is False

    def test_admin_ids_property(self):
        """Test ADMIN_IDS property"""
        settings = Settings(
            BOT_TOKEN="test_token",
            ADMIN=[123456, 789012, 555555],
            WEBHOOK_HOST="http://localhost:8011",
        )

        assert len(settings.ADMIN_IDS) == 3
        assert 123456 in settings.ADMIN_IDS
        assert 789012 in settings.ADMIN_IDS
        assert 555555 in settings.ADMIN_IDS

    def test_webhook_path_custom(self):
        """Test custom webhook path"""
        settings = Settings(
            BOT_TOKEN="test_token",
            WEBHOOK_HOST="https://example.com",
            WEBHOOK_PATH="/bot/webhook",
        )

        assert settings.WEBHOOK_PATH == "/bot/webhook"
