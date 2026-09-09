"""Handlers for anonymous channel submission, Seen button clicks, and channel management."""

import uuid
from typing import Optional
from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.messages import get_text
from app.config.settings import settings
from app.database.models import User
from app.database.repositories import (
    ChannelRepository,
    ModerationRepository,
    PersonalLinkRepository,
    UserRepository,
)
from app.bot.keyboards.inline import (
    get_cancel_inline_keyboard,
    get_main_menu_inline_keyboard,
    get_channel_management_keyboard,
)
from app.bot.states.fsm import ChannelPublishStates, PersonalChatStates
from app.security.tokens import generate_secure_token, validate_custom_slug
from app.services.channel_publishing.publishing_service import ChannelPublishingService
from app.services.channel_publishing.seen_service import SeenService
from app.services.links.link_service import LinkService
from app.services.moderation.content_filter import ContentFilterService
from app.services.moderation.rate_limiter import RateLimitService
from app.utils.redis import get_redis_pool

router = Router(name="channel_publishing_router")


def extract_personal_token_or_slug(raw_text: str) -> Optional[str]:
    """Extract token or slug from shared personal link or payload."""
    raw = raw_text.strip()
    if "start=" in raw:
        payload = raw.split("start=")[-1].split("&")[0].split(" ")[0].strip()
    elif raw.startswith("/start"):
        parts = raw.split()
        payload = parts[1].strip() if len(parts) > 1 else ""
    else:
        payload = raw

    if payload.startswith("p_"):
        return payload[2:]
    return payload if payload else None


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
async def handle_channel_connect_guide(call: types.CallbackQuery, state: FSMContext):
    """Display channel setup instructions."""
    await state.set_state(ChannelPublishStates.waiting_for_channel_forward)
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text("btn_back"), callback_data="nav:channels")]
        ]
    )
    await call.message.edit_text(
        get_text("channel_connect_instructions"), reply_markup=kb, parse_mode="HTML"
    )
    await call.answer()


@router.message(ChannelPublishStates.waiting_for_channel_forward)
@router.message(F.forward_origin | F.forward_from_chat)
async def handle_channel_connect_message(
    message: types.Message,
    db_session: AsyncSession,
    db_user: User,
    bot: Bot,
    state: FSMContext,
):
    """Process forwarded channel post or channel ID/username to connect channel."""
    channel_tg_id = None
    channel_title = None
    channel_username = None

    # 1. Check forward_origin (Telegram modern format)
    if message.forward_origin:
        origin = message.forward_origin
        if origin.type == "channel":
            channel_tg_id = origin.chat.id
            channel_title = origin.chat.title
            channel_username = origin.chat.username

    # 2. Check forward_from_chat (Legacy format)
    elif message.forward_from_chat:
        if message.forward_from_chat.type == "channel":
            channel_tg_id = message.forward_from_chat.id
            channel_title = message.forward_from_chat.title
            channel_username = message.forward_from_chat.username

    # 3. Check plain text (ID or @username)
    elif message.text:
        text = message.text.strip()
        try:
            chat_obj = await bot.get_chat(text)
            if chat_obj.type == "channel":
                channel_tg_id = chat_obj.id
                channel_title = chat_obj.title
                channel_username = chat_obj.username
        except Exception:
            pass

    if not channel_tg_id:
        return

    # Verify bot permissions in the channel
    try:
        bot_member = await bot.get_chat_member(chat_id=channel_tg_id, user_id=bot.id)
        if bot_member.status not in ["administrator", "creator"]:
            await message.answer(get_text("channel_permission_error"))
            return
        if bot_member.status == "administrator" and not getattr(bot_member, "can_post_messages", True):
            await message.answer(get_text("channel_permission_error"))
            return
    except Exception as e:
        await message.answer(get_text("channel_permission_error"))
        return

    # Verify user permissions in the channel
    try:
        user_member = await bot.get_chat_member(chat_id=channel_tg_id, user_id=message.from_user.id)
        if user_member.status not in ["administrator", "creator"]:
            await message.answer(get_text("not_channel_admin"))
            return
    except Exception as e:
        await message.answer(get_text("not_channel_admin"))
        return

    channel_repo = ChannelRepository(db_session)
    existing_channel = await channel_repo.get_by_telegram_id(channel_tg_id)

    link_service = LinkService(db_session)
    if existing_channel:
        is_admin = await channel_repo.is_user_channel_admin(existing_channel.id, db_user.id)
        if not is_admin:
            # Register user as admin
            from app.database.models import ChannelAdmin
            db_session.add(ChannelAdmin(channel_id=existing_channel.id, user_id=db_user.id, role="admin"))
            await db_session.flush()

        ident = (
            existing_channel.channel_link.custom_slug or existing_channel.channel_link.random_token
            if existing_channel.channel_link
            else ""
        )
        url = link_service.format_channel_url(ident)
        await state.clear()
        await message.answer(
            get_text("channel_connected_success", channel_title=existing_channel.title, link=url),
            parse_mode="HTML",
            reply_markup=get_main_menu_inline_keyboard(is_admin=db_user.is_admin),
        )
        return

    # Create new channel connection
    random_token = generate_secure_token(prefix="", entropy_bytes=16)
    new_channel = await channel_repo.create_channel(
        telegram_channel_id=channel_tg_id,
        title=channel_title or "کانال بدون عنوان",
        admin_user_id=db_user.id,
        username=channel_username,
        random_token=random_token,
    )

    url = link_service.format_channel_url(random_token)
    await state.clear()
    await message.answer(
        get_text("channel_connected_success", channel_title=new_channel.title, link=url),
        parse_mode="HTML",
        reply_markup=get_main_menu_inline_keyboard(is_admin=db_user.is_admin),
    )


