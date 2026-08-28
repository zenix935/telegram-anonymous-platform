"""Handlers for personal anonymous link management (view, toggle, regenerate, custom slug)."""

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.messages import get_text
from app.config.settings import settings
from app.database.models import User
from app.bot.keyboards.inline import (
    get_personal_link_management_keyboard,
    get_cancel_inline_keyboard,
)
from app.bot.states.fsm import PersonalChatStates
from app.services.links.link_service import LinkService

router = Router(name="personal_links_router")


async def render_personal_link_view(
    target_message: types.Message,
    db_session: AsyncSession,
    db_user: User,
    is_edit: bool = True,
):
    """Helper to render personal link view UI."""
    link_service = LinkService(db_session)
    link = await link_service.get_or_create_personal_link(db_user.id)

    identifier = link.custom_slug or link.random_token
    full_url = link_service.format_personal_url(identifier)
    status_text = (
        get_text("link_status_active") if link.is_active else get_text("link_status_disabled")
    )
    slug_text = link.custom_slug or "تنظیم نشده"

    text = get_text(
        "personal_link_info",
        link=full_url,
        status=status_text,
        slug=slug_text,
    )
    kb = get_personal_link_management_keyboard(
        is_active=link.is_active, has_slug=bool(link.custom_slug)
    )

    if is_edit:
        try:
            await target_message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            return
        except Exception:
            pass
    await target_message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "nav:my_link")
async def handle_view_my_link(
    call: types.CallbackQuery, db_session: AsyncSession, db_user: User
):
    """Display user's personal anonymous link."""
    await render_personal_link_view(call.message, db_session, db_user, is_edit=True)
    await call.answer()


@router.callback_query(F.data.startswith("link:toggle:"))
async def handle_toggle_link(
    call: types.CallbackQuery, db_session: AsyncSession, db_user: User
):
    """Enable or disable receiving personal anonymous messages."""
    action = call.data.split(":")[2]
    is_active = action == "enable"

    link_service = LinkService(db_session)
    await link_service.toggle_personal_link(db_user.id, is_active=is_active)

    await render_personal_link_view(call.message, db_session, db_user, is_edit=True)
    status_label = (
        get_text("link_status_active") if is_active else get_text("link_status_disabled")
    )
    await call.answer(get_text("link_status_changed", status=status_label))


@router.callback_query(F.data == "link:regenerate")
async def handle_regenerate_link(
    call: types.CallbackQuery, db_session: AsyncSession, db_user: User
):
    """Regenerate random token for personal anonymous link."""
    link_service = LinkService(db_session)
    await link_service.regenerate_personal_link(db_user.id)

    await render_personal_link_view(call.message, db_session, db_user, is_edit=True)
    await call.answer("توکن لینک شما با موفقیت بازتولید شد.")


@router.callback_query(F.data == "link:set_slug")
async def handle_prompt_set_slug(call: types.CallbackQuery, state: FSMContext):
    """Prompt user to enter custom slug."""
    await state.set_state(PersonalChatStates.setting_custom_slug)
    await call.message.edit_text(
        get_text("prompt_custom_slug", min=settings.slug_min_length, max=settings.slug_max_length),
        reply_markup=get_cancel_inline_keyboard(),
    )
    await call.answer()


@router.message(PersonalChatStates.setting_custom_slug, F.text)
async def handle_process_set_slug(
    message: types.Message, db_session: AsyncSession, db_user: User, state: FSMContext
):
    """Validate and persist new custom slug."""
    slug_input = message.text.strip()
    link_service = LinkService(db_session)

    success, err_code, link = await link_service.set_personal_custom_slug(
        db_user.id, slug_input
    )
    if not success:
        if err_code == "taken":
            await message.answer(
                get_text("slug_taken"),
                reply_markup=get_cancel_inline_keyboard(),
            )
        else:
            await message.answer(
                get_text("slug_invalid", min=settings.slug_min_length, max=settings.slug_max_length),
                reply_markup=get_cancel_inline_keyboard(),
            )
        return

    await state.clear()
    await message.answer("✅ اسلاگ اختصاصی شما با موفقیت تنظیم شد!")
    await render_personal_link_view(message, db_session, db_user, is_edit=False)


@router.callback_query(F.data == "link:remove_slug")
async def handle_remove_slug(
    call: types.CallbackQuery, db_session: AsyncSession, db_user: User
):
    """Remove custom slug."""
    link_service = LinkService(db_session)
    await link_service.remove_personal_custom_slug(db_user.id)
    await render_personal_link_view(call.message, db_session, db_user, is_edit=True)
    await call.answer("اسلاگ اختصاصی حذف گردید.")
