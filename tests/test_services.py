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


def test_build_share_url_native_tg_scheme():
    """Verify that build_share_url uses tg://msg_url instead of https://t.me/share/url"""
    import urllib.parse
    from app.bot.handlers.user.share import build_share_url, _build_user_keyboard
    from app.database.models import Contest

    contest = Contest(
        title="Writing 2026",
        welcome_message="Writing 2026",
        referral_message=None,
        required_referrals=1,
    )
    ref_link = "https://t.me/hasanboevs_bot?start=7381087311"

    url = build_share_url(ref_link, contest)

    # Must use tg://msg_url so mobile devices don't open Safari/Chrome
    assert url.startswith("tg://msg_url?")
    assert "https://t.me/share/url" not in url

    # Must contain encoded parameters
    parsed = urllib.parse.urlparse(url)
    params = urllib.parse.parse_qs(parsed.query)
    assert params["url"][0] == ref_link
    assert params["text"][0].startswith("\n")
    assert "Writing 2026" in params["text"][0]
    assert "👆 Qatnashish uchun quyidagi tugmani bosing." in params["text"][0]

    # Spaces must be encoded as %20, not +
    assert "+" not in url
    assert "%20" in url

    # Keyboard button must carry this url
    kb = _build_user_keyboard(ref_link, contest)
    share_btn = kb.inline_keyboard[0][0]
    assert share_btn.url == url
    assert share_btn.url.startswith("tg://msg_url?")


@pytest.mark.asyncio
async def test_notify_referrer_rich_user_details(db_session: AsyncSession):
    """Verify that notify_referrer sends full user details: name, username, ID, and profile link"""
    from unittest.mock import AsyncMock, MagicMock
    from app.bot.handlers.user.referral_notify import notify_referrer
    from app.database.models import User, Contest

    referrer = User(telegram_id=111111111, full_name="Referrer", referral_count=2)
    new_user = User(telegram_id=987654321, full_name="John Doe", username="johndoe")
    contest = Contest(title="Test Contest", required_referrals=5)
    db_session.add_all([referrer, new_user, contest])
    await db_session.commit()

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    mock_bot.get_me = AsyncMock(return_value=MagicMock(username="test_bot"))

    await notify_referrer(
        bot=mock_bot,
        referrer_telegram_id=111111111,
        new_user_name=new_user.full_name,
        db=db_session,
        new_user=new_user,
    )

    assert mock_bot.send_message.called
    sent_text = mock_bot.send_message.call_args.kwargs["text"]
    assert "John Doe" in sent_text
    assert "@johndoe" in sent_text
    assert "• <b>ID:</b>" not in sent_text
    assert 'href="tg://user?id=987654321"' in sent_text
    assert "Natijangiz: <b>2 / 5</b>" in sent_text


@pytest.mark.asyncio
async def test_check_full_subscription_blocks_when_inaccessible(db_session: AsyncSession):
    """Verify that when bot cannot access channel (e.g. not admin/chat not found), it treats user as not subscribed"""
    from unittest.mock import AsyncMock, MagicMock
    from aiogram.exceptions import TelegramBadRequest
    from app.services.subscription_service import SubscriptionService
    from app.database.models import Channel

    channel = Channel(channel_id=-1001758698923, title="Test Channel", is_active=True, is_required=True)
    db_session.add(channel)
    await db_session.commit()

    service = SubscriptionService(db_session)
    mock_bot = MagicMock()
    mock_bot.get_chat_member = AsyncMock(
        side_effect=TelegramBadRequest(method=MagicMock(), message="Bad Request: chat not found")
    )

    is_sub = await service.check_full_subscription(bot=mock_bot, telegram_id=8122865725)
    assert is_sub is False

