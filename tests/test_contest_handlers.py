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

