"""Template validation and rendering engine for channel anonymous messages."""

from datetime import datetime, timezone
import html
from typing import Dict, Optional, Tuple


class TemplateEngine:
    """Safe template renderer supporting variables without exposing internal secrets."""

    ALLOWED_VARIABLES = {
        "{message}",
        "{nickname}",
        "{anonymous_tag}",
        "{date}",
        "{time}",
        "{message_id}",
    }

    FORBIDDEN_PATTERNS = {
        "user_id",
        "telegram_id",
        "owner_id",
        "sender_id",
        "token",
        "secret",
        "password",
        "database",
    }

    @classmethod
    def validate_template(cls, template: str) -> Tuple[bool, Optional[str]]:
        """
        Ensure template includes necessary variables and avoids forbidden patterns.
        """
        if not template or "{message}" not in template:
            return False, "Template must contain {message} variable."

        # Check for forbidden patterns
        lower = template.lower()
        for forbidden in cls.FORBIDDEN_PATTERNS:
            if forbidden in lower:
                return False, f"Template contains forbidden variable/pattern: '{forbidden}'"

        return True, None

    @classmethod
    def render_channel_post(
        cls,
        template: str,
        message_text: Optional[str] = None,
        nickname: Optional[str] = None,
        post_telegram_id: Optional[int] = None,
    ) -> str:
        """
        Safely render the post body with variables.
        """
        now = datetime.now(timezone.utc)
        safe_msg = message_text.strip() if message_text else ""
        
        # Build anonymous tag and nickname signature
        anon_tag = "#پیام_ناشناس"
        nick_str = f"#{nickname.replace(' ', '_')}" if nickname else ""

        rendered = template
        rendered = rendered.replace("{message}", safe_msg)
        rendered = rendered.replace("{nickname}", nick_str)
        rendered = rendered.replace("{anonymous_tag}", anon_tag)
        rendered = rendered.replace("{date}", now.strftime("%Y-%m-%d"))
        rendered = rendered.replace("{time}", now.strftime("%H:%M UTC"))
        rendered = rendered.replace("{message_id}", str(post_telegram_id or ""))

        # Clean trailing extra whitespaces/newlines
        return rendered.strip()
