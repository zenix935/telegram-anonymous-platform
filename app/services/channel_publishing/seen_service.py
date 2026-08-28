"""Explicit Seen button and notification handler."""

import uuid
from typing import Optional, Tuple
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.messages import get_text
from app.database.repositories import ChannelRepository, SeenRepository, UserRepository


class SeenService:
    """Service to process seen events and send anonymous aggregate notifications."""

    def __init__(self, session: AsyncSession, bot: Bot):
        self.session = session
        self.bot = bot
        self.seen_repo = SeenRepository(session)
        self.channel_repo = ChannelRepository(session)
        self.user_repo = UserRepository(session)

    async def process_seen_click(
        self, channel_id_str: str, telegram_post_id: int, viewer_telegram_id: int
    ) -> Tuple[bool, str]:
        """
        Record unique seen event and notify anonymous author if applicable.
        Never reveals viewer identity to author.
        """
        try:
            channel_id = uuid.UUID(channel_id_str)
        except ValueError:
            return False, "invalid_channel_id"

        viewer, _ = await self.user_repo.get_or_create(telegram_id=viewer_telegram_id)
        msg = await self.seen_repo.get_channel_message_by_post_id(
            channel_id=channel_id, telegram_post_message_id=telegram_post_id
        )
        if not msg:
            return False, "message_not_found"

        # Record idempotent seen
        is_new, total_seen, author_id = await self.seen_repo.record_seen(
            channel_message_id=msg.id, viewer_id=viewer.id
        )

        if not is_new:
            return False, "seen_already_recorded"

        # If this message has an author and meets milestone notification criteria
        if author_id and (total_seen in [1, 3, 5, 10, 25, 50, 100, 250, 500, 1000] or total_seen % 50 == 0):
            author = await self.user_repo.get_by_id(author_id)
            if author:
                notif_text = get_text("seen_notification_to_author", count=total_seen)
                try:
                    await self.bot.send_message(
                        chat_id=author.telegram_id,
                        text=notif_text,
                        parse_mode="HTML",
                    )
                except Exception:
                    pass  # Non-blocking if author blocked the bot

        return True, "seen_recorded"
