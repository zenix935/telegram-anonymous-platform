"""Anonymous channel publishing service."""

import uuid
from typing import Optional, Tuple
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Channel, ChannelMessage
from app.database.repositories import ChannelRepository, SeenRepository
from app.services.templates.engine import TemplateEngine


class ChannelPublishingService:
    """Publishes anonymous messages to connected Telegram channels."""

    def __init__(self, session: AsyncSession, bot: Bot):
        self.session = session
        self.bot = bot
        self.channel_repo = ChannelRepository(session)
        self.seen_repo = SeenRepository(session)

    async def publish_anonymous_message(
        self,
        channel: Channel,
        author_id: Optional[uuid.UUID],
        content_type: str,
        text_content: Optional[str] = None,
        media_file_id: Optional[str] = None,
        nickname: Optional[str] = None,
    ) -> Tuple[bool, Optional[ChannelMessage], Optional[str]]:
        """
        Publish anonymous content to channel without forward attribution or sender info.
        Reconstructs text and media using channel's customizable template.
        """
        if not channel.is_active:
            return False, None, "channel_submission_disabled"

        from app.bot.keyboards.inline import get_seen_button_inline_keyboard

        # Render message using template
        rendered_text = TemplateEngine.render_channel_post(
            template=channel.post_template,
            message_text=text_content,
            nickname=nickname,
        )

        sent_msg = None
        try:
            if content_type == "text":
                sent_msg = await self.bot.send_message(
                    chat_id=channel.telegram_channel_id,
                    text=rendered_text,
                )
            elif content_type == "photo":
                sent_msg = await self.bot.send_photo(
                    chat_id=channel.telegram_channel_id,
                    photo=media_file_id,
                    caption=rendered_text,
                )
            elif content_type == "voice":
                sent_msg = await self.bot.send_voice(
                    chat_id=channel.telegram_channel_id,
                    voice=media_file_id,
                    caption=rendered_text,
                )
            elif content_type == "video":
                sent_msg = await self.bot.send_video(
                    chat_id=channel.telegram_channel_id,
                    video=media_file_id,
                    caption=rendered_text,
                )
            elif content_type == "document":
                sent_msg = await self.bot.send_document(
                    chat_id=channel.telegram_channel_id,
                    document=media_file_id,
                    caption=rendered_text,
                )
            elif content_type == "animation":
                sent_msg = await self.bot.send_animation(
                    chat_id=channel.telegram_channel_id,
                    animation=media_file_id,
                    caption=rendered_text,
                )
            elif content_type == "audio":
                sent_msg = await self.bot.send_audio(
                    chat_id=channel.telegram_channel_id,
                    audio=media_file_id,
                    caption=rendered_text,
                )

            if not sent_msg:
                return False, None, "channel_submission_failed"

            # Record in database
            db_msg = await self.seen_repo.record_channel_message(
                channel_id=channel.id,
                telegram_post_message_id=sent_msg.message_id,
                author_id=author_id,
                content_type=content_type,
                text_content=text_content,
                media_file_id=media_file_id,
                nickname_used=nickname,
            )
            return True, db_msg, None

        except Exception as e:
            return False, None, str(e)
