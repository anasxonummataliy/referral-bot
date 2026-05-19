import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from app.database.base import Base
from app.database.models import User, Referral, Channel, SecretChannel, Contest, Admin

# Test database configuration
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def engine():
    """Create test database engine"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False},
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    """Create test database session"""
    async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session_maker() as session:
        yield session


@pytest.fixture
def mock_bot_token():
    """Mock Telegram bot token"""
    return "123456789:ABCdefGHIjklMNOpqrsTUVwxyz-1234567890"


@pytest.fixture
def mock_user_id():
    """Mock Telegram user ID"""
    return 123456789


@pytest.fixture
def mock_admin_id():
    """Mock admin user ID"""
    return 987654321


@pytest.fixture
def mock_channel_id():
    """Mock Telegram channel ID"""
    return -1001234567890


@pytest.fixture
def mock_message():
    """Mock Telegram message"""
    return {
        "message_id": 1,
        "date": 1234567890,
        "chat": {"id": 123456789, "type": "private"},
        "from": {
            "id": 123456789,
            "is_bot": False,
            "first_name": "Test",
            "username": "testuser",
        },
        "text": "Test message",
    }


@pytest.fixture
def mock_callback_query():
    """Mock Telegram callback query"""
    return {
        "id": "12345",
        "from": {
            "id": 123456789,
            "is_bot": False,
            "first_name": "Test",
        },
        "chat_instance": "1234567890",
        "data": "test_callback",
    }
