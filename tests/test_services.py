"""Unit tests for services"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import User
from app.services.referral_service import ReferralService


@pytest.mark.asyncio
class TestReferralService:
    """Test ReferralService"""

    async def test_get_user_referral_link(self, db_session: AsyncSession):
        """Test generating referral link"""
        service = ReferralService(db_session)

        link = await service.get_user_referral_link(
            telegram_id=123456789,
            bot_username="testbot",
        )

        assert link is not None
        assert "testbot" in link
        assert "123456789" in link
        assert "https://" in link

    async def test_process_new_referral_success(self, db_session: AsyncSession):
        """Test processing valid referral"""
        service = ReferralService(db_session)

        referrer = User(telegram_id=111111111, full_name="Referrer")
        new_user = User(telegram_id=222222222, full_name="New User")
        db_session.add_all([referrer, new_user])
        await db_session.commit()

        result = await service.process_new_referral(
            new_user_telegram_id=222222222,
            referrer_telegram_id=111111111,
            give_bonus=False,
        )

        assert result is True

        await db_session.refresh(new_user)
        assert new_user.referrer_id == referrer.id

        await db_session.refresh(referrer)
        # Hali obuna tasdiqlanmagani uchun referrer count 0 qoladi
        assert referrer.referral_count == 0

        # Kanallarga qo'shilgach confirm_referral chaqiriladi
        from unittest.mock import AsyncMock, MagicMock
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock()
        mock_bot.get_me = AsyncMock(return_value=MagicMock(username="test_bot"))

        confirmed = await service.confirm_referral(222222222, mock_bot)
        assert confirmed is True

        await db_session.refresh(referrer)
        assert referrer.referral_count == 1

    async def test_process_new_referral_duplicate(self, db_session: AsyncSession):
        """Test that duplicate referral is not processed"""
        service = ReferralService(db_session)

        referrer = User(telegram_id=111111111, full_name="Referrer")
        new_user = User(telegram_id=222222222, full_name="New User", referrer=referrer)
        db_session.add_all([referrer, new_user])
        await db_session.commit()

        result = await service.process_new_referral(
            new_user_telegram_id=222222222,
            referrer_telegram_id=111111111,
        )

        assert result is False

    async def test_process_new_referral_self_referral(self, db_session: AsyncSession):
        """Test that self-referral is prevented"""
        service = ReferralService(db_session)

        user = User(telegram_id=111111111, full_name="User")
        db_session.add(user)
        await db_session.commit()

        result = await service.process_new_referral(
            new_user_telegram_id=111111111,
            referrer_telegram_id=111111111,
        )

        assert result is False

    async def test_process_new_referral_missing_users(self, db_session: AsyncSession):
        """Test that referral fails if users don't exist"""
        service = ReferralService(db_session)

        result = await service.process_new_referral(
            new_user_telegram_id=999999999,
            referrer_telegram_id=888888888,
        )

        assert result is False


def test_build_share_text_format():
    """Verify that referral link is at top, separated by newlines, with 👆 and no trailing link"""
    from app.bot.handlers.user.share import _build_share_text
    from app.database.models import Contest

    contest = Contest(
        title="Writing 2026",
        welcome_message="Writing 2026",
        referral_message=None,
        required_referrals=1,
    )
    ref_link = "https://t.me/hasanboevs_bot?start=7381087311"

    text = _build_share_text(contest, ref_link)

    expected = (
        "https://t.me/hasanboevs_bot?start=7381087311\n\n"
        "Writing 2026\n"
        "👆 Qatnashish uchun quyidagi tugmani bosing."
    )
    assert text == expected
    assert text.startswith("https://t.me/hasanboevs_bot?start=7381087311\n\n")
    assert "Havola:" not in text
    assert "👇" not in text