async def render_channel_management_view(
    channel, db_session: AsyncSession
) -> tuple[str, InlineKeyboardMarkup]:
    """Helper to render channel management text and keyboard."""
    link_service = LinkService(db_session)
    ident = channel.channel_link.custom_slug or channel.channel_link.random_token if channel.channel_link else ""
    url = link_service.format_channel_url(ident)
    status_text = get_text("link_status_active") if channel.is_active else get_text("link_status_disabled")

    channel_repo = ChannelRepository(db_session)
    inboxes = await channel_repo.get_channel_inboxes(channel.id)
    inbox_info = ""
    if inboxes:
        inbox_info = "\n\n📥 <b>صندوق‌های متصل:</b>\n" + "\n".join([f"▫️ {ib.name}" for ib in inboxes])

    text = (
        get_text(
            "channel_admin_title",
            channel_title=channel.title,
            link=url,
            status=status_text,
            template=channel.post_template,
        )
        + inbox_info
    )
    kb = get_channel_management_keyboard(
        channel_id=str(channel.id),
        is_active=channel.is_active,
        has_slug=bool(channel.channel_link and channel.channel_link.custom_slug),
        inboxes_count=len(inboxes),
    )
    return text, kb


@router.callback_query(F.data.startswith("channel:view:"))
async def handle_channel_view(
    call: types.CallbackQuery, db_session: AsyncSession, db_user: User, state: FSMContext
):
    """View details and options of a managed channel."""
    await state.clear()
    channel_id_str = call.data.split(":")[2]
    channel_id = uuid.UUID(channel_id_str)
    channel_repo = ChannelRepository(db_session)
    channel = await channel_repo.get_by_id(channel_id)

    if not channel:
        await call.answer("کانال یافت نشد.", show_alert=True)
        return

    is_admin = await channel_repo.is_user_channel_admin(channel.id, db_user.id)
    if not is_admin:
        await call.answer(get_text("not_channel_admin"), show_alert=True)
        return

    text, kb = await render_channel_management_view(channel, db_session)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("ch_manage:toggle:"))
async def handle_channel_toggle(call: types.CallbackQuery, db_session: AsyncSession, db_user: User):
    """Toggle channel submission active status."""
    channel_id_str = call.data.split(":")[2]
    channel_id = uuid.UUID(channel_id_str)
    channel_repo = ChannelRepository(db_session)
    channel = await channel_repo.get_by_id(channel_id)

    if not channel:
        await call.answer("کانال یافت نشد.", show_alert=True)
        return

    channel.is_active = not channel.is_active
    await db_session.flush()

    status_label = get_text("link_status_active") if channel.is_active else get_text("link_status_disabled")
    await call.answer(get_text("link_status_changed", status=status_label))

    text, kb = await render_channel_management_view(channel, db_session)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("ch_manage:regen:"))
async def handle_channel_regen_token(call: types.CallbackQuery, db_session: AsyncSession, db_user: User):
    """Regenerate random token for channel link."""
    channel_id_str = call.data.split(":")[2]
    channel_id = uuid.UUID(channel_id_str)
    channel_repo = ChannelRepository(db_session)
    channel = await channel_repo.get_by_id(channel_id)

    if not channel or not channel.channel_link:
        await call.answer("کانال یافت نشد.", show_alert=True)
        return

    channel.channel_link.random_token = generate_secure_token(prefix="", entropy_bytes=16)
    await db_session.flush()

    await call.answer("توکن لینک کانال با موفقیت بازتولید شد.")
    text, kb = await render_channel_management_view(channel, db_session)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("ch_manage:remove_slug:"))
