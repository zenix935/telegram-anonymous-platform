"""Centralized Persian and English localization messages."""

from typing import Dict, Any

MESSAGES: Dict[str, Dict[str, str]] = {
    "fa": {
        # General & Navigation
        "welcome": (
            "سلام {name} عزیز! به پلتفرم پیام‌رسان ناشناس خوش آمدید.\n\n"
            "با این ربات می‌توانید:\n"
            "💬 گفت‌وگوهای کاملاً ناشناس و دوطرفه داشته باشید.\n"
            "📢 پیام‌های ناشناس به کانال‌های متصل ارسال کنید.\n\n"
            "از منوی زیر گزینه مورد نظر خود را انتخاب کنید:"
        ),
        "help": (
            "📖 راهنمای ربات پیام‌رسان ناشناس:\n\n"
            "۱. 🔗 <b>لینک ناشناس من:</b> دریافت لینک اختصاصی برای دریافت پیام ناشناس از دیگران.\n"
            "۲. 📥 <b>صندوق پیام‌ها:</b> مدیریت و پاسخ به گفت‌وگوهای ناشناس دریافتی.\n"
            "۳. 📢 <b>ارسال به کانال:</b> ارسال پیام‌های ناشناس به کانال‌هایی که از طریق لینک متصل شده‌اید.\n"
            "۴. 👤 <b>نام مستعار:</b> تنظیم یا تغییر نام مستعار برای نمایش در پیام‌ها.\n"
            "۵. ⚙️ <b>تنظیمات:</b> مدیریت وضعیت لینک‌ها و تنظیمات حساب."
        ),
        "main_menu": "🏠 منوی اصلی:",
        "btn_my_link": "🔗 لینک ناشناس من",
        "btn_inbox": "📥 صندوق پیام‌ها",
        "btn_channels": "📢 کانال‌های متصل",
        "btn_nickname": "👤 نام مستعار",
        "btn_settings": "⚙️ تنظیمات",
        "btn_help": "❓ راهنما",
        "btn_admin_panel": "🛡 پنل مدیریت",
        "btn_cancel": "❌ انصراف",
        "btn_back": "🔙 بازگشت",
        "btn_refresh": "🔄 بروزرسانی",

        # Personal Link Management
        "personal_link_info": (
            "🔗 <b>لینک اختصاصی پیام ناشناس شما:</b>\n\n"
            "<code>{link}</code>\n\n"
            "📊 وضعیت: <b>{status}</b>\n"
            "🏷 اسلاگ اختصاصی: <b>{slug}</b>\n\n"
            "این لینک را در بیو، استوری یا گروه‌ها به اشتراک بگذارید تا دیگران بدون افشای هویت به شما پیام دهند."
        ),
        "link_status_active": "🟢 فعال",
        "link_status_disabled": "🔴 غیرفعال",
        "btn_toggle_link_disable": "⏸ غیرفعال کردن لینک",
        "btn_toggle_link_enable": "▶️ فعال کردن لینک",
        "btn_regenerate_link": "🔄 بازتولید توکن جدید",
        "btn_set_custom_slug": "✏️ تنظیم اسلاگ اختصاصی",
        "btn_remove_custom_slug": "🗑 حذف اسلاگ اختصاصی",
        "prompt_custom_slug": (
            "لطفاً اسلاگ (شناسه دلخواه) مورد نظر خود را وارد کنید.\n\n"
            "قوانین:\n"
            "• بین {min} تا {max} کاراکتر\n"
            "• فقط حروف انگلیسی (a-z)، اعداد (0-9) و خط تیره (_)\n"
            "• عدم استفاده از کلمات رزرو شده"
        ),
        "slug_updated_success": "✅ اسلاگ اختصاصی با موفقیت تنظیم شد:\n<code>{link}</code>",
        "slug_invalid": "❌ اسلاگ وارد شده نامعتبر است. لطفاً فقط از حروف انگلیسی، اعداد و _ استفاده کنید ({min} تا {max} کاراکتر).",
        "slug_reserved": "❌ این اسلاگ رزرو شده است و امکان استفاده از آن وجود ندارد.",
        "slug_taken": "❌ متأسفانه این اسلاگ قبلاً توسط کاربر دیگری ثبت شده است.",
        "link_regenerated": "✅ لینک جدید شما با موفقیت ایجاد و جایگزین شد:\n<code>{link}</code>",
        "link_status_changed": "✅ وضعیت لینک شما تغییر یافت: <b>{status}</b>",

        # Personal Anonymous Chat (Sender side)
        "sender_chat_opened": (
            "💬 <b>شما در حال ارسال پیام ناشناس هستید.</b>\n\n"
            "پیام شما به صورت کاملاً ناشناس تحویل داده می‌شود.\n"
            "می‌توانید متن، عکس، ویس، ویدیو یا فایل ارسال کنید.\n\n"
            "برای پایان دادن به این گفت‌وگو دکمه زیر را فشار دهید:"
        ),
        "btn_close_conversation": "❌ پایان گفتگو",
        "btn_block_user": "🚫 مسدود کردن فرستنده",
        "btn_report_user": "🚨 گزارش تخلف",
        "btn_reply_msg": "↩️ پاسخ",
        "message_sent_to_recipient": "✅ پیام شما به صورت ناشناس تحویل داده شد.",
        "recipient_link_disabled": "⚠️ کاربر مقصد دریافت پیام‌های ناشناس را موقتاً غیرفعال کرده است.",
        "cannot_message_self": "❌ شما نمی‌توانید به لینک اختصاصی خودتان پیام ناشناس بفرستید!",
        "sender_blocked": "⛔ امکان ارسال پیام به این مقصد وجود ندارد.",
        "conversation_closed_by_sender": "🚪 شما به گفت‌وگو پایان دادید.",
        "conversation_closed_by_owner": "🚪 مخاطب به این گفت‌وگو پایان داد.",

        # Personal Anonymous Chat (Owner side / Inbox)
        "incoming_anonymous_message_header": "📩 <b>پیام ناشناس جدید دریافت شد!</b>",
        "incoming_anonymous_message_footer": "👇 برای ارسال پاسخ، روی دکمه «پاسخ» در زیر این پیام کلیک کنید.",
        "reply_mode_activated": (
            "↩️ <b>حالت پاسخ به {sender_alias} فعال شد.</b>\n\n"
            "پیام بعدی شما مستقیماً و منحصراً به همین گفت‌وگو ارسال خواهد شد.\n"
            "🎯 شناسه پاسخ: <code>{reply_target}</code>"
        ),
        "reply_mode_cancelled": "❌ حالت پاسخ لغو شد.",
        "reply_sent_success": "✅ پاسخ شما با موفقیت برای مخاطب ناشناس ارسال شد.",
        "inbox_title": "📥 <b>صندوق پیام‌های ناشناس شما:</b>\n\nتعداد کل گفت‌وگوها: {total_count}",
        "inbox_empty": "📭 صندوق شما در حال حاضر خالی است.",
        "conversation_view_title": (
            "💬 <b>گفت‌وگو با {sender_alias}</b>\n"
            "📊 وضعیت: <b>{status}</b>\n"
            "🕒 تاریخ ایجاد: <code>{created_at}</code>\n"
            "📝 آخرین پیام: <code>{last_message_at}</code>"
        ),
        "btn_reply_to_conv": "↩️ ارسال پیام در این گفت‌وگو",
        "btn_unblock_user": "🔓 رفع مسدودیت",

        # Blocking & Reports
        "block_confirm": "آیا از مسدود کردن این فرستنده ناشناس اطمینان دارید؟ او دیگر قادر به ارسال پیام به شما نخواهد بود.",
        "user_blocked_success": "🚫 فرستنده ناشناس با موفقیت مسدود شد.",
        "user_unblocked_success": "🔓 فرستنده ناشناس رفع مسدودیت شد.",
        "report_prompt": "لطفاً دلیل گزارش تخلف را انتخاب یا تایپ کنید:",
        "report_submitted": "🚨 گزارش شما ثبت شد و توسط مدیران سیستم بررسی خواهد شد.",

        # Channel Anonymous Publishing
        "channel_submission_opened": (
            "📢 <b>ارسال پیام ناشناس به کانال «{channel_title}»</b>\n\n"
            "پیام شما به صورت کاملاً ناشناس در کانال منتشر خواهد شد.\n"
            "نام کاربری و هویت تلگرام شما به هیچ عنوان درج نمی‌شود.\n\n"
            "👇 پیام، عکس، ویس، ویدیو یا فایل خود را ارسال کنید:"
        ),
        "channel_post_published_success": "✅ پیام ناشناس شما با موفقیت در کانال منتشر شد!",
        "channel_submission_disabled": "⛔ ارسال پیام ناشناس به این کانال موقتاً توسط مدیران متوقف شده است.",
        "channel_submission_failed": "❌ متأسفانه خطایی در انتشار پیام در کانال رخ داد.",
        "btn_seen_action": "👁 پیام را دیدم",
        "seen_recorded": "👁 بازدید شما ثبت شد!",
        "seen_already_recorded": "⚠️ شما قبلاً این پیام را دیده‌اید.",
        "seen_notification_to_author": "👁 پیام شما در کانال توسط <b>{count}</b> نفر دیده شد.",

        # Nickname System
        "nickname_info": (
            "👤 <b>نام مستعار ناشناس شما:</b> <b>{nickname}</b>\n\n"
            "این نام در صورت فعال بودن به عنوان هشتگ یا امضا روی پیام‌های ناشناس شما قرار می‌گیرد و ربطی به نام کاربری واقعی تلگرام شما ندارد."
        ),
        "btn_set_nickname": "✏️ تنظیم نام مستعار",
        "btn_remove_nickname": "🗑 حذف نام مستعار",
        "prompt_nickname": "لطفاً نام مستعار جدید خود را وارد کنید (حداکثر {max} کاراکتر):",
        "nickname_updated": "✅ نام مستعار شما به <b>{nickname}</b> تغییر یافت.",
        "nickname_removed": "✅ نام مستعار شما حذف شد.",
        "nickname_invalid": "❌ نام مستعار وارد شده نامعتبر یا طولانی است.",
        "nickname_reserved": "❌ این نام مستعار رزرو شده است و امکان استفاده از آن وجود ندارد.",

        # Channel Admin & Management
        "channel_admin_title": (
            "📢 <b>مدیریت کانال: {channel_title}</b>\n\n"
            "🔗 لینک ارسال ناشناس:\n<code>{link}</code>\n\n"
            "📊 وضعیت ارسال: <b>{status}</b>\n"
            "🎨 الگوی پیام: <code>{template}</code>"
        ),
        "channel_connect_instructions": (
            "برای اتصال کانال به ربات:\n"
            "۱. ابتدا ربات را در کانال خود به عنوان <b>مدیر (Admin)</b> با دسترسی ارسال پیام اضافه کنید.\n"
            "۲. سپس یک پیام از کانال را به این ربات فوروارد (Forward) کنید یا آیدی عددی کانال را بفرستید."
        ),
        "channel_connected_success": "✅ کانال <b>{channel_title}</b> با موفقیت متصل شد!\n\nلینک ارسال ناشناس اختصاصی:\n<code>{link}</code>",
        "channel_permission_error": "❌ ربات دسترسی ادمین برای ارسال پیام در این کانال را ندارد.",
        "not_channel_admin": "❌ شما به عنوان مدیر در این کانال شناسایی نشدید.",

        # Rate Limiting & Filters
        "rate_limit_exceeded": "⏳ شما بیش از حد مجاز پیام ارسال کرده‌اید. لطفاً کمی بعد دوباره تلاش کنید.",
        "duplicate_message_rejected": "⚠️ پیام تکراری شناسایی شد. لطفاً کمی بعد تلاش کنید.",
        "content_filtered_word": "⛔ پیام شما به دلیل حاوی بودن کلمات غیرمجاز رد شد.",
        "content_filtered_url": "⛔ ارسال لینک در پیام ناشناس مجاز نیست.",
        "message_too_long": "❌ طول پیام شما بیش از حد مجاز ({max} کاراکتر) است.",

        # System & Admin Panel
        "admin_welcome": "🛡 <b>پنل مدیریت سیستم</b>\n\nیکی از بخش‌ها را انتخاب کنید:",
        "admin_stats": (
            "📊 <b>آمار سیستم:</b>\n\n"
            "👥 کاربران کل: <code>{users_count}</code>\n"
            "💬 گفت‌وگوهای فعال: <code>{active_convs}</code>\n"
            "📨 پیام‌های ردوبدل شده: <code>{messages_count}</code>\n"
            "📢 کانال‌های متصل: <code>{channels_count}</code>\n"
            "👁 کل Seen ثبت شده: <code>{seen_count}</code>\n"
            "🚨 گزارش‌های بررسی‌نشده: <code>{pending_reports}</code>"
        ),
        "generic_error": "❌ متأسفانه خطایی در پردازش رخ داد. لطفاً مجدداً تلاش کنید.",
    }
}


def get_text(key: str, lang: str = "fa", **kwargs: Any) -> str:
    """Retrieve localized message by key, with formatting support."""
    lang_dict = MESSAGES.get(lang, MESSAGES["fa"])
    template = lang_dict.get(key, MESSAGES["fa"].get(key, f"[{key}]"))
    if kwargs:
        try:
            return template.format(**kwargs)
        except Exception:
            return template
    return template
