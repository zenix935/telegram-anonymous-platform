"""Handlers for personal anonymous chat interactions, inbox, and message-level replies."""

import uuid
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.messages import get_text
from app.database.models import ConversationStatus, User
from app.database.repositories import (
    ConversationRepository,
    ModerationRepository,
    UserRepository,
)
from app.bot.keyboards.inline import (
    get_inbox_inline_keyboard,
    get_conversation_action_inline_keyboard,
    get_cancel_inline_keyboard,
    get_main_menu_inline_keyboard,
)
from app.bot.states.fsm import PersonalChatStates
from app.services.anonymous_chat.chat_service import AnonymousChatService
from app.services.anonymous_chat.reply_target import ReplyTargetService
from app.services.moderation.content_filter import ContentFilterService
from app.services.moderation.rate_limiter import RateLimitService
from app.utils.redis import get_redis_pool

router = Router(name="personal_chat_router")


# --- 1. SENDER FLOW: Sending anonymous message to link owner ---


@router.message(PersonalChatStates.waiting_for_message)
async def handle_sender_submitting_message(
    message: types.Message,
    db_session: AsyncSession,
    db_user: User,
    bot: Bot,
    state: FSMContext,
):
    """Anonymous sender submits message to link owner."""
    state_data = await state.get_data()
    target_owner_id_str = state_data.get("target_owner_id")

    if not target_owner_id_str:
        await state.clear()
        await message.answer(get_text("generic_error"))
        return

    target_owner_id = uuid.UUID(target_owner_id_str)

    # Content moderation & Duplicate check
    content_text = message.text or message.caption or ""
    filter_service = ContentFilterService(db_session)
    is_clean, reason = await filter_service.filter_content(content_text)
    if not is_clean:
        await message.answer(get_text(reason or "content_filtered_word"))
        return

    redis = await get_redis_pool()
    rate_service = RateLimitService(redis)
    if await rate_service.check_duplicate_message(message.from_user.id, content_text):
        await message.answer(get_text("duplicate_message_rejected"))
        return

    # Extract media content
    content_type = "text"
    media_file_id = None
    if message.photo:
        content_type = "photo"
        media_file_id = message.photo[-1].file_id
    elif message.voice:
        content_type = "voice"
        media_file_id = message.voice.file_id
    elif message.video:
        content_type = "video"
        media_file_id = message.video.file_id
    elif message.document:
        content_type = "document"
        media_file_id = message.document.file_id
    elif message.audio:
        content_type = "audio"
        media_file_id = message.audio.file_id
    elif message.animation:
        content_type = "animation"
        media_file_id = message.animation.file_id
    elif message.sticker:
        content_type = "sticker"
        media_file_id = message.sticker.file_id

    # Retrieve or create conversation
    reply_target_service = ReplyTargetService(redis)
    chat_service = AnonymousChatService(db_session, bot, reply_target_service)

    user_repo = UserRepository(db_session)
    profile_user = await user_repo.get_by_id(db_user.id)
    sender_nickname = profile_user.anonymous_profile.nickname if profile_user and profile_user.anonymous_profile else None

    conv, err = await chat_service.get_or_create_conversation(
        owner_id=target_owner_id,
        sender_id=db_user.id,
        sender_nickname=sender_nickname,
    )
    if not conv:
        await message.answer(get_text(err or "generic_error"))
        return

    # Deliver message to owner
    success, db_msg = await chat_service.deliver_sender_message(
        conversation=conv,
        sender_user=db_user,
        content_type=content_type,
        text_content=message.text,
        media_file_id=media_file_id,
        caption=message.caption,
        sender_tg_msg_id=message.message_id,
    )

    if success:
        await message.answer(
            get_text("message_sent_to_recipient"),
            reply_markup=get_main_menu_inline_keyboard(is_admin=db_user.is_admin),
        )
        await state.clear()
    else:
        await message.answer(get_text("generic_error"))


# --- 2. OWNER FLOW: Inbox & Viewing Conversations ---


@router.callback_query(F.data.startswith("nav:inbox:"))
async def handle_open_inbox(
    call: types.CallbackQuery, db_session: AsyncSession, db_user: User
):
    """Display owner inbox of anonymous conversations."""
    page = int(call.data.split(":")[2])
    conv_repo = ConversationRepository(db_session)
    conversations, total = await conv_repo.get_owner_inbox(
        owner_id=db_user.id, limit=10, offset=page * 10
    )

    if total == 0:
        await call.message.edit_text(
            get_text("inbox_empty"),
            reply_markup=get_main_menu_inline_keyboard(is_admin=db_user.is_admin),
        )
        await call.answer()
        return

    kb = get_inbox_inline_keyboard(conversations, page=page, total_count=total)
    await call.message.edit_text(
        get_text("inbox_title", total_count=total),
        reply_markup=kb,
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("conv:open:"))
async def handle_view_conversation(
    call: types.CallbackQuery, db_session: AsyncSession, db_user: User
):
    """View details of a specific conversation from the inbox."""
    conv_id_str = call.data.split(":")[2]
    conv_repo = ConversationRepository(db_session)
    conv = await conv_repo.get_by_id(uuid.UUID(conv_id_str))

    if not conv or conv.owner_id != db_user.id:
        await call.answer("گفت‌وگو یافت نشد.", show_alert=True)
        return

    status_str = (
        "🟢 در حال گفت‌وگو"
        if conv.status == ConversationStatus.ACTIVE
        else "⚪ بسته شده"
    )
    text = get_text(
        "conversation_view_title",
        sender_alias=conv.sender_alias,
        status=status_str,
        created_at=conv.created_at.strftime("%Y-%m-%d %H:%M"),
        last_message_at=conv.last_message_at.strftime("%Y-%m-%d %H:%M"),
    )
    kb = get_conversation_action_inline_keyboard(
        conv_id=str(conv.id), is_active=(conv.status == ConversationStatus.ACTIVE)
    )
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


