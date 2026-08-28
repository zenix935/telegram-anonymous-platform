"""Link service handling personal and channel anonymous links."""

import uuid
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.database.models import Channel, PersonalLink
from app.database.repositories import ChannelRepository, PersonalLinkRepository
from app.security.tokens import generate_secure_token, validate_custom_slug


class LinkService:
    """Service for creating, validating, toggling, and resolving anonymous links."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.personal_repo = PersonalLinkRepository(session)
        self.channel_repo = ChannelRepository(session)

    def format_personal_url(self, token_or_slug: str) -> str:
        """Construct full Telegram deep link for personal anonymous chat."""
        return f"https://t.me/{settings.bot_username}?start=p_{token_or_slug}"

    def format_channel_url(self, token_or_slug: str) -> str:
        """Construct full Telegram deep link for channel anonymous submission."""
        return f"https://t.me/{settings.bot_username}?start=c_{token_or_slug}"

    async def get_or_create_personal_link(self, owner_id: uuid.UUID) -> PersonalLink:
        """Retrieve existing personal link or generate new opaque random token."""
        link = await self.personal_repo.get_by_owner_id(owner_id)
        if not link:
            random_token = generate_secure_token(prefix="", entropy_bytes=settings.token_entropy_bytes)
            link = await self.personal_repo.create_or_update(
                owner_id=owner_id,
                random_token=random_token,
            )
        return link

    async def regenerate_personal_link(self, owner_id: uuid.UUID) -> PersonalLink:
        """Regenerate a brand new random token, revoking prior random token."""
        new_token = generate_secure_token(prefix="", entropy_bytes=settings.token_entropy_bytes)
        link = await self.personal_repo.create_or_update(
            owner_id=owner_id,
            random_token=new_token,
        )
        return link

    async def set_personal_custom_slug(
        self, owner_id: uuid.UUID, slug: str
    ) -> Tuple[bool, Optional[str], Optional[PersonalLink]]:
        """
        Validate and set custom slug for user personal link.
        Returns (success, error_message, updated_link).
        """
        is_valid, err = validate_custom_slug(slug)
        if not is_valid:
            return False, err, None

        link = await self.get_or_create_personal_link(owner_id)
        if await self.personal_repo.is_slug_taken(slug, exclude_link_id=link.id):
            return False, "taken", None

        link.custom_slug = slug.strip().lower()
        await self.session.flush()
        return True, None, link

    async def remove_personal_custom_slug(self, owner_id: uuid.UUID) -> Optional[PersonalLink]:
        """Remove user custom slug, reverting purely to random token."""
        link = await self.get_or_create_personal_link(owner_id)
        link.custom_slug = None
        await self.session.flush()
        return link

    async def toggle_personal_link(self, owner_id: uuid.UUID, is_active: bool) -> Optional[PersonalLink]:
        """Enable or disable receiving messages through personal link."""
        link = await self.get_or_create_personal_link(owner_id)
        link.is_active = is_active
        await self.session.flush()
        return link

    async def resolve_start_payload(
        self, start_param: str
    ) -> Tuple[str, Optional[PersonalLink], Optional[Channel]]:
        """
        Securely parse and dispatch deep link start parameter.
        Strict separation:
        - 'p_' prefix -> Personal Link ONLY
        - 'c_' prefix -> Channel Link ONLY
        Returns (mode: 'personal' | 'channel' | 'invalid', personal_link, channel).
        """
        if not start_param or len(start_param) < 3:
            return "invalid", None, None

        if start_param.startswith("p_"):
            token_part = start_param[2:]
            personal_link = await self.personal_repo.get_by_token_or_slug(token_part)
            if personal_link:
                return "personal", personal_link, None
            return "invalid", None, None

        elif start_param.startswith("c_"):
            token_part = start_param[2:]
            channel = await self.channel_repo.get_by_token_or_slug(token_part)
            if channel:
                return "channel", None, channel
            return "invalid", None, None

        return "invalid", None, None
