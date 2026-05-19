"""Unit tests for database models"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import User, Referral


@pytest.mark.asyncio
class TestUserModel:
    """Test User model"""

    async def test_user_creation(self, db_session: AsyncSession):
        """Test creating a user"""
        user = User(
            telegram_id=123456789,
            username="testuser",
            full_name="Test User",
            language_code="en",
        )
        db_session.add(user)
        await db_session.commit()

        retrieved = await db_session.get(User, user.id)
        assert retrieved is not None
        assert retrieved.telegram_id == 123456789
        assert retrieved.username == "testuser"

    async def test_user_defaults(self, db_session: AsyncSession):
        """Test user model default values"""
        user = User(
            telegram_id=987654321,
            full_name="Test User 2",
        )
        db_session.add(user)
        await db_session.commit()

        retrieved = await db_session.get(User, user.id)
        assert retrieved.referral_count == 0
        assert retrieved.is_subscribed is False
        assert retrieved.is_active is True
        assert retrieved.referrer_id is None

    async def test_user_repr(self, db_session: AsyncSession):
        """Test user __repr__ method"""
        user = User(
            telegram_id=123456789,
            full_name="Test User",
        )
        db_session.add(user)
        await db_session.commit()

        repr_str = repr(user)
        assert "123456789" in repr_str
        assert "Refs: 0" in repr_str


@pytest.mark.asyncio
class TestReferralModel:
    """Test Referral model"""

    async def test_referral_creation(self, db_session: AsyncSession):
        """Test creating a referral"""
        # Create users first
        referrer = User(
            telegram_id=111111111,
            full_name="Referrer",
        )
        referred = User(
            telegram_id=222222222,
            full_name="Referred User",
        )
        db_session.add_all([referrer, referred])
        await db_session.commit()

        # Create referral
        referral = Referral(
            referrer_id=referrer.id,
            referred_user_id=referred.id,
        )
        db_session.add(referral)
        await db_session.commit()

        retrieved = await db_session.get(Referral, referral.id)
        assert retrieved is not None
        assert retrieved.referrer_id == referrer.id
        assert retrieved.referred_user_id == referred.id


@pytest.mark.asyncio
class TestUserRelationships:
    """Test User model relationships"""

    async def test_user_referrer_relationship(self, db_session: AsyncSession):
        """Test referrer relationship"""
        referrer = User(
            telegram_id=111111111,
            full_name="Referrer",
        )
        referral_user = User(
            telegram_id=222222222,
            full_name="Referred User",
            referrer=referrer,
        )
        db_session.add_all([referrer, referral_user])
        await db_session.commit()

        # Refresh to load relationships
        await db_session.refresh(referral_user)
        assert referral_user.referrer_id == referrer.id
        assert referral_user.referrer.telegram_id == 111111111

    async def test_user_referrals_relationship(self, db_session: AsyncSession):
        """Test referrals (inverse) relationship"""
        referrer = User(
            telegram_id=111111111,
            full_name="Referrer",
        )
        referred1 = User(
            telegram_id=222222222,
            full_name="Referred User 1",
            referrer=referrer,
        )
        referred2 = User(
            telegram_id=333333333,
            full_name="Referred User 2",
            referrer=referrer,
        )
        db_session.add_all([referrer, referred1, referred2])
        await db_session.commit()

        await db_session.refresh(referrer)
        assert len(referrer.referrals) == 2