# --- 3. MESSAGE-LEVEL REPLY TARGETING ---


@router.callback_query(F.data.startswith("reply:msg:"))
async def handle_reply_to_specific_message(
    call: types.CallbackQuery,
    db_session: AsyncSession,
    db_user: User,
    state: FSMContext,
):
    """
    Owner clicks 'Reply' on an incoming message.
    Sets explicit message-level reply target in Redis and activates reply state.
    """
    parts = call.data.split(":")
    delivered_tg_msg_id = int(parts[2])
    conv_id_str = parts[3]

    conv_repo = ConversationRepository(db_session)
    conv = await conv_repo.get_by_id(uuid.UUID(conv_id_str))
    if not conv or conv.owner_id != db_user.id:
        await call.answer("گفت‌وگو یافت نشد.", show_alert=True)
        return

    # Set message-level reply target in Redis
    redis = await get_redis_pool()
    reply_target_service = ReplyTargetService(redis)
    await reply_target_service.set_active_target(
        owner_telegram_id=call.from_user.id,
        recipient_telegram_message_id=delivered_tg_msg_id,
        conversation_id=str(conv.id),
        sender_alias=conv.sender_alias,
    )

    await state.set_state(PersonalChatStates.replying_to_message)
    await state.update_data(active_conv_id=str(conv.id))

    await call.message.reply(
        get_text(
            "reply_mode_activated",
            sender_alias=conv.sender_alias,
            reply_target=f"msg_{delivered_tg_msg_id}",
        ),
        reply_markup=get_cancel_inline_keyboard(),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("conv:reply:"))
async def handle_reply_from_conv_view(
    call: types.CallbackQuery,
    db_session: AsyncSession,
    db_user: User,
    state: FSMContext,
):
    """Owner initiates reply from within conversation view."""
    conv_id_str = call.data.split(":")[2]
    conv_repo = ConversationRepository(db_session)
    conv = await conv_repo.get_by_id(uuid.UUID(conv_id_str))

    if not conv or conv.owner_id != db_user.id:
        await call.answer("گفت‌وگو یافت نشد.", show_alert=True)
        return

    # Set active conversation target in Redis
    redis = await get_redis_pool()
    reply_target_service = ReplyTargetService(redis)
    await reply_target_service.set_active_target(
        owner_telegram_id=call.from_user.id,
        recipient_telegram_message_id=0,
        conversation_id=str(conv.id),
        sender_alias=conv.sender_alias,
    )

    await state.set_state(PersonalChatStates.replying_to_message)
    await state.update_data(active_conv_id=str(conv.id))

    await call.message.reply(
        get_text("reply_mode_activated", sender_alias=conv.sender_alias, reply_target=f"conv_{str(conv.id)[:8]}"),
        reply_markup=get_cancel_inline_keyboard(),
        parse_mode="HTML",
    )
    await call.answer()


