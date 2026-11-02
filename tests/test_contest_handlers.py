from unittest.mock import AsyncMock, MagicMock

import pytest

from app.bot.handlers.admin.contest import contest_title


@pytest.mark.asyncio
async def test_contest_title_non_text_message():
    """Verify that contest_title does not crash when message.text is None"""
    message = MagicMock()
    message.from_user.id = 8122865725  # admin
    message.text = None
    message.caption = None
    message.answer = AsyncMock()

    state = MagicMock()
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()

    db = AsyncMock()

    await contest_title(message, state, db)

    message.answer.assert_awaited_once()
    assert "❌ Nom juda qisqa yoki noto'g'ri" in message.answer.call_args[0][0]
    state.update_data.assert_not_called()


@pytest.mark.asyncio
async def test_contest_title_with_valid_text():
    """Verify contest_title saves valid title"""
    message = MagicMock()
    message.from_user.id = 8122865725
    message.text = "Navro'z Konkurs 2026"
    message.caption = None
    message.answer = AsyncMock()

    state = MagicMock()
    state.update_data = AsyncMock()
    state.set_state = AsyncMock()

    db = AsyncMock()

    await contest_title(message, state, db)

    state.update_data.assert_awaited_once_with(title="Navro'z Konkurs 2026")
    message.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_webhook_endpoint_catches_exceptions(monkeypatch):
    """Verify that webhook endpoint does not return 500 when feed_raw_update fails"""
    from api.main import dp, webhook

    async def mock_feed(*args, **kwargs):
        raise ValueError("Simulated unexpected handler error")

    monkeypatch.setattr(dp, "feed_raw_update", mock_feed)

    mock_request = MagicMock()
    mock_request.json = AsyncMock(return_value={"update_id": 12345})

    response = await webhook(mock_request)
    assert response == {"status": "ok"}


@pytest.mark.asyncio
async def test_referral_not_counted_until_subscribed(db_session):
    """Test referral is not counted (+1) until user subscribes and confirm_referral is called"""
    from app.database.models import User
    from app.services.referral_service import ReferralService

    referrer = User(telegram_id=111222333, full_name="Referrer A")
    new_user = User(telegram_id=444555666, full_name="User B")
    db_session.add_all([referrer, new_user])
    await db_session.commit()

    service = ReferralService(db_session)
    registered = await service.process_new_referral(
        new_user_telegram_id=444555666,
        referrer_telegram_id=111222333,
        give_bonus=False,
    )
    assert registered is True

    await db_session.refresh(referrer)
    assert referrer.referral_count == 0  # Hali 0 ta, chunki obuna bo'lmagan

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    mock_bot.get_me = AsyncMock(return_value=MagicMock(username="test_bot"))

    confirmed = await service.confirm_referral(444555666, mock_bot)
    assert confirmed is True

    await db_session.refresh(referrer)
    assert referrer.referral_count == 1  # Endi 1 ta bo'ldi!


@pytest.mark.asyncio
async def test_prize_link_combined_message():
    """Test send_prize_link produces a single post combining prize link and stats"""
    from app.bot.handlers.user.prize import send_prize_link
    from app.database.models import Contest

    contest = Contest(
        title="Super Konkurs",
        prize_channel_id=-100999888,
        prize_channel_title="Python VIP",
        required_referrals=1,
    )
    mock_bot = MagicMock()
    mock_invite = MagicMock(invite_link="https://t.me/+AbCdEf")
    mock_bot.create_chat_invite_link = AsyncMock(return_value=mock_invite)
    mock_bot.unban_chat_member = AsyncMock()
    mock_bot.send_message = AsyncMock()

    sent = await send_prize_link(
        bot=mock_bot,
        user_id=123456,
        contest=contest,
        is_resubscribed=True,
        ref_count=1,
    )
    assert sent is True
    mock_bot.send_message.assert_awaited_once()
    sent_text = mock_bot.send_message.call_args[1]["text"]
    assert "✅ <b>Obuna tasdiqlandi!</b>" in sent_text
    assert "Python VIP</b> kanaliga 1 martalik havolangiz:" in sent_text
    assert "📊 <b>Sizning natijangiz</b>" in sent_text
    assert "✅ Tasdiqlangan: <b>1 ta</b>" in sent_text


@pytest.mark.asyncio
async def test_cmd_mystats_clean_without_obuna_tasdiqlandi(db_session):
    """Test /stats command outputs results without 'Obuna tasdiqlandi'"""
    from app.bot.handlers.user.stats import cmd_mystats
    from app.database.models import User

    user = User(telegram_id=999888, full_name="Test User", referral_count=2)
    db_session.add(user)
    await db_session.commit()

    message = MagicMock()
    message.from_user.id = 999888
    message.answer = AsyncMock()

    await cmd_mystats(message, db_session)
    message.answer.assert_awaited_once()
    text = message.answer.call_args[0][0]
    assert "Obuna tasdiqlandi" not in text
    assert "📊 <b>Sizning natijangiz</b>" in text
    assert "✅ Tasdiqlangan: <b>2 ta</b>" in text


