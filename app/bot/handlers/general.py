"""General commands and navigation handlers (/start, /help, main menu)."""

import uuid
from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.messages import get_text
from app.database.models import User
from app.bot.keyboards.inline import (
    get_main_menu_inline_keyboard,
    get_cancel_inline_keyboard,
    get_settings_keyboard,
)
from app.services.links.link_service import LinkService
from app.bot.states.fsm import PersonalChatStates, ChannelPublishStates

router = Router(name="general_router")


@router.message(CommandStart())
async def handle_start_command(
    message: types.Message,
    command: CommandObject,
    db_session: AsyncSession,
    db_user: User,
    state: FSMContext,
):
    """Handle /start command with optional deep link argument."""
    await state.clear()
    payload = command.args

    if not payload:
        # Default start command: Show welcome message & main menu
        kb = get_main_menu_inline_keyboard(is_admin=db_user.is_admin)
        await message.answer(
            get_text("welcome", name=message.from_user.first_name),
            reply_markup=kb,
        )
        return

    # Deep link processing
    link_service = LinkService(db_session)
    mode, personal_link, channel = await link_service.resolve_start_payload(payload)

    if mode == "personal" and personal_link:
        if personal_link.owner_id == db_user.id:
            await message.answer(get_text("cannot_message_self"))
            return
        if not personal_link.is_active:
            await message.answer(get_text("recipient_link_disabled"))
            return

        # Start 1-to-1 anonymous chat
        await state.set_state(PersonalChatStates.waiting_for_message)
        await state.update_data(
            target_owner_id=str(personal_link.owner_id),
            link_id=str(personal_link.id),
        )
        await message.answer(
            get_text("sender_chat_opened"),
        )
        return

    elif mode == "channel" and channel:
        if not channel.is_active:
            await message.answer(get_text("channel_submission_disabled"))
            return

        # Start anonymous channel submission
        await state.set_state(ChannelPublishStates.waiting_for_channel_post)
        await state.update_data(target_channel_id=str(channel.id))
        await message.answer(
            get_text("channel_submission_opened", channel_title=channel.title),
        )
        return

    # Invalid start parameter
    await message.answer(
        "❌ لینک مورد نظر نامعتبر است یا منقضی شده است.",
        reply_markup=get_main_menu_inline_keyboard(is_admin=db_user.is_admin),
    )


@router.message(Command("help"))
async def handle_help_command(message: types.Message, db_user: User):
    """Display bot help."""
    await message.answer(
        get_text("help"),
        reply_markup=get_main_menu_inline_keyboard(is_admin=db_user.is_admin),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "nav:main")
async def handle_nav_main(call: types.CallbackQuery, db_user: User, state: FSMContext):
    """Navigate back to main menu."""
    await state.clear()
    kb = get_main_menu_inline_keyboard(is_admin=db_user.is_admin)
    try:
        await call.message.edit_text(get_text("main_menu"), reply_markup=kb)
    except Exception:
        await call.message.answer(get_text("main_menu"), reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "nav:help")
async def handle_nav_help(call: types.CallbackQuery, db_user: User):
    """Help button callback."""
    kb = get_main_menu_inline_keyboard(is_admin=db_user.is_admin)
    try:
        await call.message.edit_text(get_text("help"), reply_markup=kb, parse_mode="HTML")
    except Exception:
        await call.message.answer(get_text("help"), reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "nav:settings")
