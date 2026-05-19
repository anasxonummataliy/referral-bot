"""Integration tests"""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import User, Referral, Channel
from app.repositories.user_repo import UserRepository
from app.repositories.referral_repo import ReferralRepository
from app.repositories.channel_repo import ChannelRepository


@pytest.mark.asyncio
class TestUserReferralFlow:
    """Test complete user referral flow"""

    async def test_user_registration_and_referral(self, db_session: AsyncSession):
        """Test user registration with referral"""
        user_repo = UserRepository(db_session)
        referral_repo = ReferralRepository(db_session)
        
        # Create referrer
        referrer = await user_repo.create(
            telegram_id=111111111,
            full_name="Referrer User",
            is_subscribed=True,
        )
        
        # Create new user through referral
        new_user = await user_repo.create(
            telegram_id=222222222,
            full_name="New User",
            referrer_id=referrer.id,
        )
        
        # Create referral record
        referral = await referral_repo.create(
            referrer_id=referrer.id,
            referred_user_id=new_user.id,
        )
        
        # Update referrer count
        await user_repo.update(referrer.id, referral_count=1)
        
        # Verify flow
        assert referral.referrer_id == referrer.id
        assert referral.referred_user_id == new_user.id
        
        updated_referrer = await user_repo.get(referrer.id)
        assert updated_referrer.referral_count == 1

    async def test_multiple_referrals(self, db_session: AsyncSession):
        """Test handling multiple referrals"""
        user_repo = UserRepository(db_session)
        
        referrer = await user_repo.create(
            telegram_id=111111111,
            full_name="Referrer",
        )
        
        # Create multiple referrals
        for i in range(5):
            referred = await user_repo.create(
                telegram_id=222222220 + i,
                full_name=f"Referred User {i}",
                referrer_id=referrer.id,
            )
        
        # Update referrer count
        await user_repo.update(referrer.id, referral_count=5)
        
        updated_referrer = await user_repo.get(referrer.id)
        assert updated_referrer.referral_count == 5


@pytest.mark.asyncio
class TestChannelManagement:
    """Test channel management"""

    async def test_channel_creation(self, db_session: AsyncSession):
        """Test creating a channel"""
        channel_repo = ChannelRepository(db_session)
        
        channel = await channel_repo.create(
            telegram_channel_id=-1001234567890,
            title="Test Channel",
        )
        
        assert channel.id is not None
        assert channel.telegram_channel_id == -1001234567890
        assert channel.title == "Test Channel"

    async def test_channel_retrieval(self, db_session: AsyncSession):
        """Test retrieving channel"""
        channel_repo = ChannelRepository(db_session)
        
        created = await channel_repo.create(
            telegram_channel_id=-1001234567890,
            title="Test Channel",
        )
        
        retrieved = await channel_repo.get(created.id)
        assert retrieved is not None
        assert retrieved.telegram_channel_id == -1001234567890
