"""Unit tests for repositories"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import User, Admin
from app.repositories.user_repo import UserRepository
from app.repositories.admin_repo import AdminRepository


@pytest.mark.asyncio
class TestUserRepository:
    """Test UserRepository"""

    async def test_user_create(self, db_session: AsyncSession):
        """Test creating a user"""
        repo = UserRepository(db_session)
        
        user = await repo.create(
            telegram_id=123456789,
            username="testuser",
            full_name="Test User",
            language_code="en",
        )
        
        assert user.id is not None
        assert user.telegram_id == 123456789
        assert user.username == "testuser"

    async def test_user_get_by_telegram_id(self, db_session: AsyncSession):
        """Test getting user by telegram_id"""
        repo = UserRepository(db_session)
        
        created = await repo.create(
            telegram_id=123456789,
            full_name="Test User",
        )
        
        retrieved = await repo.get_by_telegram_id(123456789)
        assert retrieved is not None
        assert retrieved.id == created.id

    async def test_user_get_all(self, db_session: AsyncSession):
        """Test getting all users"""
        repo = UserRepository(db_session)
        
        await repo.create(telegram_id=111111111, full_name="User 1")
        await repo.create(telegram_id=222222222, full_name="User 2")
        await repo.create(telegram_id=333333333, full_name="User 3")
        
        users = await repo.get_all()
        assert len(users) == 3

    async def test_user_update(self, db_session: AsyncSession):
        """Test updating a user"""
        repo = UserRepository(db_session)
        
        user = await repo.create(
            telegram_id=123456789,
            full_name="Test User",
            is_subscribed=False,
        )
        
        updated = await repo.update(user.id, is_subscribed=True, referral_count=5)
        assert updated is not None
        assert updated.is_subscribed is True
        assert updated.referral_count == 5

    async def test_user_update_by_telegram_id(self, db_session: AsyncSession):
        """Test updating user by telegram_id"""
        repo = UserRepository(db_session)
        
        await repo.create(telegram_id=123456789, full_name="Test User")
        
        updated = await repo.update_by_telegram_id(
            123456789, 
            username="newusername"
        )
        assert updated is not None
        assert updated.username == "newusername"

    async def test_user_delete(self, db_session: AsyncSession):
        """Test deleting a user"""
        repo = UserRepository(db_session)
        
        user = await repo.create(telegram_id=123456789, full_name="Test User")
        
        result = await repo.delete(user.id)
        assert result is True
        
        deleted = await repo.get(user.id)
        assert deleted is None


@pytest.mark.asyncio
class TestAdminRepository:
    """Test AdminRepository"""

    async def test_admin_create(self, db_session: AsyncSession):
        """Test creating an admin"""
        repo = AdminRepository(db_session)
        
        admin = await repo.create(
            telegram_id=987654321,
            username="admin",
        )
        
        assert admin.id is not None
        assert admin.telegram_id == 987654321

    async def test_admin_get_by_telegram_id(self, db_session: AsyncSession):
        """Test getting admin by telegram_id"""
        repo = AdminRepository(db_session)
        
        created = await repo.create(telegram_id=987654321, username="admin")
        
        retrieved = await repo.get_by_telegram_id(987654321)
        assert retrieved is not None
        assert retrieved.id == created.id

    async def test_admin_get_all(self, db_session: AsyncSession):
        """Test getting all admins"""
        repo = AdminRepository(db_session)
        
        await repo.create(telegram_id=111111111, username="admin1")
        await repo.create(telegram_id=222222222, username="admin2")
        
        admins = await repo.get_all()
        assert len(admins) == 2