async def handle_nav_settings(call: types.CallbackQuery, db_user: User):
    """Settings menu callback."""
    kb = get_settings_keyboard()
    settings_text = (
        "⚙️ <b>تنظیمات حساب و ربات:</b>\n\n"
        "از گزینه‌های زیر بخش مورد نظر خود را برای ویرایش یا مدیریت انتخاب کنید:"
    )
    try:
        await call.message.edit_text(settings_text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await call.message.answer(settings_text, reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "nav:blocked_list")
async def handle_view_blocked_list(call: types.CallbackQuery, db_session: AsyncSession, db_user: User):
    """Display list of blocked anonymous users with pseudonymized IDs."""
    from app.database.repositories import ModerationRepository
    from app.security.tokens import generate_opaque_user_id

    mod_repo = ModerationRepository(db_session)
    blocked_list = await mod_repo.get_blocked_users_by_blocker(db_user.id)

    if not blocked_list:
        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text=get_text("btn_back"), callback_data="nav:settings")]
            ]
        )
        await call.message.edit_text(
            "🚫 <b>لیست کاربران مسدود شده:</b>\n\nشما در حال حاضر هیچ کاربری را مسدود نکرده‌اید.",
            reply_markup=kb,
            parse_mode="HTML",
        )
        await call.answer()
        return

    buttons = []
    for b in blocked_list:
        opaque_id = generate_opaque_user_id(str(b.blocked_id))
        buttons.append(
            [
                types.InlineKeyboardButton(text=f"👤 {opaque_id}", callback_data="noop"),
                types.InlineKeyboardButton(
                    text="🔓 رفع انسداد",
                    callback_data=f"unblock:user:{b.blocked_id}",
                ),
            ]
        )

    buttons.append([types.InlineKeyboardButton(text=get_text("btn_back"), callback_data="nav:settings")])
    kb = types.InlineKeyboardMarkup(inline_keyboard=buttons)

    await call.message.edit_text(
        "🚫 <b>لیست کاربران مسدود شده:</b>\n\n"
        "در زیر شناسه‌های رمزنگاری‌شده کاربرانی که مسدود کرده‌اید را مشاهده می‌کنید. "
        "برای رفع انسداد روی دکمه مربوطه کلیک کنید:",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data.startswith("unblock:user:"))
async def handle_unblock_user_callback(call: types.CallbackQuery, db_session: AsyncSession, db_user: User):
    """Unblock a user by UUID."""
    from app.database.repositories import ModerationRepository
    from app.security.tokens import generate_opaque_user_id

    blocked_id_str = call.data.split(":")[2]
    blocked_uuid = uuid.UUID(blocked_id_str)

    mod_repo = ModerationRepository(db_session)
    await mod_repo.unblock_user(blocker_id=db_user.id, blocked_id=blocked_uuid)

    await call.answer("کاربر با موفقیت رفع انسداد شد.", show_alert=True)

    # Refresh list
    blocked_list = await mod_repo.get_blocked_users_by_blocker(db_user.id)
    if not blocked_list:
        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text=get_text("btn_back"), callback_data="nav:settings")]
            ]
        )
        await call.message.edit_text(
            "🚫 <b>لیست کاربران مسدود شده:</b>\n\nشما در حال حاضر هیچ کاربری را مسدود نکرده‌اید.",
            reply_markup=kb,
            parse_mode="HTML",
        )
        return

    buttons = []
    for b in blocked_list:
        opaque_id = generate_opaque_user_id(str(b.blocked_id))
        buttons.append(
            [
                types.InlineKeyboardButton(text=f"👤 {opaque_id}", callback_data="noop"),
                types.InlineKeyboardButton(
                    text="🔓 رفع انسداد",
                    callback_data=f"unblock:user:{b.blocked_id}",
                ),
            ]
        )

    buttons.append([types.InlineKeyboardButton(text=get_text("btn_back"), callback_data="nav:settings")])
    kb = types.InlineKeyboardMarkup(inline_keyboard=buttons)
    await call.message.edit_text(
        "🚫 <b>لیست کاربران مسدود شده:</b>\n\n"
        "در زیر شناسه‌های رمزنگاری‌شده کاربرانی که مسدود کرده‌اید را مشاهده می‌کنید. "
        "برای رفع انسداد روی دکمه مربوطه کلیک کنید:",
        reply_markup=kb,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "noop")
async def handle_noop_callback(call: types.CallbackQuery):
    """No-op for informative buttons."""
    await call.answer()


@router.callback_query(F.data == "action:cancel")
async def handle_action_cancel(call: types.CallbackQuery, state: FSMContext, db_user: User):
    """Cancel any active FSM input."""
    await state.clear()
    kb = get_main_menu_inline_keyboard(is_admin=db_user.is_admin)
    try:
        await call.message.edit_text(get_text("reply_mode_cancelled"), reply_markup=kb)
    except Exception:
        await call.message.answer(get_text("reply_mode_cancelled"), reply_markup=kb)
    await call.answer("عملیات لغو شد.")
