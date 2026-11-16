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


@pytest.mark.asyncio
async def test_my_referrals_cb_when_user_not_in_db(db_session):
    """Test 'Natijam' button creates user if missing and renders stats"""
    from app.bot.handlers.user.stats import my_referrals_cb

    callback = MagicMock()
    callback.from_user.id = 7381087311
    callback.from_user.full_name = "Anasxon Ummataliy"
    callback.from_user.username = "anasxon_ummataliy"
    callback.from_user.language_code = "uz"
    callback.answer = AsyncMock()
    callback.message.edit_text = AsyncMock()

    await my_referrals_cb(callback, db_session)

    callback.message.edit_text.assert_awaited_once()
    text = callback.message.edit_text.call_args[0][0]
    assert "📊 <b>Sizning natijangiz</b>" in text
    assert "✅ Tasdiqlangan: <b>0 ta</b>" in text
    assert "Hali hech kimni taklif qilmadingiz" in text


@pytest.mark.asyncio
async def test_cmd_start_with_referral_payload_registers_referral_and_notifies(db_session):
    """Test /start <referrer_id> registers referral and triggers notification"""
    from app.bot.handlers.user.start import cmd_start
    from app.database.models import User, Contest

    # Referrer
    referrer = User(telegram_id=7381087311, full_name="Referrer Anas", referral_count=0)
    contest = Contest(title="Test Contest", required_referrals=1, is_active=True)
    db_session.add_all([referrer, contest])
    await db_session.commit()

    # New user joins with /start 7381087311
    message = MagicMock()
    message.from_user.id = 8730701881
    message.from_user.is_bot = False
    message.from_user.full_name = "Invited Friend"
    message.from_user.username = "invited_friend"
    message.from_user.language_code = "uz"
    message.chat.id = 8730701881
    message.chat.full_name = "Invited Friend"
    message.chat.username = "invited_friend"
    message.text = "/start 7381087311"
    message.answer = AsyncMock()

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    mock_bot.get_me = AsyncMock(return_value=MagicMock(username="OralExamBot"))
    mock_bot.get_chat_member = AsyncMock()
    message.bot = mock_bot

    await cmd_start(message, mock_bot, db_session)

    # Referrer should have received a notification and referral_count should be +1!
    await db_session.refresh(referrer)
    assert referrer.referral_count == 1
    mock_bot.send_message.assert_awaited()
    # Check that a notification message was sent to referrer 7381087311
    sent_to_referrer = any(
        call.kwargs.get("chat_id") == 7381087311 for call in mock_bot.send_message.call_args_list
    )
    assert sent_to_referrer is True


@pytest.mark.asyncio
async def test_cmd_start_with_existing_user_notifies_referrer_already_user(db_session):
    """When an existing bot user clicks someone's referral link, referrer is notified that user was already a member"""
    from app.bot.handlers.user.start import cmd_start
    from app.database.models import User, Contest

    # Referrer
    referrer = User(telegram_id=222333, full_name="Active Referrer", referral_count=0)
    # Existing user (already registered in DB)
    existing_user = User(telegram_id=444555, full_name="Already Existing User", username="old_user")
    contest = Contest(title="Writing 2026", required_referrals=5, is_active=True)
    db_session.add_all([referrer, existing_user, contest])
    await db_session.commit()

    # Existing user clicks referral link of referrer: /start 222333
    message = MagicMock()
    message.from_user.id = 444555
    message.from_user.is_bot = False
    message.from_user.full_name = "Already Existing User"
    message.from_user.username = "old_user"
    message.from_user.language_code = "uz"
    message.chat.id = 444555
    message.chat.full_name = "Already Existing User"
    message.chat.username = "old_user"
    message.text = "/start 222333"
    message.answer = AsyncMock()

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock()
    mock_bot.get_me = AsyncMock(return_value=MagicMock(username="TestBot"))
    mock_bot.get_chat_member = AsyncMock()
    message.bot = mock_bot

    await cmd_start(message, mock_bot, db_session)

    # Referrer referral_count must NOT increase
    await db_session.refresh(referrer)
    assert referrer.referral_count == 0

    # Referrer must receive a notification stating that the user was already a member
    referrer_notifications = [
        call.kwargs for call in mock_bot.send_message.call_args_list
        if call.kwargs.get("chat_id") == 222333
    ]
    assert len(referrer_notifications) >= 1
    text = referrer_notifications[0].get("text", "")
    assert "allaqachon botimiz foydalanuvchisi edi" in text
    assert "Already Existing User" in text


