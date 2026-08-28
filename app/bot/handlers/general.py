"""General commands and navigation handlers (/start, /help, main menu)."""

from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.messages import get_text
from app.database.models import User
from app.bot.keyboards.inline import (
    get_main_menu_inline_keyboard,
    get_personal_link_management_keyboard,
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
