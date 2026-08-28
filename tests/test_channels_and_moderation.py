"""Tests for channel publishing, template rendering, Seen button idempotency, and anti-spam."""

import pytest
from unittest.mock import AsyncMock
from app.database.repositories import UserRepository, ChannelRepository, SeenRepository
from app.services.channel_publishing.publishing_service import ChannelPublishingService
from app.services.channel_publishing.seen_service import SeenService
from app.services.templates.engine import TemplateEngine
from app.services.moderation.content_filter import ContentFilterService
from app.services.moderation.rate_limiter import RateLimitService


@pytest.mark.asyncio
async def test_template_rendering_and_variable_safety():
    """Verify safe template substitution and validation."""
    valid_template = "{message}\n\n#پیام_ناشناس {nickname}"
    valid, _ = TemplateEngine.validate_template(valid_template)
    assert valid is True

    # Render post
    rendered = TemplateEngine.render_channel_post(
        template=valid_template,
        message_text="This is an anonymous channel post!",
        nickname="Ghost",
    )
    assert "This is an anonymous channel post!" in rendered
    assert "#Ghost" in rendered
    assert "#پیام_ناشناس" in rendered

    # Reject forbidden secrets template
    bad_template = "{message}\nUser ID: {telegram_id}"
    invalid, err = TemplateEngine.validate_template(bad_template)
    assert invalid is False
    assert "forbidden" in err.lower()


@pytest.mark.asyncio
async def test_channel_anonymous_publishing(db_session, mock_bot):
    """Verify channel publishing strips identity and attaches Seen button."""
    user_repo = UserRepository(db_session)
    ch_repo = ChannelRepository(db_session)
    pub_service = ChannelPublishingService(db_session, mock_bot)

    admin, _ = await user_repo.get_or_create(telegram_id=8888, first_name="Admin")
    author, _ = await user_repo.get_or_create(telegram_id=9999, first_name="Author")

    channel = await ch_repo.create_channel(
        telegram_channel_id=-100987654321,
        title="Official Confessions",
        admin_user_id=admin.id,
        random_token="ch_tok_123",
    )

    mock_bot.send_message.reset_mock()
    post_msg = AsyncMock()
    post_msg.message_id = 7771
    mock_bot.send_message.return_value = post_msg

    ok, db_msg, err = await pub_service.publish_anonymous_message(
        channel=channel,
        author_id=author.id,
        content_type="text",
        text_content="Confession message text",
        nickname="SecretGuy",
    )
    assert ok is True
    assert db_msg is not None
    assert db_msg.telegram_post_message_id == 7771
    assert db_msg.author_id == author.id

    # Verify message sent to channel chat_id
    mock_bot.send_message.assert_called_once()
    assert mock_bot.send_message.call_args[1]["chat_id"] == -100987654321


@pytest.mark.asyncio
async def test_seen_button_idempotency_and_author_notification(db_session, mock_bot):
    """Verify Seen count increments once per user and sends milestone notification to author."""
    user_repo = UserRepository(db_session)
    ch_repo = ChannelRepository(db_session)
    seen_repo = SeenRepository(db_session)
    seen_service = SeenService(db_session, mock_bot)

    admin, _ = await user_repo.get_or_create(telegram_id=5000, first_name="Admin")
    author, _ = await user_repo.get_or_create(telegram_id=6000, first_name="Author")
    viewer1, _ = await user_repo.get_or_create(telegram_id=7001, first_name="Viewer1")
    viewer2, _ = await user_repo.get_or_create(telegram_id=7002, first_name="Viewer2")

    channel = await ch_repo.create_channel(
        telegram_channel_id=-100111222333,
        title="Channel",
        admin_user_id=admin.id,
        random_token="ch_token_seen",
    )

    msg = await seen_repo.record_channel_message(
        channel_id=channel.id,
        telegram_post_message_id=5555,
        author_id=author.id,
        text_content="Sample post",
    )

    # 1. First Seen click from Viewer 1
    mock_bot.send_message.reset_mock()
    ok1, res1 = await seen_service.process_seen_click(
        channel_id_str=str(channel.id),
        telegram_post_id=5555,
        viewer_telegram_id=viewer1.telegram_id,
    )
    assert ok1 is True
    assert res1 == "seen_recorded"

    # Verify notification sent to author (milestone = 1)
    mock_bot.send_message.assert_called_once()
    assert mock_bot.send_message.call_args[1]["chat_id"] == author.telegram_id

    # 2. Duplicate click from same Viewer 1 (must be idempotent)
    ok_dup, res_dup = await seen_service.process_seen_click(
        channel_id_str=str(channel.id),
        telegram_post_id=5555,
        viewer_telegram_id=viewer1.telegram_id,
    )
    assert ok_dup is False
    assert res_dup == "seen_already_recorded"

    # 3. Second Seen click from Viewer 2
    ok2, res2 = await seen_service.process_seen_click(
        channel_id_str=str(channel.id),
        telegram_post_id=5555,
        viewer_telegram_id=viewer2.telegram_id,
    )
    assert ok2 is True
    assert res2 == "seen_recorded"


@pytest.mark.asyncio
async def test_content_filter_and_rate_limiting(db_session, mock_redis):
    """Test URL blocking and duplicate message cooldown."""
    filter_service = ContentFilterService(db_session)
    rate_service = RateLimitService(mock_redis)

    # 1. Reject message with URL
    is_clean, reason = await filter_service.filter_content("Check this out: https://spam.com")
    assert is_clean is False
    assert reason == "content_filtered_url"

    # 2. Accept clean message
    is_clean_ok, _ = await filter_service.filter_content("This is a clean and harmless message.")
    assert is_clean_ok is True

    # 3. Duplicate detection
    is_dup1 = await rate_service.check_duplicate_message(12345, "Exact repeated message")
    assert is_dup1 is False  # First time is fine
    is_dup2 = await rate_service.check_duplicate_message(12345, "Exact repeated message")
    assert is_dup2 is True   # Second identical message within window is rejected
