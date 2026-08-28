"""Handlers for user nickname configuration."""

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.messages import get_text
from app.config.settings import settings
from app.database.models import User
from app.database.repositories import UserRepository
from app.bot.keyboards.inline import get_cancel_inline_keyboard, get_main_menu_inline_keyboard
from app.bot.states.fsm import PersonalChatStates
from app.security.tokens import sanitize_nickname

router = Router(name="nicknames_router")


@router.callback_query(F.data == "nav:nickname")
async def handle_view_nickname(
    call: types.CallbackQuery, db_session: AsyncSession, db_user: User
):
    """View and manage anonymous nickname."""
    user_repo = UserRepository(db_session)
    user = await user_repo.get_by_id(db_user.id)
    current_nick = user.anonymous_profile.nickname if user and user.anonymous_profile and user.anonymous_profile.nickname else "تنظیم نشده"

    kb_buttons = [
        [types.InlineKeyboardButton(text=get_text("btn_set_nickname"), callback_data="nick:set")],
    ]
    if user and user.anonymous_profile and user.anonymous_profile.nickname:
        kb_buttons[0].append(
            types.InlineKeyboardButton(text=get_text("btn_remove_nickname"), callback_data="nick:remove")
        )
    kb_buttons.append([types.InlineKeyboardButton(text=get_text("btn_back"), callback_data="nav:main")])

    kb = types.InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await call.message.edit_text(
        get_text("nickname_info", nickname=current_nick),
        reply_markup=kb,
        parse_mode="HTML",
    )
    await call.answer()


@router.callback_query(F.data == "nick:set")
async def handle_prompt_nickname(call: types.CallbackQuery, state: FSMContext):
    """Prompt user for nickname input."""
    await state.set_state(PersonalChatStates.setting_nickname)
    await call.message.edit_text(
        get_text("prompt_nickname", max=settings.max_nickname_length),
        reply_markup=get_cancel_inline_keyboard(),
    )
    await call.answer()


@router.message(PersonalChatStates.setting_nickname, F.text)
async def handle_process_nickname(
    message: types.Message, db_session: AsyncSession, db_user: User, state: FSMContext
):
    """Sanitize, validate, and store nickname."""
    raw_nick = message.text.strip()
    sanitized = sanitize_nickname(raw_nick)

    if not sanitized:
        await message.answer(
            get_text("nickname_invalid"), reply_markup=get_cancel_inline_keyboard()
        )
        return

    user_repo = UserRepository(db_session)
    user = await user_repo.get_by_id(db_user.id)
    if user and user.anonymous_profile:
        user.anonymous_profile.nickname = sanitized
        await db_session.flush()

    await state.clear()
    await message.answer(
        get_text("nickname_updated", nickname=sanitized),
        reply_markup=get_main_menu_inline_keyboard(is_admin=db_user.is_admin),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "nick:remove")
async def handle_remove_nickname(
    call: types.CallbackQuery, db_session: AsyncSession, db_user: User
):
    """Remove user's anonymous nickname."""
    user_repo = UserRepository(db_session)
    user = await user_repo.get_by_id(db_user.id)
    if user and user.anonymous_profile:
        user.anonymous_profile.nickname = None
        await db_session.flush()

    await call.message.edit_text(
        get_text("nickname_removed"),
        reply_markup=get_main_menu_inline_keyboard(is_admin=db_user.is_admin),
    )
    await call.answer()
