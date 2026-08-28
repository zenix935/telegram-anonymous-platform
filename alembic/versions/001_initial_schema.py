"""Initial migration for Telegram Anonymous Platform

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-08-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('first_name', sa.String(length=128), nullable=True),
        sa.Column('username', sa.String(length=128), nullable=True),
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_globally_banned', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('ban_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_users_telegram_id', 'users', ['telegram_id'], unique=True)
    op.create_index('ix_users_is_globally_banned', 'users', ['is_globally_banned'])

    # Anonymous profiles
    op.create_table(
        'anonymous_profiles',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('nickname', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('user_id'),
    )

    # Personal links
    op.create_table(
        'personal_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('random_token', sa.String(length=64), nullable=False),
        sa.Column('custom_slug', sa.String(length=64), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('owner_id'),
    )
    op.create_index('ix_personal_links_random_token', 'personal_links', ['random_token'], unique=True)
    op.create_index('ix_personal_links_custom_slug', 'personal_links', ['custom_slug'], unique=True)

    # Channels
    op.create_table(
        'channels',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('telegram_channel_id', sa.BigInteger(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('username', sa.String(length=128), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('post_template', sa.Text(), nullable=False),
        sa.Column('enable_seen_button', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_channels_telegram_channel_id', 'channels', ['telegram_channel_id'], unique=True)

    # Channel Admins
    op.create_table(
        'channel_admins',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('channel_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('channels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False, server_default='admin'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('channel_id', 'user_id', name='uq_channel_admin_channel_user'),
    )

    # Channel Links
    op.create_table(
        'channel_links',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('channel_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('channels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('random_token', sa.String(length=64), nullable=False),
        sa.Column('custom_slug', sa.String(length=64), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('channel_id'),
    )
    op.create_index('ix_channel_links_random_token', 'channel_links', ['random_token'], unique=True)
    op.create_index('ix_channel_links_custom_slug', 'channel_links', ['custom_slug'], unique=True)

    # Conversations
    op.create_table(
        'conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('owner_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sender_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='ACTIVE'),
        sa.Column('sender_alias', sa.String(length=64), nullable=False),
        sa.Column('unread_by_owner_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_conversations_owner_id', 'conversations', ['owner_id'])
    op.create_index('ix_conversations_sender_id', 'conversations', ['sender_id'])
    op.create_index('ix_conversations_status', 'conversations', ['status'])
    op.create_index('ix_conversations_last_message_at', 'conversations', ['last_message_at'])

    # Conversation Messages
    op.create_table(
        'conversation_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sender_role', sa.String(length=32), nullable=False),
        sa.Column('recipient_telegram_message_id', sa.BigInteger(), nullable=True),
        sa.Column('sender_telegram_message_id', sa.BigInteger(), nullable=True),
        sa.Column('content_type', sa.String(length=32), nullable=False, server_default='text'),
        sa.Column('text_content', sa.Text(), nullable=True),
        sa.Column('media_file_id', sa.String(length=255), nullable=True),
        sa.Column('caption', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_conv_msg_conv_id', 'conversation_messages', ['conversation_id'])
    op.create_index('ix_conv_msg_recip_tg_id', 'conversation_messages', ['recipient_telegram_message_id'])

    # Channel Messages
    op.create_table(
        'channel_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('channel_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('channels.id', ondelete='CASCADE'), nullable=False),
        sa.Column('author_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('telegram_post_message_id', sa.BigInteger(), nullable=False),
        sa.Column('content_type', sa.String(length=32), nullable=False, server_default='text'),
        sa.Column('text_content', sa.Text(), nullable=True),
        sa.Column('media_file_id', sa.String(length=255), nullable=True),
        sa.Column('nickname_used', sa.String(length=64), nullable=True),
        sa.Column('seen_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_channel_messages_channel_id', 'channel_messages', ['channel_id'])
    op.create_index('ix_channel_messages_tg_post_id', 'channel_messages', ['telegram_post_message_id'])

    # Seen Events
    op.create_table(
        'seen_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('channel_message_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('channel_messages.id', ondelete='CASCADE'), nullable=False),
        sa.Column('viewer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('channel_message_id', 'viewer_id', name='uq_channel_message_viewer'),
    )

    # Blocks
    op.create_table(
        'blocks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('blocker_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('blocked_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('blocker_id', 'blocked_id', name='uq_blocker_blocked'),
    )

    # Reports
    op.create_table(
        'reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('reporter_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reported_user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='PENDING'),
        sa.Column('moderator_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    # Content filters
    op.create_table(
        'content_filters',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('pattern', sa.Text(), nullable=False),
        sa.Column('is_regex', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('action', sa.String(length=32), nullable=False, server_default='REJECT'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('content_filters')
    op.drop_table('reports')
    op.drop_table('blocks')
    op.drop_table('seen_events')
    op.drop_table('channel_messages')
    op.drop_table('conversation_messages')
    op.drop_table('conversations')
    op.drop_table('channel_links')
    op.drop_table('channel_admins')
    op.drop_table('channels')
    op.drop_table('personal_links')
    op.drop_table('anonymous_profiles')
    op.drop_table('users')
