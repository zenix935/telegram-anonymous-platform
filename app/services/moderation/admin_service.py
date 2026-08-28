"""System administration, moderation, and metrics service."""

import uuid
from typing import Any, Dict, List, Optional
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Report, ReportStatus, User
from app.database.repositories import (
    ChannelRepository,
    ConversationRepository,
    ModerationRepository,
    SeenRepository,
    UserRepository,
)


class AdminService:
    """Service handling platform statistics, bans, and moderation workflows."""

    def __init__(self, session: AsyncSession, bot: Bot):
        self.session = session
        self.bot = bot
        self.user_repo = UserRepository(session)
        self.conv_repo = ConversationRepository(session)
        self.channel_repo = ChannelRepository(session)
        self.mod_repo = ModerationRepository(session)
        self.seen_repo = SeenRepository(session)

    async def get_system_stats(self) -> Dict[str, Any]:
        """Aggregate high-level platform statistics."""
        return {
            "users_count": await self.user_repo.count_all(),
            "active_convs": await self.conv_repo.count_active(),
            "messages_count": await self.conv_repo.count_total_messages(),
            "channels_count": await self.channel_repo.count_all(),
            "seen_count": await self.seen_repo.count_total_seen(),
            "pending_reports": await self.mod_repo.count_pending_reports(),
        }

    async def ban_user(self, user_id: uuid.UUID, reason: str) -> bool:
        """Globally ban user from using bot."""
        return await self.user_repo.set_global_ban(user_id=user_id, is_banned=True, reason=reason)

    async def unban_user(self, user_id: uuid.UUID) -> bool:
        """Unban user."""
        return await self.user_repo.set_global_ban(user_id=user_id, is_banned=False, reason=None)

    async def get_pending_reports(self, limit: int = 10) -> List[Report]:
        """Fetch unresolved abuse reports."""
        return await self.mod_repo.get_pending_reports(limit=limit)
