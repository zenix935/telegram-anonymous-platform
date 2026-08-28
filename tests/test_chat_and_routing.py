"""Comprehensive tests for message routing, multi-conversation isolation, and reply targeting."""

import pytest
from unittest.mock import AsyncMock
from app.database.models import ConversationStatus
from app.database.repositories import ConversationRepository, ModerationRepository, UserRepository
from app.services.anonymous_chat.chat_service import AnonymousChatService
from app.services.anonymous_chat.reply_target import ReplyTargetService


@pytest.mark.asyncio
async def test_multi_conversation_and_explicit_reply_routing(db_session, mock_bot, mock_redis):
    """
    CRITICAL TEST SCENARIO:
    Owner has conversations with Alice (A), Bob (B), and Charlie (C).
    Owner presses Reply on a message from B.
    Owner sends a message -> routed ONLY to B.
    Owner presses Reply on a message from A.
    Owner sends another message -> routed ONLY to A.
    Verifies total isolation and no cross-conversation leakage.
    """
    user_repo = UserRepository(db_session)
    conv_repo = ConversationRepository(db_session)
    reply_target_service = ReplyTargetService(mock_redis)
    chat_service = AnonymousChatService(db_session, mock_bot, reply_target_service)

    # Create Owner and 3 distinct Senders
    owner, _ = await user_repo.get_or_create(telegram_id=1000, first_name="Owner")
    alice, _ = await user_repo.get_or_create(telegram_id=2001, first_name="Alice")
    bob, _ = await user_repo.get_or_create(telegram_id=2002, first_name="Bob")
    charlie, _ = await user_repo.get_or_create(telegram_id=2003, first_name="Charlie")

    # 1. Establish 3 independent conversations
    conv_a, _ = await chat_service.get_or_create_conversation(owner.id, alice.id, sender_nickname="Alice_Alias")
    conv_b, _ = await chat_service.get_or_create_conversation(owner.id, bob.id, sender_nickname="Bob_Alias")
    conv_c, _ = await chat_service.get_or_create_conversation(owner.id, charlie.id, sender_nickname="Charlie_Alias")

    assert conv_a.id != conv_b.id != conv_c.id

    # 2. Sender B sends a message to Owner
    mock_bot.send_message.reset_mock()
    msg_b_delivery = AsyncMock()
    msg_b_delivery.message_id = 8881
    mock_bot.send_message.return_value = msg_b_delivery

    ok_b, db_msg_b = await chat_service.deliver_sender_message(
        conversation=conv_b,
        sender_user=bob,
        content_type="text",
        text_content="Hello from Bob!",
        sender_tg_msg_id=501,
    )
    assert ok_b is True
    assert db_msg_b.conversation_id == conv_b.id

    # 3. Sender A sends a message to Owner
    msg_a_delivery = AsyncMock()
    msg_a_delivery.message_id = 8882
    mock_bot.send_message.return_value = msg_a_delivery

    ok_a, db_msg_a = await chat_service.deliver_sender_message(
        conversation=conv_a,
        sender_user=alice,
        content_type="text",
        text_content="Hello from Alice!",
        sender_tg_msg_id=601,
    )
    assert ok_a is True
    assert db_msg_a.conversation_id == conv_a.id

    # 4. Owner presses Reply on message from Bob (delivered msg 8881)
    await reply_target_service.set_active_target(
        owner_telegram_id=owner.telegram_id,
        recipient_telegram_message_id=8881,
        conversation_id=str(conv_b.id),
        sender_alias=conv_b.sender_alias,
    )

    # Verify active target points to Bob's conversation
    target = await reply_target_service.get_active_target(owner.telegram_id)
    assert target["conv_id"] == str(conv_b.id)

    # Owner dispatches reply
    mock_bot.send_message.reset_mock()
    reply_delivered = AsyncMock()
    reply_delivered.message_id = 9991
    mock_bot.send_message.return_value = reply_delivered

    ok_reply_b, rep_msg_b = await chat_service.deliver_owner_reply(
        conversation=conv_b,
        owner_user=owner,
        content_type="text",
        text_content="Hi Bob, this reply is only for you!",
    )
    assert ok_reply_b is True
    # Verify Telegram Bot sent message to Bob's telegram_id (2002) and NOT Alice or Charlie
    mock_bot.send_message.assert_called_once()
    assert mock_bot.send_message.call_args[1]["chat_id"] == bob.telegram_id

    # 5. Owner now switches active reply target to message from Alice (delivered msg 8882)
    await reply_target_service.set_active_target(
        owner_telegram_id=owner.telegram_id,
        recipient_telegram_message_id=8882,
        conversation_id=str(conv_a.id),
        sender_alias=conv_a.sender_alias,
    )

    # Verify active target changed
    target_a = await reply_target_service.get_active_target(owner.telegram_id)
    assert target_a["conv_id"] == str(conv_a.id)

    mock_bot.send_message.reset_mock()
    ok_reply_a, rep_msg_a = await chat_service.deliver_owner_reply(
        conversation=conv_a,
        owner_user=owner,
        content_type="text",
        text_content="Hi Alice, this reply is only for you!",
    )
    assert ok_reply_a is True
    # Verify Telegram Bot sent message to Alice's telegram_id (2001) and NOT Bob or Charlie
    mock_bot.send_message.assert_called_once()
    assert mock_bot.send_message.call_args[1]["chat_id"] == alice.telegram_id


@pytest.mark.asyncio
async def test_conversation_blocking_and_reporting(db_session, mock_bot, mock_redis):
    """Test blocking anonymous sender and filing abuse report."""
    user_repo = UserRepository(db_session)
    mod_repo = ModerationRepository(db_session)
    conv_repo = ConversationRepository(db_session)
    reply_target_service = ReplyTargetService(mock_redis)
    chat_service = AnonymousChatService(db_session, mock_bot, reply_target_service)

    owner, _ = await user_repo.get_or_create(telegram_id=3000, first_name="Target Owner")
    spammer, _ = await user_repo.get_or_create(telegram_id=3001, first_name="Spammer")

    # 1. Create conversation
    conv, err = await chat_service.get_or_create_conversation(owner.id, spammer.id)
    assert conv is not None
    assert err is None

    # 2. Block sender
    await mod_repo.block_user(blocker_id=owner.id, blocked_id=spammer.id)
    await conv_repo.set_status(conv.id, ConversationStatus.BLOCKED)

    # 3. Subsequent attempts to message through owner's link must fail
    blocked_conv, block_err = await chat_service.get_or_create_conversation(owner.id, spammer.id)
    assert blocked_conv is None
    assert block_err == "sender_blocked"

    # 4. Report abusive message/conversation
    report = await mod_repo.create_report(
        reporter_id=owner.id,
        reported_user_id=spammer.id,
        reason="Harassment and spam",
        conversation_id=conv.id,
    )
    assert report.id is not None
    assert report.status.value == "PENDING"
