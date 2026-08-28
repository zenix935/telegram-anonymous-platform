"""Database repositories providing clean, isolated data access layer."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_, func, or_, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import (
    AnonymousProfile,
    Block,
    Channel,
    ChannelAdmin,
    ChannelLink,
    ChannelMessage,
    ContentFilter,
    Conversation,
    ConversationMessage,
    ConversationStatus,
    MessageSenderRole,
    PersonalLink,
    Report,
    ReportStatus,
    SeenEvent,
    User,
    utcnow,
)


class UserRepository:
    """Repository for User management."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        query = (
            select(User)
            .options(
                selectinload(User.anonymous_profile),
                selectinload(User.personal_link),
            )
            .where(User.telegram_id == telegram_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        query = (
            select(User)
            .options(
                selectinload(User.anonymous_profile),
                selectinload(User.personal_link),
            )
            .where(User.id == user_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_or_create(
        self, telegram_id: int, first_name: Optional[str] = None, username: Optional[str] = None, is_admin: bool = False
    ) -> Tuple[User, bool]:
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            # Update meta if changed
            if user.first_name != first_name or user.username != username or (is_admin and not user.is_admin):
                user.first_name = first_name
                user.username = username
                if is_admin:
                    user.is_admin = True
                user.updated_at = utcnow()
                await self.session.flush()
            return user, False

        user = User(
            telegram_id=telegram_id,
            first_name=first_name,
            username=username,
            is_admin=is_admin,
        )
        self.session.add(user)
        await self.session.flush()
        
        # Create empty anonymous profile
        profile = AnonymousProfile(user_id=user.id)
        self.session.add(profile)
        await self.session.flush()
        
        return user, True

    async def set_global_ban(self, user_id: uuid.UUID, is_banned: bool, reason: Optional[str] = None) -> bool:
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(is_globally_banned=is_banned, ban_reason=reason, updated_at=utcnow())
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def count_all(self) -> int:
        query = select(func.count(User.id))
        result = await self.session.execute(query)
        return result.scalar() or 0


class PersonalLinkRepository:
    """Repository for personal anonymous links."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_owner_id(self, owner_id: uuid.UUID) -> Optional[PersonalLink]:
        query = select(PersonalLink).where(PersonalLink.owner_id == owner_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_token_or_slug(self, token_or_slug: str) -> Optional[PersonalLink]:
        token_clean = token_or_slug.strip().lower()
        query = (
            select(PersonalLink)
            .options(selectinload(PersonalLink.owner).selectinload(User.anonymous_profile))
            .where(
                or_(
                    func.lower(PersonalLink.random_token) == token_clean,
                    func.lower(PersonalLink.custom_slug) == token_clean,
                )
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def is_slug_taken(self, slug: str, exclude_link_id: Optional[uuid.UUID] = None) -> bool:
        slug_clean = slug.strip().lower()
        query = select(PersonalLink.id).where(func.lower(PersonalLink.custom_slug) == slug_clean)
        if exclude_link_id:
            query = query.where(PersonalLink.id != exclude_link_id)
        result = await self.session.execute(query)
        if result.scalar_one_or_none() is not None:
            return True
            
        # Also check channel slugs to prevent cross-namespace collision
        c_query = select(ChannelLink.id).where(func.lower(ChannelLink.custom_slug) == slug_clean)
        c_result = await self.session.execute(c_query)
        return c_result.scalar_one_or_none() is not None

    async def create_or_update(
        self, owner_id: uuid.UUID, random_token: str, custom_slug: Optional[str] = None
    ) -> PersonalLink:
        link = await self.get_by_owner_id(owner_id)
        if link:
            link.random_token = random_token
            if custom_slug is not None:
                link.custom_slug = custom_slug.lower() if custom_slug else None
            link.updated_at = utcnow()
        else:
            link = PersonalLink(
                owner_id=owner_id,
                random_token=random_token,
                custom_slug=custom_slug.lower() if custom_slug else None,
                is_active=True,
            )
            self.session.add(link)
        await self.session.flush()
        return link

    async def set_active_status(self, link_id: uuid.UUID, is_active: bool) -> bool:
        stmt = (
            update(PersonalLink)
            .where(PersonalLink.id == link_id)
            .values(is_active=is_active, updated_at=utcnow())
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0


class ChannelRepository:
    """Repository for connected channels and channel links."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_telegram_id(self, telegram_channel_id: int) -> Optional[Channel]:
        query = (
            select(Channel)
            .options(
                selectinload(Channel.channel_link),
                selectinload(Channel.admins),
            )
            .where(Channel.telegram_channel_id == telegram_channel_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_id(self, channel_id: uuid.UUID) -> Optional[Channel]:
        query = (
            select(Channel)
            .options(
                selectinload(Channel.channel_link),
                selectinload(Channel.admins),
            )
            .where(Channel.id == channel_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_token_or_slug(self, token_or_slug: str) -> Optional[Channel]:
        token_clean = token_or_slug.strip().lower()
        query = (
            select(Channel)
            .join(ChannelLink, Channel.id == ChannelLink.channel_id)
            .options(selectinload(Channel.channel_link))
            .where(
                or_(
                    func.lower(ChannelLink.random_token) == token_clean,
                    func.lower(ChannelLink.custom_slug) == token_clean,
                )
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def is_slug_taken(self, slug: str, exclude_link_id: Optional[uuid.UUID] = None) -> bool:
        slug_clean = slug.strip().lower()
        query = select(ChannelLink.id).where(func.lower(ChannelLink.custom_slug) == slug_clean)
        if exclude_link_id:
            query = query.where(ChannelLink.id != exclude_link_id)
        result = await self.session.execute(query)
        if result.scalar_one_or_none() is not None:
            return True
            
        p_query = select(PersonalLink.id).where(func.lower(PersonalLink.custom_slug) == slug_clean)
        p_result = await self.session.execute(p_query)
        return p_result.scalar_one_or_none() is not None

    async def create_channel(
        self,
        telegram_channel_id: int,
        title: str,
        admin_user_id: uuid.UUID,
        username: Optional[str] = None,
        random_token: Optional[str] = None,
    ) -> Channel:
        channel = Channel(
            telegram_channel_id=telegram_channel_id,
            title=title,
            username=username,
            is_active=True,
        )
        self.session.add(channel)
        await self.session.flush()

        admin = ChannelAdmin(
            channel_id=channel.id,
            user_id=admin_user_id,
            role="owner",
        )
        self.session.add(admin)

        if random_token:
            link = ChannelLink(
                channel_id=channel.id,
                random_token=random_token,
                is_active=True,
            )
            self.session.add(link)

        await self.session.flush()
        return channel

    async def get_user_channels(self, user_id: uuid.UUID) -> List[Channel]:
        query = (
            select(Channel)
            .join(ChannelAdmin, Channel.id == ChannelAdmin.channel_id)
            .options(selectinload(Channel.channel_link))
            .where(ChannelAdmin.user_id == user_id)
            .order_by(Channel.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def is_user_channel_admin(self, channel_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        query = select(ChannelAdmin.id).where(
            and_(
                ChannelAdmin.channel_id == channel_id,
                ChannelAdmin.user_id == user_id,
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def update_template(self, channel_id: uuid.UUID, template: str) -> bool:
        stmt = (
            update(Channel)
            .where(Channel.id == channel_id)
            .values(post_template=template, updated_at=utcnow())
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def count_all(self) -> int:
        query = select(func.count(Channel.id))
        result = await self.session.execute(query)
        return result.scalar() or 0


class ConversationRepository:
    """Repository for 1-to-1 anonymous conversations and messages."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, conversation_id: uuid.UUID) -> Optional[Conversation]:
        query = (
            select(Conversation)
            .options(
                selectinload(Conversation.owner),
                selectinload(Conversation.sender),
            )
            .where(Conversation.id == conversation_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_active_conversation(
        self, owner_id: uuid.UUID, sender_id: uuid.UUID
    ) -> Optional[Conversation]:
        query = (
            select(Conversation)
            .options(
                selectinload(Conversation.owner),
                selectinload(Conversation.sender),
            )
            .where(
                and_(
                    Conversation.owner_id == owner_id,
                    Conversation.sender_id == sender_id,
                    Conversation.status == ConversationStatus.ACTIVE,
                )
            )
            .order_by(Conversation.updated_at.desc())
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_conversation(
        self, owner_id: uuid.UUID, sender_id: uuid.UUID, sender_alias: str = "ناشناس"
    ) -> Conversation:
        conv = Conversation(
            owner_id=owner_id,
            sender_id=sender_id,
            sender_alias=sender_alias,
            status=ConversationStatus.ACTIVE,
        )
        self.session.add(conv)
        await self.session.flush()
        return conv

    async def get_owner_inbox(
        self, owner_id: uuid.UUID, limit: int = 20, offset: int = 0
    ) -> Tuple[List[Conversation], int]:
        count_q = select(func.count(Conversation.id)).where(Conversation.owner_id == owner_id)
        total_count = (await self.session.execute(count_q)).scalar() or 0

        query = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(Conversation.owner_id == owner_id)
            .order_by(Conversation.last_message_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all()), total_count

    async def add_message(
        self,
        conversation_id: uuid.UUID,
        sender_role: MessageSenderRole,
        content_type: str = "text",
        text_content: Optional[str] = None,
        media_file_id: Optional[str] = None,
        caption: Optional[str] = None,
        recipient_telegram_message_id: Optional[int] = None,
        sender_telegram_message_id: Optional[int] = None,
    ) -> ConversationMessage:
        msg = ConversationMessage(
            conversation_id=conversation_id,
            sender_role=sender_role,
            content_type=content_type,
            text_content=text_content,
            media_file_id=media_file_id,
            caption=caption,
            recipient_telegram_message_id=recipient_telegram_message_id,
            sender_telegram_message_id=sender_telegram_message_id,
        )
        self.session.add(msg)
        
        # Update conversation last_message_at
        stmt = (
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(last_message_at=utcnow(), updated_at=utcnow())
        )
        await self.session.execute(stmt)
        await self.session.flush()
        return msg

    async def get_message_by_recipient_tg_id(
        self, recipient_tg_msg_id: int
    ) -> Optional[ConversationMessage]:
        query = (
            select(ConversationMessage)
            .options(
                selectinload(ConversationMessage.conversation).selectinload(Conversation.owner),
                selectinload(ConversationMessage.conversation).selectinload(Conversation.sender),
            )
            .where(ConversationMessage.recipient_telegram_message_id == recipient_tg_msg_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def set_status(
        self, conversation_id: uuid.UUID, status: ConversationStatus
    ) -> bool:
        stmt = (
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(status=status, updated_at=utcnow())
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def count_active(self) -> int:
        query = select(func.count(Conversation.id)).where(
            Conversation.status == ConversationStatus.ACTIVE
        )
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def count_total_messages(self) -> int:
        query = select(func.count(ConversationMessage.id))
        result = await self.session.execute(query)
        return result.scalar() or 0


class ModerationRepository:
    """Repository for Block, Report, Ban, and Content Filtering."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def is_blocked(self, blocker_id: uuid.UUID, blocked_id: uuid.UUID) -> bool:
        query = select(Block.id).where(
            and_(Block.blocker_id == blocker_id, Block.blocked_id == blocked_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def block_user(self, blocker_id: uuid.UUID, blocked_id: uuid.UUID) -> bool:
        if await self.is_blocked(blocker_id, blocked_id):
            return True
        block = Block(blocker_id=blocker_id, blocked_id=blocked_id)
        self.session.add(block)
        await self.session.flush()
        return True

    async def unblock_user(self, blocker_id: uuid.UUID, blocked_id: uuid.UUID) -> bool:
        stmt = delete(Block).where(
            and_(Block.blocker_id == blocker_id, Block.blocked_id == blocked_id)
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def get_blocked_users_by_blocker(self, blocker_id: uuid.UUID) -> List[Block]:
        query = (
            select(Block)
            .where(Block.blocker_id == blocker_id)
            .order_by(Block.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_report(
        self,
        reporter_id: uuid.UUID,
        reported_user_id: uuid.UUID,
        reason: str,
        conversation_id: Optional[uuid.UUID] = None,
    ) -> Report:
        report = Report(
            reporter_id=reporter_id,
            reported_user_id=reported_user_id,
            reason=reason,
            conversation_id=conversation_id,
            status=ReportStatus.PENDING,
        )
        self.session.add(report)
        await self.session.flush()
        return report

    async def get_pending_reports(self, limit: int = 20) -> List[Report]:
        query = (
            select(Report)
            .options(
                selectinload(Report.conversation),
            )
            .where(Report.status == ReportStatus.PENDING)
            .order_by(Report.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_report_by_id(self, report_id: uuid.UUID) -> Optional[Report]:
        query = (
            select(Report)
            .options(
                selectinload(Report.conversation),
            )
            .where(Report.id == report_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def resolve_report(
        self, report_id: uuid.UUID, status: ReportStatus, moderator_notes: Optional[str] = None
    ) -> bool:
        stmt = (
            update(Report)
            .where(Report.id == report_id)
            .values(status=status, moderator_notes=moderator_notes, updated_at=utcnow())
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def count_pending_reports(self) -> int:
        query = select(func.count(Report.id)).where(Report.status == ReportStatus.PENDING)
        result = await self.session.execute(query)
        return result.scalar() or 0

    async def get_active_filters(self) -> List[ContentFilter]:
        query = select(ContentFilter).where(ContentFilter.is_active == True)
        result = await self.session.execute(query)
        return list(result.scalars().all())


class SeenRepository:
    """Repository for Channel Message and Seen Events."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_channel_message(
        self,
        channel_id: uuid.UUID,
        telegram_post_message_id: int,
        author_id: Optional[uuid.UUID] = None,
        content_type: str = "text",
        text_content: Optional[str] = None,
        media_file_id: Optional[str] = None,
        nickname_used: Optional[str] = None,
    ) -> ChannelMessage:
        msg = ChannelMessage(
            channel_id=channel_id,
            telegram_post_message_id=telegram_post_message_id,
            author_id=author_id,
            content_type=content_type,
            text_content=text_content,
            media_file_id=media_file_id,
            nickname_used=nickname_used,
            seen_count=0,
        )
        self.session.add(msg)
        await self.session.flush()
        return msg

    async def get_channel_message_by_post_id(
        self, channel_id: uuid.UUID, telegram_post_message_id: int
    ) -> Optional[ChannelMessage]:
        query = (
            select(ChannelMessage)
            .options(selectinload(ChannelMessage.channel))
            .where(
                and_(
                    ChannelMessage.channel_id == channel_id,
                    ChannelMessage.telegram_post_message_id == telegram_post_message_id,
                )
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def record_seen(
        self, channel_message_id: uuid.UUID, viewer_id: uuid.UUID
    ) -> Tuple[bool, int, Optional[uuid.UUID]]:
        """
        Idempotent seen registration.
        Returns (is_new_seen, total_seen_count, author_id).
        """
        # Check if already seen
        query = select(SeenEvent.id).where(
            and_(
                SeenEvent.channel_message_id == channel_message_id,
                SeenEvent.viewer_id == viewer_id,
            )
        )
        existing = (await self.session.execute(query)).scalar_one_or_none()
        if existing:
            # Already seen
            msg_q = select(ChannelMessage).where(ChannelMessage.id == channel_message_id)
            msg = (await self.session.execute(msg_q)).scalar_one()
            return False, msg.seen_count, msg.author_id

        # Insert SeenEvent
        event = SeenEvent(channel_message_id=channel_message_id, viewer_id=viewer_id)
        self.session.add(event)

        # Atomic increment
        stmt = (
            update(ChannelMessage)
            .where(ChannelMessage.id == channel_message_id)
            .values(seen_count=ChannelMessage.seen_count + 1)
            .returning(ChannelMessage.seen_count, ChannelMessage.author_id)
        )
        res = await self.session.execute(stmt)
        row = res.one()
        await self.session.flush()
        return True, row[0], row[1]

    async def count_total_seen(self) -> int:
        query = select(func.count(SeenEvent.id))
        result = await self.session.execute(query)
        return result.scalar() or 0