@router.message(PersonalChatStates.replying_to_message)
async def handle_owner_sending_reply(
    message: types.Message,
    db_session: AsyncSession,
    db_user: User,
    bot: Bot,
    state: FSMContext,
):
    """
    Owner sends response message.
    Message is strictly routed ONLY to the conversation bound to active reply target.
    """
    redis = await get_redis_pool()
    reply_target_service = ReplyTargetService(redis)
    active_target = await reply_target_service.get_active_target(message.from_user.id)

    if not active_target or "conv_id" not in active_target:
        await state.clear()
        await message.answer("⚠️ نشست پاسخ منقضی شده است. لطفاً مجدداً دکمه پاسخ را انتخاب کنید.")
        return

    conv_id = uuid.UUID(active_target["conv_id"])
    conv_repo = ConversationRepository(db_session)
    conv = await conv_repo.get_by_id(conv_id)

    if not conv or conv.owner_id != db_user.id:
        await state.clear()
        await message.answer("❌ گفت‌وگو معتبر نیست.")
        return

    if conv.status != ConversationStatus.ACTIVE:
        await state.clear()
        await message.answer("⚠️ این گفت‌وگو قبلاً بسته شده است.")
        return

    # Content filter
    content_text = message.text or message.caption or ""
    filter_service = ContentFilterService(db_session)
    is_clean, reason = await filter_service.filter_content(content_text)
    if not is_clean:
        await message.answer(get_text(reason or "content_filtered_word"))
        return

    # Determine message content type
    content_type = "text"
    media_file_id = None
    if message.photo:
        content_type = "photo"
        media_file_id = message.photo[-1].file_id
    elif message.voice:
        content_type = "voice"
        media_file_id = message.voice.file_id
    elif message.video:
        content_type = "video"
        media_file_id = message.video.file_id
    elif message.document:
        content_type = "document"
        media_file_id = message.document.file_id
    elif message.sticker:
        content_type = "sticker"
        media_file_id = message.sticker.file_id

    chat_service = AnonymousChatService(db_session, bot, reply_target_service)
    success, _ = await chat_service.deliver_owner_reply(
        conversation=conv,
        owner_user=db_user,
        content_type=content_type,
        text_content=message.text,
        media_file_id=media_file_id,
        caption=message.caption,
        owner_tg_msg_id=message.message_id,
    )

    if success:
        await message.answer(
            get_text("reply_sent_success"),
            reply_markup=get_main_menu_inline_keyboard(is_admin=db_user.is_admin),
        )
        # Clear reply target
        await reply_target_service.clear_active_target(message.from_user.id)
        await state.clear()
    else:
        await message.answer(get_text("generic_error"))


# --- 4. CONVERSATION MANAGEMENT: Close, Block, Report ---


@router.callback_query(F.data.startswith("conv:close:"))
async def handle_close_conversation(
    call: types.CallbackQuery, db_session: AsyncSession, db_user: User
):
    """Close an active conversation."""
    conv_id_str = call.data.split(":")[2]
    conv_repo = ConversationRepository(db_session)
    conv = await conv_repo.get_by_id(uuid.UUID(conv_id_str))

    if not conv or (conv.owner_id != db_user.id and conv.sender_id != db_user.id):
        await call.answer("گفت‌وگو یافت نشد.", show_alert=True)
        return

    new_status = (
        ConversationStatus.CLOSED_BY_OWNER
        if conv.owner_id == db_user.id
        else ConversationStatus.CLOSED_BY_SENDER
    )
    await conv_repo.set_status(conv.id, new_status)
    await call.message.edit_text("🚪 این گفت‌وگو با موفقیت بسته شد.")
    await call.answer()


@router.callback_query(F.data.startswith("conv:block:"))
async def handle_block_conversation_user(
    call: types.CallbackQuery, db_session: AsyncSession, db_user: User
):
    """Block the anonymous participant in the conversation."""
    conv_id_str = call.data.split(":")[2]
    conv_repo = ConversationRepository(db_session)
    conv = await conv_repo.get_by_id(uuid.UUID(conv_id_str))

    if not conv or conv.owner_id != db_user.id:
        await call.answer("گفت‌وگو یافت نشد.", show_alert=True)
        return

    mod_repo = ModerationRepository(db_session)
    await mod_repo.block_user(blocker_id=db_user.id, blocked_id=conv.sender_id)
    await conv_repo.set_status(conv.id, ConversationStatus.BLOCKED)

    await call.answer(get_text("user_blocked_success"), show_alert=True)
    await call.message.edit_text("🚫 فرستنده ناشناس مسدود شد و گفت‌وگو پایان یافت.")


@router.callback_query(F.data.startswith("conv:report:"))
async def handle_report_prompt(call: types.CallbackQuery, state: FSMContext):
    """Prompt for report reason."""
    conv_id_str = call.data.split(":")[2]
    await state.set_state(PersonalChatStates.reporting_reason)
    await state.update_data(reporting_conv_id=conv_id_str)
    await call.message.edit_text(
        get_text("report_prompt"), reply_markup=get_cancel_inline_keyboard()
    )
    await call.answer()


@router.message(PersonalChatStates.reporting_reason, F.text)
async def handle_submit_report(
    message: types.Message, db_session: AsyncSession, db_user: User, state: FSMContext
):
    """Persist abuse report."""
    reason = message.text.strip()
    data = await state.get_data()
    conv_id_str = data.get("reporting_conv_id")

    if conv_id_str:
        conv_repo = ConversationRepository(db_session)
        conv = await conv_repo.get_by_id(uuid.UUID(conv_id_str))
        if conv:
            reported_user_id = conv.sender_id if conv.owner_id == db_user.id else conv.owner_id
            mod_repo = ModerationRepository(db_session)
            await mod_repo.create_report(
                reporter_id=db_user.id,
                reported_user_id=reported_user_id,
                reason=reason,
                conversation_id=conv.id,
            )

    await state.clear()
    await message.answer(
        get_text("report_submitted"),
        reply_markup=get_main_menu_inline_keyboard(is_admin=db_user.is_admin),
    )