async def handle_channel_remove_slug(call: types.CallbackQuery, db_session: AsyncSession, db_user: User):
    """Remove custom slug from channel link."""
    channel_id_str = call.data.split(":")[2]
    channel_id = uuid.UUID(channel_id_str)
    channel_repo = ChannelRepository(db_session)
    channel = await channel_repo.get_by_id(channel_id)

    if not channel or not channel.channel_link:
        await call.answer("کانال یافت نشد.", show_alert=True)
        return

    channel.channel_link.custom_slug = None
    await db_session.flush()

    await call.answer("اسلاگ اختصاصی کانال حذف شد.")
    text, kb = await render_channel_management_view(channel, db_session)
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("ch_manage:set_slug:"))
async def handle_channel_prompt_slug(call: types.CallbackQuery, state: FSMContext):
    """Prompt user for channel custom slug."""
    channel_id_str = call.data.split(":")[2]
    await state.set_state(ChannelPublishStates.setting_channel_slug)
    await state.update_data(managing_channel_id=channel_id_str)
    await call.message.edit_text(
        "لطفاً اسلاگ (شناسه دلخواه) مورد نظر خود را برای این کانال ارسال کنید:",
        reply_markup=get_cancel_inline_keyboard(),
    )
    await call.answer()


@router.message(ChannelPublishStates.setting_channel_slug, F.text)
async def handle_channel_save_slug(
    message: types.Message, db_session: AsyncSession, db_user: User, state: FSMContext
):
    """Save custom slug for channel link."""
    data = await state.get_data()
    channel_id_str = data.get("managing_channel_id")
    if not channel_id_str:
        await state.clear()
        return

    slug = message.text.strip().lower()
    is_valid, err = validate_custom_slug(slug)
    if not is_valid:
        await message.answer(get_text("slug_invalid", min=3, max=32))
        return

    channel_id = uuid.UUID(channel_id_str)
    channel_repo = ChannelRepository(db_session)
    channel = await channel_repo.get_by_id(channel_id)

    if not channel or not channel.channel_link:
        await state.clear()
        return

    if await channel_repo.is_slug_taken(slug, exclude_link_id=channel.channel_link.id):
        await message.answer(get_text("slug_taken"))
        return

    channel.channel_link.custom_slug = slug
    await db_session.flush()

    link_service = LinkService(db_session)
    url = link_service.format_channel_url(slug)
    await state.clear()
    await message.answer(
        get_text("slug_updated_success", link=url),
        parse_mode="HTML",
        reply_markup=get_main_menu_inline_keyboard(is_admin=db_user.is_admin),
    )


# --- 4. CHANNEL SUB-INBOX MANAGEMENT & ROUTING ---


@router.callback_query(F.data.startswith("ch_inbox:add:"))
async def handle_add_channel_inbox_prompt(
    call: types.CallbackQuery, db_session: AsyncSession, db_user: User, state: FSMContext
):
    """Prompt admin to add a sub-inbox to this channel."""
    channel_id_str = call.data.split(":")[2]
    channel_id = uuid.UUID(channel_id_str)
    channel_repo = ChannelRepository(db_session)

    is_admin = await channel_repo.is_user_channel_admin(channel_id, db_user.id)
    if not is_admin:
        await call.answer(get_text("not_channel_admin"), show_alert=True)
        return

    await state.set_state(ChannelPublishStates.waiting_for_inbox_name)
    await state.update_data(target_channel_id=channel_id_str)

    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text("btn_cancel"), callback_data=f"channel:view:{channel_id_str}")]
        ]
    )
    await call.message.edit_text(
        "📥 <b>اضافه کردن صندوق جدید به کانال</b>\n\n"
        "لطفاً یک <b>نام</b> برای این صندوق وارد کنید:\n"
        "(مثال: <code>پشتیبانی</code>، <code>مدیر تبلیغات</code>، <code>ارتباط با ادمین</code>)",
        reply_markup=cancel_kb,
        parse_mode="HTML",
    )
    await call.answer()


