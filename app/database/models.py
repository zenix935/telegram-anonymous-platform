"""SQLAlchemy PostgreSQL models for Telegram Anonymous Platform."""

import enum
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base


def utcnow() -> datetime:
    """Return current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class ConversationStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    CLOSED_BY_OWNER = "CLOSED_BY_OWNER"
    CLOSED_BY_SENDER = "CLOSED_BY_SENDER"
    BLOCKED = "BLOCKED"


class ReportStatus(str, enum.Enum):
    PENDING = "PENDING"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"


class MessageSenderRole(str, enum.Enum):
    SENDER = "SENDER"
    OWNER = "OWNER"


class User(Base):
    """Internal user record mapping to a unique Telegram user."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    first_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_globally_banned: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, index=True
    )
    ban_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    # Relationships
    anonymous_profile: Mapped[Optional["AnonymousProfile"]] = relationship(
        "AnonymousProfile", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    personal_link: Mapped[Optional["PersonalLink"]] = relationship(
        "PersonalLink", back_populates="owner", uselist=False, cascade="all, delete-orphan"
    )
    owned_conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation", foreign_keys="Conversation.owner_id", back_populates="owner"
    )
    sent_conversations: Mapped[List["Conversation"]] = relationship(
        "Conversation", foreign_keys="Conversation.sender_id", back_populates="sender"
    )
    channel_admins: Mapped[List["ChannelAdmin"]] = relationship(
        "ChannelAdmin", back_populates="user", cascade="all, delete-orphan"
    )


class AnonymousProfile(Base):
    """Anonymous profile metadata, customizable per-user (e.g. nickname)."""

    __tablename__ = "anonymous_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    nickname: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="anonymous_profile")


class PersonalLink(Base):
    """
    Personal anonymous link entry.
    Contains both opaque cryptographically generated random_token and optional custom_slug.
    """

    __tablename__ = "personal_links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    random_token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    custom_slug: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    owner: Mapped["User"] = relationship("User", back_populates="personal_link")


class Channel(Base):
    """Connected Telegram channel entity."""

    __tablename__ = "channels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    telegram_channel_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    post_template: Mapped[str] = mapped_column(
        Text,
        default="{message}\n\n#پیام_ناشناس {nickname}",
        nullable=False,
    )
    enable_seen_button: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    # Relationships
    channel_link: Mapped[Optional["ChannelLink"]] = relationship(
        "ChannelLink", back_populates="channel", uselist=False, cascade="all, delete-orphan"
    )
    admins: Mapped[List["ChannelAdmin"]] = relationship(
        "ChannelAdmin", back_populates="channel", cascade="all, delete-orphan"
    )
    messages: Mapped[List["ChannelMessage"]] = relationship(
        "ChannelMessage", back_populates="channel", cascade="all, delete-orphan"
    )


class ChannelAdmin(Base):
    """Admins associated with managing a connected channel."""

    __tablename__ = "channel_admins"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(32), default="admin", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    channel: Mapped["Channel"] = relationship("Channel", back_populates="admins")
    user: Mapped["User"] = relationship("User", back_populates="channel_admins")

    __table_args__ = (
        UniqueConstraint("channel_id", "user_id", name="uq_channel_admin_channel_user"),
    )


class ChannelLink(Base):
    """
    Channel anonymous submission link.
    Contains both opaque cryptographically generated random_token and optional custom_slug.
    """

    __tablename__ = "channel_links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channels.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    random_token: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    custom_slug: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    channel: Mapped["Channel"] = relationship("Channel", back_populates="channel_link")


class Conversation(Base):
    """
    Persistent 1-to-1 anonymous conversation between link owner and anonymous sender.
    """

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[ConversationStatus] = mapped_column(
        Enum(ConversationStatus, name="conversation_status_enum", create_type=False),
        default=ConversationStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    sender_alias: Mapped[str] = mapped_column(
        String(64), default="ناشناس", nullable=False
    )
    unread_by_owner_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    owner: Mapped["User"] = relationship(
        "User", foreign_keys=[owner_id], back_populates="owned_conversations"
    )
    sender: Mapped["User"] = relationship(
        "User", foreign_keys=[sender_id], back_populates="sent_conversations"
    )
    messages: Mapped[List["ConversationMessage"]] = relationship(
        "ConversationMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="ConversationMessage.created_at"
    )
    reports: Mapped[List["Report"]] = relationship(
        "Report", back_populates="conversation", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_conv_owner_status_last_msg", "owner_id", "status", "last_message_at"),
        Index("ix_conv_sender_status", "sender_id", "status"),
    )


class ConversationMessage(Base):
    """
    Individual message sent inside a 1-to-1 anonymous conversation.
    Maps telegram message ids for both sender and recipient to support reply targeting.
    """

    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_role: Mapped[MessageSenderRole] = mapped_column(
        Enum(MessageSenderRole, name="message_sender_role_enum", create_type=False),
        nullable=False,
    )
    # Telegram message ID when delivered to the recipient (owner or sender)
    recipient_telegram_message_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, index=True
    )
    sender_telegram_message_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True
    )
    content_type: Mapped[str] = mapped_column(String(32), default="text", nullable=False)
    text_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    media_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_seen: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )


class ChannelMessage(Base):
    """Records anonymous messages published to channels."""

    __tablename__ = "channel_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    telegram_post_message_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, index=True
    )
    content_type: Mapped[str] = mapped_column(String(32), default="text", nullable=False)
    text_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    media_file_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    nickname_used: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    seen_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )

    channel: Mapped["Channel"] = relationship("Channel", back_populates="messages")
    seen_events: Mapped[List["SeenEvent"]] = relationship(
        "SeenEvent", back_populates="channel_message", cascade="all, delete-orphan"
    )


class SeenEvent(Base):
    """
    Explicit seen event when a user clicks the 'Seen' button.
    Unique per viewer and channel_message.
    """

    __tablename__ = "seen_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    channel_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("channel_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    viewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    channel_message: Mapped["ChannelMessage"] = relationship(
        "ChannelMessage", back_populates="seen_events"
    )

    __table_args__ = (
        UniqueConstraint(
            "channel_message_id", "viewer_id", name="uq_channel_message_viewer"
        ),
    )


class Block(Base):
    """
    Conversation-level or user-level block.
    Blocker blocks Blocked.
    """

    __tablename__ = "blocks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    blocker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    blocked_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("blocker_id", "blocked_id", name="uq_blocker_blocked"),
    )


class Report(Base):
    """Abuse and harassment reports for anonymous messages and conversations."""

    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    reporter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
    )
    reported_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    reported_message_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, name="report_status_enum", create_type=False),
        default=ReportStatus.PENDING,
        nullable=False,
        index=True,
    )
    moderator_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    conversation: Mapped[Optional["Conversation"]] = relationship(
        "Conversation", back_populates="reports"
    )


class ContentFilter(Base):
    """Configurable server-side content filter rules."""

    __tablename__ = "content_filters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pattern: Mapped[str] = mapped_column(Text, nullable=False)
    is_regex: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    action: Mapped[str] = mapped_column(String(32), default="REJECT", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