@pytest.mark.asyncio
async def test_generate_admin_prize_link_success(db_session):
    """Test generating 1-time prize channel link for admin"""
    from app.database.models import Contest
    from app.bot.handlers.admin.contest import generate_admin_prize_link

    contest = Contest(
        title="Admin Test Contest",
        required_referrals=5,
        prize_channel_id=-1003750541188,
        prize_channel_title="Dominators",
        is_active=True,
    )
    db_session.add(contest)
    await db_session.commit()

    mock_bot = MagicMock()
    mock_invite = MagicMock()
    mock_invite.invite_link = "https://t.me/+AdminPrize123"
    mock_bot.create_chat_invite_link = AsyncMock(return_value=mock_invite)

    link, title = await generate_admin_prize_link(mock_bot, db_session, 8122865725)
    assert link == "https://t.me/+AdminPrize123"
    assert title == "Dominators"
    mock_bot.create_chat_invite_link.assert_awaited_once_with(
        chat_id=-1003750541188,
        member_limit=1,
        creates_join_request=False,
        name="Admin link (8122865725)",
    )


@pytest.mark.asyncio
async def test_generate_admin_prize_link_no_prize_channel(db_session):
    """Test generating prize link when no prize channel is set"""
    from app.database.models import Contest
    from app.bot.handlers.admin.contest import generate_admin_prize_link

    contest = Contest(
        title="Contest Without Prize",
        required_referrals=5,
        prize_channel_id=None,
        is_active=True,
    )
    db_session.add(contest)
    await db_session.commit()

    mock_bot = MagicMock()
    link, err = await generate_admin_prize_link(mock_bot, db_session, 8122865725)
    assert link is None
    assert "Prize kanal belgilanmagan" in err


@pytest.mark.asyncio
async def test_adm_get_prize_link_cb(db_session):
    """Test callback query to get 1-time prize link"""
    from app.database.models import Contest, Admin
    from app.bot.handlers.admin.contest import adm_get_prize_link_cb

    admin = Admin(telegram_id=8122865725, full_name="Super Admin")
    contest = Contest(
        title="Active Contest",
        required_referrals=5,
        prize_channel_id=-1003750541188,
        prize_channel_title="Dominators VIP",
        is_active=True,
    )
    db_session.add_all([admin, contest])
    await db_session.commit()

    callback = MagicMock()
    callback.from_user.id = 8122865725
    callback.answer = AsyncMock()
    callback.message.edit_text = AsyncMock()
    callback.message.answer = AsyncMock()

    mock_bot = MagicMock()
    mock_invite = MagicMock()
    mock_invite.invite_link = "https://t.me/+AdmOneTimeCb"
    mock_bot.create_chat_invite_link = AsyncMock(return_value=mock_invite)
    callback.bot = mock_bot

    await adm_get_prize_link_cb(callback, db_session)

    callback.message.edit_text.assert_awaited_once()
    sent_text = callback.message.edit_text.call_args[0][0]
    assert "https://t.me/+AdmOneTimeCb" in sent_text
    assert "Dominators VIP" in sent_text
    assert "faqat <b>1 marta</b> ishlaydi" in sent_text


@pytest.mark.asyncio
async def test_cmd_referral_and_link_for_admin_and_user(db_session):
    """Test /link command behavior for admin (gives prize link + referral link) and regular user (gives referral link)"""
    from app.database.models import Contest, Admin, User
    from app.bot.handlers.user.share import cmd_referral

    admin = Admin(telegram_id=8122865725, full_name="Super Admin")
    admin_user = User(telegram_id=8122865725, full_name="Admin Boss")
    reg_user = User(telegram_id=999888, full_name="Regular User")
    contest = Contest(
        title="Active Contest",
        required_referrals=5,
        prize_channel_id=-1003750541188,
        prize_channel_title="Dominators VIP",
        is_active=True,
    )
    db_session.add_all([admin, admin_user, reg_user, contest])
    await db_session.commit()

    mock_bot = MagicMock()
    mock_bot.get_me = AsyncMock(return_value=MagicMock(username="hasanboevs_bot"))
    mock_invite = MagicMock()
    mock_invite.invite_link = "https://t.me/+AdminSecret123"
    mock_bot.create_chat_invite_link = AsyncMock(return_value=mock_invite)

    # 1. Admin calls /link
    admin_msg = MagicMock()
    admin_msg.from_user.id = 8122865725
    admin_msg.bot = mock_bot
    admin_msg.answer = AsyncMock()

    await cmd_referral(admin_msg, db_session)
    admin_msg.answer.assert_awaited_once()
    admin_text = admin_msg.answer.call_args[0][0]
    assert "https://t.me/+AdminSecret123" in admin_text
    assert "1 martalik Prize Havola" in admin_text
    assert "Shaxsiy Taklif Havolangiz" in admin_text
    assert "hasanboevs_bot?start=8122865725" in admin_text

    # 2. Regular user calls /link
    user_msg = MagicMock()
    user_msg.from_user.id = 999888
    user_msg.bot = mock_bot
    user_msg.answer = AsyncMock()

    await cmd_referral(user_msg, db_session)
    user_msg.answer.assert_awaited_once()
    user_text = user_msg.answer.call_args[0][0]
    assert "Taklif havolangiz" in user_text
    assert "hasanboevs_bot?start=999888" in user_text
    # Regular user must NOT see the 1-time prize link!
    assert "1 martalik Prize Havola" not in user_text
    assert "Admin" not in user_text