@router.message(ChannelPublishStates.waiting_for_inbox_name, F.text)
async def handle_save_inbox_name(message: types.Message, state: FSMContext):
    """Save inbox name and prompt for personal link."""
    name = message.text.strip()
    if not name or len(name) > 60:
        await message.answer("❌ نام صندوق باید بین ۱ تا ۶۰ کاراکتر باشد. لطفاً نام دیگری وارد کنید:")
        return

    data = await state.get_data()
    channel_id_str = data.get("target_channel_id")
    if not channel_id_str:
        await state.clear()
        await message.answer(get_text("generic_error"))
        return

    await state.update_data(inbox_name=name)
    await state.set_state(ChannelPublishStates.waiting_for_inbox_link)

    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=get_text("btn_cancel"), callback_data=f"channel:view:{channel_id_str}")]
        ]
    )
    await message.answer(
        f"🔗 <b>لینک ناشناس متصل به صندوق «{name}»</b>\n\n"
        "لطفاً لینک ناشناس شخص مورد نظر را ارسال کنید (لینکی که پیام‌ها به آن هدایت شوند):\n"
        f"(مثال: <code>https://t.me/{settings.bot_username}?start=p_...</code>)",
        reply_markup=cancel_kb,
        parse_mode="HTML",
    )


@router.message(ChannelPublishStates.waiting_for_inbox_link, F.text)
async def handle_save_inbox_link(
    message: types.Message,
    db_session: AsyncSession,
    db_user: User,
    state: FSMContext,
):
    """Validate personal link and attach inbox to channel."""
    data = await state.get_data()
    channel_id_str = data.get("target_channel_id")
    inbox_name = data.get("inbox_name")

    if not channel_id_str or not inbox_name:
        await state.clear()
        await message.answer(get_text("generic_error"))
        return

    channel_id = uuid.UUID(channel_id_str)
    channel_repo = ChannelRepository(db_session)
    channel = await channel_repo.get_by_id(channel_id)
    if not channel:
        await state.clear()
        await message.answer("کانال یافت نشد.")
        return

    token = extract_personal_token_or_slug(message.text)
    personal_link = None
    if token:
        personal_repo = PersonalLinkRepository(db_session)
        personal_link = await personal_repo.get_by_token_or_slug(token)
        if not personal_link and not token.startswith("p_"):
            personal_link = await personal_repo.get_by_token_or_slug(f"p_{token}")

    if not personal_link:
        cancel_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=get_text("btn_cancel"), callback_data=f"channel:view:{channel_id_str}")]
            ]
        )
        await message.answer(
            "❌ لینک ناشناس وارد شده نامعتبر است یا کاربری با این لینک یافت نشد.\n\n"
            "لطفاً یک لینک معتبر ارسال کنید (یا دکمه انصراف را بزنید):",
            reply_markup=cancel_kb,
        )
        return

    await channel_repo.add_inbox(
        channel_id=channel.id,
        name=inbox_name,
        personal_link_id=personal_link.id,
    )
    await state.clear()

    text, kb = await render_channel_management_view(channel, db_session)
    await message.answer(
        f"✅ صندوق «<b>{inbox_name}</b>» با موفقیت به کانال «{channel.title}» متصل شد!\n\n"
        "از این پس هنگام ارسال پیام به کانال، کاربران می‌توانند این صندوق را به عنوان مقصد انتخاب کنند.",
        parse_mode="HTML",
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("ch_inbox:manage:"))
async def handle_manage_channel_inboxes(
    call: types.CallbackQuery, db_session: AsyncSession, db_user: User
):
    """View list of channel inboxes with delete options."""
    channel_id_str = call.data.split(":")[2]
    channel_id = uuid.UUID(channel_id_str)
    channel_repo = ChannelRepository(db_session)
    channel = await channel_repo.get_by_id(channel_id)

    if not channel:
        await call.answer("کانال یافت نشد.", show_alert=True)
        return

    is_admin = await channel_repo.is_user_channel_admin(channel.id, db_user.id)
    if not is_admin:
        await call.answer(get_text("not_channel_admin"), show_alert=True)
        return

    inboxes = await channel_repo.get_channel_inboxes(channel.id)
    buttons = []
    for ib in inboxes:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"🗑 حذف «{ib.name}»",
                    callback_data=f"ch_inbox:del:{ib.id}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="➕ اضافه کردن صندوق جدید",
                callback_data=f"ch_inbox:add:{channel.id}",
            )
        ]
    )
    buttons.append(
        [InlineKeyboardButton(text=get_text("btn_back"), callback_data=f"channel:view:{channel.id}")]
    )

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = (
        f"📋 <b>مدیریت صندوق‌های متصل به کانال «{channel.title}»:</b>\n\n"
        f"تعداد صندوق‌ها: {len(inboxes)}\n\n"
        "برای حذف هر صندوق روی دکمه مربوطه کلیک کنید:"
    )
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("ch_inbox:del:"))
async def handle_delete_channel_inbox(
    call: types.CallbackQuery, db_session: AsyncSession, db_user: User
):
    """Delete a sub-inbox from channel."""
    parts = call.data.split(":")
    inbox_id = uuid.UUID(parts[2])
    channel_repo = ChannelRepository(db_session)

    inbox = await channel_repo.get_inbox_by_id(inbox_id)
    if not inbox:
        await call.answer("صندوق یافت نشد.", show_alert=True)
        return

    channel_id = inbox.channel_id
    is_admin = await channel_repo.is_user_channel_admin(channel_id, db_user.id)
    if not is_admin:
        await call.answer(get_text("not_channel_admin"), show_alert=True)
        return

    name = inbox.name
    await channel_repo.delete_inbox(inbox_id)
    await call.answer(f"✅ صندوق «{name}» حذف شد.", show_alert=False)

    channel = await channel_repo.get_by_id(channel_id)
    if not channel:
        return

    inboxes = await channel_repo.get_channel_inboxes(channel_id)
    if not inboxes:
        text, kb = await render_channel_management_view(channel, db_session)
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
        return

    buttons = []
    for ib in inboxes:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"🗑 حذف «{ib.name}»",
                    callback_data=f"ch_inbox:del:{ib.id}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text="➕ اضافه کردن صندوق جدید",
                callback_data=f"ch_inbox:add:{channel.id}",
            )
        ]
    )
    buttons.append(
        [InlineKeyboardButton(text=get_text("btn_back"), callback_data=f"channel:view:{channel.id}")]
    )
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = (
        f"📋 <b>مدیریت صندوق‌های متصل به کانال «{channel.title}»:</b>\n\n"
        f"تعداد صندوق‌ها: {len(inboxes)}\n\n"
        "برای حذف هر صندوق روی دکمه مربوطه کلیک کنید:"
    )
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("ch_dest:main:"))
async def handle_select_main_channel_inbox(
    call: types.CallbackQuery, db_session: AsyncSession, state: FSMContext
):
    """User selects main channel inbox to publish directly to channel."""
    channel_id_str = call.data.split(":")[2]
    channel_id = uuid.UUID(channel_id_str)
    channel_repo = ChannelRepository(db_session)
    channel = await channel_repo.get_by_id(channel_id)

    if not channel or not channel.is_active:
        await call.answer(get_text("channel_submission_disabled"), show_alert=True)
        return

    await state.set_state(ChannelPublishStates.waiting_for_channel_post)
    await state.update_data(target_channel_id=str(channel.id))

    await call.message.edit_text(
        get_text("channel_submission_opened", channel_title=channel.title),
        reply_markup=get_cancel_inline_keyboard(),
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("ch_dest:inbox:"))
async def handle_select_custom_channel_inbox(
    call: types.CallbackQuery, db_session: AsyncSession, db_user: User, state: FSMContext
):
    """User selects custom channel inbox to message the associated personal link."""
    inbox_id_str = call.data.split(":")[2]
    channel_repo = ChannelRepository(db_session)
    inbox = await channel_repo.get_inbox_by_id(uuid.UUID(inbox_id_str))

    if not inbox or not inbox.personal_link:
        await call.answer("صندوق مورد نظر یافت نشد.", show_alert=True)
        return

    personal_link = inbox.personal_link
    if personal_link.owner_id == db_user.id:
        await call.answer("❌ شما نمی‌توانید به صندوق خودتان پیام ناشناس بفرستید!", show_alert=True)
        return

    if not personal_link.is_active:
        await call.answer("⚠️ این صندوق در حال حاضر غیرفعال است.", show_alert=True)
        return

    mod_repo = ModerationRepository(db_session)
    if await mod_repo.is_blocked(blocker_id=personal_link.owner_id, blocked_id=db_user.id):
        await call.answer("⛔ امکان ارسال پیام به این مقصد وجود ندارد.", show_alert=True)
        return

    await state.set_state(PersonalChatStates.waiting_for_message)
    await state.update_data(
        target_owner_id=str(personal_link.owner_id),
        link_id=str(personal_link.id),
    )

    await call.message.edit_text(
        get_text("sender_chat_opened", target_name=inbox.name),
        reply_markup=get_cancel_inline_keyboard(),
        parse_mode="HTML",
    )
    await call.answer()

