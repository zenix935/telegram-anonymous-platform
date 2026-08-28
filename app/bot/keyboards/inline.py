"""Inline keyboard markups."""

from typing import List, Optional
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from app.config.messages import get_text
from app.database.models import Conversation


def get_main_menu_inline_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """Generate main menu inline keyboard."""
    buttons = [
        [
            InlineKeyboardButton(
                text=get_text("btn_my_link"), callback_data="nav:my_link"
            ),
            InlineKeyboardButton(
                text=get_text("btn_inbox"), callback_data="nav:inbox:0"
            ),
        ],
        [
            InlineKeyboardButton(
                text=get_text("btn_channels"), callback_data="nav:channels"
            ),
            InlineKeyboardButton(
                text=get_text("btn_nickname"), callback_data="nav:nickname"
            ),
        ],
        [
            InlineKeyboardButton(
                text=get_text("btn_settings"), callback_data="nav:settings"
            ),
            InlineKeyboardButton(
                text=get_text("btn_help"), callback_data="nav:help"
            ),
        ],
    ]
    if is_admin:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=get_text("btn_admin_panel"), callback_data="admin:dashboard"
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_personal_link_management_keyboard(is_active: bool, has_slug: bool) -> InlineKeyboardMarkup:
    """Keyboard for managing personal anonymous link."""
    toggle_text = (
        get_text("btn_toggle_link_disable")
        if is_active
        else get_text("btn_toggle_link_enable")
    )
    toggle_action = "link:toggle:disable" if is_active else "link:toggle:enable"

    buttons = [
        [
            InlineKeyboardButton(
                text=toggle_text, callback_data=toggle_action
            ),
            InlineKeyboardButton(
                text=get_text("btn_regenerate_link"), callback_data="link:regenerate"
            ),
        ],
        [
            InlineKeyboardButton(
                text=get_text("btn_set_custom_slug"), callback_data="link:set_slug"
            ),
        ],
    ]
    if has_slug:
        buttons[1].append(
            InlineKeyboardButton(
                text=get_text("btn_remove_custom_slug"), callback_data="link:remove_slug"
            )
        )
    buttons.append(
        [InlineKeyboardButton(text=get_text("btn_back"), callback_data="nav:main")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_reply_to_message_inline_keyboard(
    delivered_tg_msg_id: int, conv_id: str
) -> InlineKeyboardMarkup:
    """
    Direct Reply button attached to incoming anonymous message.
    Preserves exact message-level reply target.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("btn_reply_msg"),
                    callback_data=f"reply:msg:{delivered_tg_msg_id}:{conv_id}",
                ),
                InlineKeyboardButton(
                    text=get_text("btn_block_user"),
                    callback_data=f"conv:block:{conv_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=get_text("btn_report_user"),
                    callback_data=f"conv:report:{conv_id}",
                ),
            ],
        ]
    )


def get_inbox_inline_keyboard(
    conversations: List[Conversation], page: int = 0, total_count: int = 0
) -> InlineKeyboardMarkup:
    """Generate Inbox conversation list with pagination."""
    buttons = []
    for conv in conversations:
        status_emoji = "🟢" if conv.status.value == "ACTIVE" else "⚪"
        unread = f" ({conv.unread_by_owner_count})" if conv.unread_by_owner_count > 0 else ""
        btn_text = f"{status_emoji} {conv.sender_alias}{unread}"
        buttons.append(
            [
                InlineKeyboardButton(
                    text=btn_text, callback_data=f"conv:open:{conv.id}"
                )
            ]
        )

    # Navigation row
    nav_row = []
    if page > 0:
        nav_row.append(
            InlineKeyboardButton(text="◀️ قبلی", callback_data=f"nav:inbox:{page - 1}")
        )
    if (page + 1) * 10 < total_count:
        nav_row.append(
            InlineKeyboardButton(text="بعدی ▶️", callback_data=f"nav:inbox:{page + 1}")
        )
    if nav_row:
        buttons.append(nav_row)

    buttons.append(
        [InlineKeyboardButton(text=get_text("btn_back"), callback_data="nav:main")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_conversation_action_inline_keyboard(
    conv_id: str, is_active: bool
) -> InlineKeyboardMarkup:
    """Actions available when viewing a specific conversation."""
    buttons = []
    if is_active:
        buttons.append(
            [
                InlineKeyboardButton(
                    text=get_text("btn_reply_to_conv"),
                    callback_data=f"conv:reply:{conv_id}",
                ),
                InlineKeyboardButton(
                    text=get_text("btn_close_conversation"),
                    callback_data=f"conv:close:{conv_id}",
                ),
            ]
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    text=get_text("btn_block_user"),
                    callback_data=f"conv:block:{conv_id}",
                ),
                InlineKeyboardButton(
                    text=get_text("btn_report_user"),
                    callback_data=f"conv:report:{conv_id}",
                ),
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                text=get_text("btn_back"), callback_data="nav:inbox:0"
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_seen_button_inline_keyboard(
    channel_id: str, post_message_id: int
) -> InlineKeyboardMarkup:
    """Construct explicit 'Seen' button attached to channel posts."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("btn_seen_action"),
                    callback_data=f"seen:{channel_id}:{post_message_id}",
                )
            ]
        ]
    )


def get_cancel_inline_keyboard() -> InlineKeyboardMarkup:
    """Simple cancel button."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("btn_cancel"), callback_data="action:cancel"
                )
            ]
        ]
    )


def get_channel_management_keyboard(
    channel_id: str, is_active: bool, has_slug: bool
) -> InlineKeyboardMarkup:
    """Keyboard for managing a connected channel."""
    toggle_text = (
        get_text("btn_toggle_link_disable")
        if is_active
        else get_text("btn_toggle_link_enable")
    )
    toggle_action = f"ch_manage:toggle:{channel_id}"

    buttons = [
        [
            InlineKeyboardButton(text=toggle_text, callback_data=toggle_action),
            InlineKeyboardButton(
                text=get_text("btn_regenerate_link"),
                callback_data=f"ch_manage:regen:{channel_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=get_text("btn_set_custom_slug"),
                callback_data=f"ch_manage:set_slug:{channel_id}",
            ),
        ],
    ]
    if has_slug:
        buttons[1].append(
            InlineKeyboardButton(
                text=get_text("btn_remove_custom_slug"),
                callback_data=f"ch_manage:remove_slug:{channel_id}",
            )
        )
    buttons.append(
        [InlineKeyboardButton(text=get_text("btn_back"), callback_data="nav:channels")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """Settings menu navigation keyboard."""
    buttons = [
        [
            InlineKeyboardButton(text="🔗 مدیریت لینک ناشناس", callback_data="nav:my_link"),
            InlineKeyboardButton(text="👤 نام مستعار", callback_data="nav:nickname"),
        ],
        [
            InlineKeyboardButton(text="📢 کانال‌های من", callback_data="nav:channels"),
            InlineKeyboardButton(text="🚫 لیست بلاک‌ها", callback_data="nav:blocked_list"),
        ],
        [InlineKeyboardButton(text=get_text("btn_back"), callback_data="nav:main")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_panel_keyboard() -> InlineKeyboardMarkup:
    """Admin dashboard navigation."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📊 آمار سیستم", callback_data="admin:stats"),
                InlineKeyboardButton(text="🚨 گزارش‌ها", callback_data="admin:reports:0"),
            ],
            [
                InlineKeyboardButton(text="🔙 بازگشت به منو", callback_data="nav:main"),
            ],
        ]
    )
