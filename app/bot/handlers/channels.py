"""Handlers for anonymous channel submission, Seen button clicks, and channel management."""

import uuid
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.messages import get_text
from app.database.models import User
from app.database.repositories import (
    ChannelRepository,
    UserRepository,
)
from app.bot.keyboards.inline import (
    get_cancel_inline_keyboard,
    get_main_menu_inline_keyboard,
)
from app.bot.states.fsm import ChannelPublishStates
from app.security.tokens import generate_secure_token, validate_custom_slug
from app.services.channel_publishing.publishing_service import ChannelPublishingService
from app.services.channel_publishing.seen_service import SeenService
from app.services.links.link_service import LinkService
from app.services.moderation.content_filter import ContentFilterService
from app.services.moderation.rate_limiter import RateLimitService
from app.utils.redis import get_redis_pool

router = Router(name="channel_publishing_router")


# --- 1. CHANNEL SUBMISSION (ANONYMOUS AUTHOR) ---


@router.message(ChannelPublishStates.waiting_for_channel_post)
async def handle_submitting_channel_post(
    message: types.Message,
    db_session: AsyncSession,
    db_user: User,
    bot: Bot,
    state: FSMContext,
):
    """Publish user's submitted content to the associated channel."""
    state_data = await state.get_data()
    channel_id_str = state_data.get("target_channel_id")

    if not channel_id_str:
        await state.clear()
        await message.answer(get_text("generic_error"))
        return

    channel_id = uuid.UUID(channel_id_str)
    channel_repo = ChannelRepository(db_session)
    channel = await channel_repo.get_by_id(channel_id)

    if not channel or not channel.is_active:
        await state.clear()
        await message.answer(get_text("channel_submission_disabled"))
        return

    # Content filter & anti-spam
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

    # Extract media
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

    # Retrieve author nickname if available
    user_repo = UserRepository(db_session)
    profile_user = await user_repo.get_by_id(db_user.id)
    nickname = profile_user.anonymous_profile.nickname if profile_user and profile_user.anonymous_profile else None

    pub_service = ChannelPublishingService(db_session, bot)
    success, db_msg, err = await pub_service.publish_anonymous_message(
        channel=channel,
        author_id=db_user.id,
        content_type=content_type,
        text_content=message.text or message.caption,
        media_file_id=media_file_id,
        nickname=nickname,
    )

    if success:
        await message.answer(
            get_text("channel_post_published_success"),
            reply_markup=get_main_menu_inline_keyboard(is_admin=db_user.is_admin),
        )
        await state.clear()
    else:
        await message.answer(get_text("channel_submission_failed"))


# --- 2. SEEN BUTTON CLICK (IDEMPOTENT EVENT) ---


@router.callback_query(F.data.startswith("seen:"))
async def handle_seen_button_click(
    call: types.CallbackQuery, db_session: AsyncSession, bot: Bot
):
    """Handle explicit 'Seen' button click on channel post."""
    parts = call.data.split(":")
    channel_id_str = parts[1]
    post_message_id = int(parts[2])

    seen_service = SeenService(db_session, bot)
    success, result_key = await seen_service.process_seen_click(
        channel_id_str=channel_id_str,
        telegram_post_id=post_message_id,
        viewer_telegram_id=call.from_user.id,
    )

    if success:
        await call.answer(get_text("seen_recorded"), show_alert=False)
    else:
        await call.answer(get_text(result_key), show_alert=False)


# --- 3. CHANNEL CONNECTION & MANAGEMENT FOR ADMINS ---


@router.callback_query(F.data == "nav:channels")
async def handle_list_managed_channels(
    call: types.CallbackQuery, db_session: AsyncSession, db_user: User
):
    """List connected channels managed by this user."""
    channel_repo = ChannelRepository(db_session)
    channels = await channel_repo.get_user_channels(db_user.id)

    if not channels:
        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➕ راهنمای اتصال کانال جدید",
                        callback_data="channel:connect_guide",
                    )
                ],
                [InlineKeyboardButton(text=get_text("btn_back"), callback_data="nav:main")],
            ]
        )
        await call.message.edit_text(
            "📢 شما هنوز هیچ کانالی متصل نکرده‌اید.\n\nبرای اتصال کانال، ربات را به عنوان ادمین در کانال خود اضافه کنید.",
            reply_markup=kb,
        )
        await call.answer()
        return

    link_service = LinkService(db_session)
    buttons = []
    for ch in channels:
        ident = ch.channel_link.custom_slug or ch.channel_link.random_token if ch.channel_link else ""
        link_url = link_service.format_channel_url(ident)
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"📢 {ch.title}", callback_data=f"channel:view:{ch.id}"
                )
            ]
        )

    buttons.append(
        [InlineKeyboardButton(text="➕ راهنمای اتصال کانال جدید", callback_data="channel:connect_guide")]
    )
    buttons.append(
        [InlineKeyboardButton(text=get_text("btn_back"), callback_data="nav:main")]
    )

    kb = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await call.message.edit_text("📢 <b>کانال‌های متصل شما:</b>", reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "channel:connect_guide")
async def handle_channel_connect_guide(call: types.CallbackQuery):
    """Display channel setup instructions."""
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text("btn_back"), callback_data="nav:channels")]
        ]
    )
    await call.message.edit_text(
        get_text("channel_connect_instructions"), reply_markup=kb, parse_mode="HTML"
    )
    await call.answer()


# Import InlineKeyboardButton for local keyboard creation
from aiogram.types import InlineKeyboardButton
