"""Unit and integration tests for prize flow and closed channel management"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.bot.handlers.user.chat_member import on_chat_member_updated
from app.bot.handlers.user.prize import (
    check_and_send_prize,
    kick_user_from_prize_channel,
    send_prize_link,
)
from app.database.models import Channel, Contest, User


@pytest.mark.asyncio
class TestPrizeFlow:
    """Test 1-time invite link generation and prize logic"""

    async def test_kick_user_from_prize_channel(self):
        """Test kicking user by banning and unbanning"""
        bot = MagicMock()
        bot.ban_chat_member = AsyncMock(return_value=True)
        bot.unban_chat_member = AsyncMock(return_value=True)

        result = await kick_user_from_prize_channel(bot, prize_channel_id=-1009999999999, user_id=12345)

        assert result is True
        bot.ban_chat_member.assert_awaited_once_with(chat_id=-1009999999999, user_id=12345)
        bot.unban_chat_member.assert_awaited_once_with(
            chat_id=-1009999999999, user_id=12345, only_if_banned=True
        )

    async def test_send_prize_link_one_time(self):
        """Test creating a 1-time link with member_limit=1"""
        bot = MagicMock()
        bot.unban_chat_member = AsyncMock(return_value=True)
        mock_invite = MagicMock()
        mock_invite.invite_link = "https://t.me/+OneTimeLink123"
        bot.create_chat_invite_link = AsyncMock(return_value=mock_invite)
        bot.send_message = AsyncMock(return_value=MagicMock())

        contest = Contest(
            title="Super Konkurs",
            prize_channel_id=-1001112223334,
            prize_channel_title="Yopiq Premium Kanal",
            required_referrals=5,
        )

        success = await send_prize_link(bot, user_id=987654, contest=contest, is_resubscribed=False)

        assert success is True
        # Verify 1-time link was requested
        bot.create_chat_invite_link.assert_awaited_once_with(
            chat_id=-1001112223334,
            member_limit=1,
            creates_join_request=False,
            name="User 987654",
        )
        bot.send_message.assert_awaited_once()
        args, kwargs = bot.send_message.call_args
        assert kwargs["chat_id"] == 987654
        assert "1 marta" in kwargs["text"]

    async def test_check_and_send_prize_when_subscribed(self, db_session: AsyncSession):
        """Test check_and_send_prize gives link when user meets referral target and is subscribed"""
        user = User(telegram_id=111222, full_name="Active Referrer", referral_count=5, is_subscribed=True)
        contest = Contest(
            title="Konkurs",
            prize_channel_id=-100555666777,
            prize_channel_title="Yopiq Kanal",
            required_referrals=5,
            is_active=True,
        )
        db_session.add_all([user, contest])
        await db_session.commit()

        bot = MagicMock()
        bot.unban_chat_member = AsyncMock(return_value=True)
        mock_invite = MagicMock()
        mock_invite.invite_link = "https://t.me/+Link"
        bot.create_chat_invite_link = AsyncMock(return_value=mock_invite)
        bot.send_message = AsyncMock(return_value=MagicMock())

        # No mandatory channels in DB, so check_full_subscription returns True
        result = await check_and_send_prize(bot, 111222, db_session)

        assert result is True
        await db_session.refresh(user)
        assert user.has_prize_access is True

    async def test_check_and_send_prize_blocked_when_not_subscribed(self, db_session: AsyncSession):
        """Test check_and_send_prize does not give link if mandatory channel not subscribed"""
        user = User(
            telegram_id=333444,
            full_name="User",
            referral_count=5,
            has_prize_access=True,
        )
        channel = Channel(
            channel_id=-100888999,
            title="Majburiy Kanal",
            is_active=True,
            is_required=True,
        )
        contest = Contest(
            title="Konkurs",
            prize_channel_id=-100555666777,
            prize_channel_title="Yopiq Kanal",
            required_referrals=5,
            is_active=True,
        )
        db_session.add_all([user, channel, contest])
        await db_session.commit()

        bot = MagicMock()
        # User is not a member of mandatory channel
        mock_member = MagicMock()
        mock_member.status = "left"
        bot.get_chat_member = AsyncMock(return_value=mock_member)
        bot.ban_chat_member = AsyncMock(return_value=True)
        bot.unban_chat_member = AsyncMock(return_value=True)

        result = await check_and_send_prize(bot, 333444, db_session)

        # Should be False and user kicked from prize channel
        assert result is False
        bot.ban_chat_member.assert_awaited_once_with(chat_id=-100555666777, user_id=333444)
        await db_session.refresh(user)
        assert user.has_prize_access is False


@pytest.mark.asyncio
class TestChatMemberUpdatedFlow:
    """Test ChatMemberUpdated events for kick and rejoin"""

    async def test_user_leaves_mandatory_channel_gets_kicked_from_prize(self, db_session: AsyncSession):
        """User leaves mandatory channel -> kicked from closed channel"""
        user = User(
            telegram_id=777888,
            full_name="Kicked User",
            referral_count=10,
            has_prize_access=True,
            is_subscribed=True,
        )
        channel = Channel(
            channel_id=-100444555,
            title="Majburiy Kanal 1",
            is_active=True,
            is_required=True,
        )
        contest = Contest(
            title="Konkurs",
            prize_channel_id=-100999000,
            prize_channel_title="Yopiq Kanal",
            required_referrals=5,
            is_active=True,
        )
        db_session.add_all([user, channel, contest])
        await db_session.commit()

        bot = MagicMock()
        bot.ban_chat_member = AsyncMock(return_value=True)
        bot.unban_chat_member = AsyncMock(return_value=True)
        bot.send_message = AsyncMock(return_value=MagicMock())

        # Create mock ChatMemberUpdated event where user left channel -100444555
        event = MagicMock()
        event.chat.id = -100444555
        event.new_chat_member.user.id = 777888
        event.new_chat_member.user.is_bot = False
        event.old_chat_member.status = "member"
        event.new_chat_member.status = "left"

        await on_chat_member_updated(event, bot, db_session)

        # Verified that bot kicked user from prize channel
        bot.ban_chat_member.assert_awaited_once_with(chat_id=-100999000, user_id=777888)
        bot.unban_chat_member.assert_awaited_once_with(
            chat_id=-100999000, user_id=777888, only_if_banned=True
        )
        await db_session.refresh(user)
        assert user.has_prize_access is False
        assert user.is_subscribed is False
        # Verified notification was sent to user
        bot.send_message.assert_awaited_once()
        args, kwargs = bot.send_message.call_args
        assert kwargs["chat_id"] == 777888
        assert "yopiq kanaldan chiqarildingiz" in kwargs["text"]

    async def test_user_rejoins_mandatory_channel_gets_new_link(self, db_session: AsyncSession):
        """User rejoins mandatory channel -> issued fresh 1-time link"""
        user = User(
            telegram_id=777888,
            full_name="Rejoining User",
            referral_count=10,
            has_prize_access=False,  # previously revoked
            is_subscribed=False,
        )
        channel = Channel(
            channel_id=-100444555,
            title="Majburiy Kanal 1",
            is_active=True,
            is_required=True,
        )
        contest = Contest(
            title="Konkurs",
            prize_channel_id=-100999000,
            prize_channel_title="Yopiq Kanal",
            required_referrals=5,
            is_active=True,
        )
        db_session.add_all([user, channel, contest])
        await db_session.commit()

        bot = MagicMock()
        mock_member = MagicMock()
        mock_member.status = "member"
        bot.get_chat_member = AsyncMock(return_value=mock_member)
        bot.unban_chat_member = AsyncMock(return_value=True)
        mock_invite = MagicMock()
        mock_invite.invite_link = "https://t.me/+NewOneTimeLink"
        bot.create_chat_invite_link = AsyncMock(return_value=mock_invite)
        bot.send_message = AsyncMock(return_value=MagicMock())

        # Event: user joined back
        event = MagicMock()
        event.chat.id = -100444555
        event.new_chat_member.user.id = 777888
        event.new_chat_member.user.is_bot = False
        event.old_chat_member.status = "left"
        event.new_chat_member.status = "member"

        await on_chat_member_updated(event, bot, db_session)

        # Verified fresh 1-time link created and sent
        bot.create_chat_invite_link.assert_awaited_once_with(
            chat_id=-100999000,
            member_limit=1,
            creates_join_request=False,
            name="User 777888",
        )
        await db_session.refresh(user)
        assert user.has_prize_access is True
        assert user.is_subscribed is True
        bot.send_message.assert_awaited_once()
        args, kwargs = bot.send_message.call_args
        assert kwargs["chat_id"] == 777888
        assert "yangi 1 martalik havolangiz" in kwargs["text"]
