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


@router.callback_query(F.data.startswith("admin:reports"))
async def handle_admin_reports_list(
    call: types.CallbackQuery, db_session: AsyncSession, db_user: User
):
    """Display unresolved reports in admin panel."""
    if not (db_user.is_admin or call.from_user.id in settings.admin_ids):
        await call.answer("دسترسی غیرمجاز.", show_alert=True)
        return

    admin_service = AdminService(db_session, call.bot)
    reports = await admin_service.get_pending_reports(limit=10)

    if not reports:
        kb = types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:dashboard")]
            ]
        )
        await call.message.edit_text("🚨 <b>گزارش‌های ثبت‌شده:</b>\n\nهیچ گزارش بررسی‌نشده‌ای وجود ندارد.", reply_markup=kb, parse_mode="HTML")
        await call.answer()
        return

    from app.security.tokens import generate_opaque_user_id

    buttons = []
    text_lines = ["🚨 <b>لیست گزارش‌های در انتظار بررسی:</b>\n"]

    for idx, r in enumerate(reports, 1):
        reporter_label = generate_opaque_user_id(str(r.reporter_id))
        reported_label = generate_opaque_user_id(str(r.reported_user_id))
        text_lines.append(
            f"<b>{idx}. گزارش #{str(r.id)[:6]}</b>\n"
            f"👤 شاکی: <code>{reporter_label}</code>\n"
            f"🚫 متخلف: <code>{reported_label}</code>\n"
            f"📝 دلیل: {r.reason}\n"
            f"🕒 تاریخ: <code>{r.created_at.strftime('%Y-%m-%d %H:%M')}</code>\n"
        )
        buttons.append([
            types.InlineKeyboardButton(text=f"🚫 مسدودسازی #{str(r.id)[:6]}", callback_data=f"admin:ban_report:{r.id}"),
            types.InlineKeyboardButton(text=f"✅ رد گزارش", callback_data=f"admin:dismiss_report:{r.id}"),
        ])

    buttons.append([types.InlineKeyboardButton(text="🔙 بازگشت", callback_data="admin:dashboard")])
    kb = types.InlineKeyboardMarkup(inline_keyboard=buttons)

    await call.message.edit_text("\n".join(text_lines), reply_markup=kb, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("admin:ban_report:"))
async def handle_admin_ban_from_report(
    call: types.CallbackQuery, db_session: AsyncSession, db_user: User
):
    """Ban reported user and resolve report."""
    if not (db_user.is_admin or call.from_user.id in settings.admin_ids):
        await call.answer("دسترسی غیرمجاز.", show_alert=True)
        return

    import uuid
    from app.database.repositories import ModerationRepository, UserRepository
    from app.database.models import ReportStatus

    report_id_str = call.data.split(":")[2]
    report_id = uuid.UUID(report_id_str)

    mod_repo = ModerationRepository(db_session)
    user_repo = UserRepository(db_session)

    report = await mod_repo.get_report_by_id(report_id)
    if not report:
        await call.answer("گزارش یافت نشد.", show_alert=True)
        return

    # Ban reported user globally
    await user_repo.set_global_ban(user_id=report.reported_user_id, is_banned=True, reason=f"Report #{str(report.id)[:6]}: {report.reason}")
    await mod_repo.resolve_report(report_id=report.id, status=ReportStatus.RESOLVED, moderator_notes="Banned by admin")

    await call.answer("کاربر متخلف مسدود شد و گزارش بسته شد.", show_alert=True)

    # Refresh reports
    await handle_admin_reports_list(call, db_session, db_user)


@router.callback_query(F.data.startswith("admin:dismiss_report:"))
async def handle_admin_dismiss_report(
    call: types.CallbackQuery, db_session: AsyncSession, db_user: User
):
    """Dismiss report without banning user."""
    if not (db_user.is_admin or call.from_user.id in settings.admin_ids):
        await call.answer("دسترسی غیرمجاز.", show_alert=True)
        return

    import uuid
    from app.database.repositories import ModerationRepository
    from app.database.models import ReportStatus

    report_id_str = call.data.split(":")[2]
    report_id = uuid.UUID(report_id_str)

    mod_repo = ModerationRepository(db_session)
    report = await mod_repo.get_report_by_id(report_id)
    if not report:
        await call.answer("گزارش یافت نشد.", show_alert=True)
        return

    await mod_repo.resolve_report(report_id=report.id, status=ReportStatus.REJECTED, moderator_notes="Dismissed by admin")

    await call.answer("گزارش رد شد.", show_alert=True)

    # Refresh reports
    await handle_admin_reports_list(call, db_session, db_user)
