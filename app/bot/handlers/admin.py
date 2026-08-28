"""Handlers for system administration and moderation dashboard."""

from aiogram import Router, types, F, Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.messages import get_text
from app.config.settings import settings
from app.database.models import User
from app.bot.keyboards.inline import get_admin_panel_keyboard, get_main_menu_inline_keyboard
from app.services.moderation.admin_service import AdminService

router = Router(name="admin_router")


@router.callback_query(F.data == "admin:dashboard")
async def handle_admin_dashboard(call: types.CallbackQuery, db_user: User):
    """Admin dashboard landing view."""
    if not (db_user.is_admin or call.from_user.id in settings.admin_ids):
        await call.answer("دسترسی غیرمجاز.", show_alert=True)
        return

    kb = get_admin_panel_keyboard()
    await call.message.edit_text(get_text("admin_welcome"), reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "admin:stats")
async def handle_admin_stats(
    call: types.CallbackQuery, db_session: AsyncSession, db_user: User, bot: Bot
):
    """Display real-time aggregated platform statistics."""
    if not (db_user.is_admin or call.from_user.id in settings.admin_ids):
        await call.answer("دسترسی غیرمجاز.", show_alert=True)
        return

    admin_service = AdminService(db_session, bot)
    stats = await admin_service.get_system_stats()

    text = get_text(
        "admin_stats",
        users_count=stats["users_count"],
        active_convs=stats["active_convs"],
        messages_count=stats["messages_count"],
        channels_count=stats["channels_count"],
        seen_count=stats["seen_count"],
        pending_reports=stats["pending_reports"],
    )
    kb = types.InlineKeyboardMarkup(
        inline_keyboard=[
            [types.InlineKeyboardButton(text="🔄 بروزرسانی", callback_data="admin:stats")],
            [types.InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:dashboard")],
        ]
    )
    try:
        await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass
    await call.answer()
