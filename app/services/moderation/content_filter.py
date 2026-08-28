"""Server-side content filtering and moderation engine."""

import re
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.database.models import ContentFilter
from app.database.repositories import ModerationRepository

URL_PATTERN = re.compile(
    r"(https?://|www\.|t\.me/|telegram\.me/|joinchat/)[^\s]+", re.IGNORECASE
)
USERNAME_PATTERN = re.compile(r"@[a-zA-Z0-9_]{4,}", re.IGNORECASE)


class ContentFilterService:
    """Service to evaluate messages against forbidden words, patterns, and links."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ModerationRepository(session)

    async def filter_content(
        self, text: Optional[str], allow_urls: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate text against length, URLs, usernames, and database filters.
        Returns (is_clean, reason).
        """
        if not text:
            return True, None

        cleaned_text = text.strip()

        # Length check
        if len(cleaned_text) > settings.max_message_length:
            return False, "message_too_long"

        # URL check if not explicitly allowed
        if not allow_urls and URL_PATTERN.search(cleaned_text):
            return False, "content_filtered_url"

        # Fetch active dynamic content filters
        filters = await self.repo.get_active_filters()
        for f in filters:
            if f.is_regex:
                try:
                    if re.search(f.pattern, cleaned_text, re.IGNORECASE):
                        return False, "content_filtered_word"
                except Exception:
                    continue
            else:
                if f.pattern.lower() in cleaned_text.lower():
                    return False, "content_filtered_word"

        return True, None
