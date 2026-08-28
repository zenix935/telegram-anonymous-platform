"""Personal 1-to-1 anonymous chat service."""

import uuid
from typing import Optional, Tuple
from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.messages import get_text
from app.database.models import (
    Conversation,
    ConversationMessage,
    ConversationStatus,
    MessageSenderRole,
    User,
)
from app.database.repositories import (
    ConversationRepository,
    ModerationRepository,
    PersonalLinkRepository,
    UserRepository,
)
from app.services.anonymous_chat.reply_target import ReplyTargetService


class AnonymousChatService:
    """Core service for managing 1-to-1 anonymous conversations and message delivery."""

    def __init__(
        self,
        session: AsyncSession,
        bot: Bot,
        reply_target_service: ReplyTargetService,
    ):
        self.session = session
        self.bot = bot
        self.reply_target_service = reply_target_service
        self.user_repo = UserRepository(session)
        self.personal_link_repo = PersonalLinkRepository(session)
        self.conv_repo = ConversationRepository(session)
        self.mod_repo = ModerationRepository(session)

    async def get_or_create_conversation(
        self, owner_id: uuid.UUID, sender_id: uuid.UUID, sender_nickname: Optional[str] = None
    ) -> Tuple[Optional[Conversation], Optional[str]]:
        """
        Retrieve active conversation or create a new one between owner and sender.
        Checks for self-messaging and active blocks.
        """
        if owner_id == sender_id:
            return None, "cannot_message_self"

        # Check if sender is blocked by owner
        if await self.mod_repo.is_blocked(blocker_id=owner_id, blocked_id=sender_id):
            return None, "sender_blocked"

        conv = await self.conv_repo.get_active_conversation(owner_id=owner_id, sender_id=sender_id)
        if conv:
            return conv, None

        alias = sender_nickname or "ناشناس"
        conv = await self.conv_repo.create_conversation(
            owner_id=owner_id, sender_id=sender_id, sender_alias=alias
        )
        return conv, None

    async def deliver_sender_message(
        self,
        conversation: Conversation,
        sender_user: User,
        content_type: str,
        text_content: Optional[str] = None,
        media_file_id: Optional[str] = None,
        caption: Optional[str] = None,
        sender_tg_msg_id: Optional[int] = None,
    ) -> Tuple[bool, Optional[ConversationMessage]]:
        """
        Deliver message from anonymous sender to the link owner.
        Reconstructs media anonymously without forward attribution.
        """
        owner = await self.user_repo.get_by_id(conversation.owner_id)
        if not owner or owner.is_globally_banned:
            return False, None

        from app.bot.keyboards.inline import get_reply_to_message_inline_keyboard

        # Send to owner via Bot API
        delivered_msg = None
        time_str = conversation.created_at.strftime("%H:%M")
        header = get_text(
            "incoming_anonymous_message",
            sender_alias=conversation.sender_alias,
            time=time_str,
        )

        try:
            if content_type == "text":
                formatted_text = f"{header}\n\n{text_content}"
                delivered_msg = await self.bot.send_message(
                    chat_id=owner.telegram_id,
                    text=formatted_text,
                    parse_mode="HTML",
                )
            elif content_type == "photo":
                cap = f"{header}\n\n{caption or ''}".strip()
                delivered_msg = await self.bot.send_photo(
                    chat_id=owner.telegram_id,
                    photo=media_file_id,
                    caption=cap,
                    parse_mode="HTML",
                )
            elif content_type == "voice":
                delivered_msg = await self.bot.send_voice(
                    chat_id=owner.telegram_id,
                    voice=media_file_id,
                    caption=header,
                    parse_mode="HTML",
                )
            elif content_type == "video":
                cap = f"{header}\n\n{caption or ''}".strip()
                delivered_msg = await self.bot.send_video(
                    chat_id=owner.telegram_id,
                    video=media_file_id,
                    caption=cap,
                    parse_mode="HTML",
                )
            elif content_type == "document":
                cap = f"{header}\n\n{caption or ''}".strip()
                delivered_msg = await self.bot.send_document(
                    chat_id=owner.telegram_id,
                    document=media_file_id,
                    caption=cap,
                    parse_mode="HTML",
                )
            elif content_type == "audio":
                cap = f"{header}\n\n{caption or ''}".strip()
                delivered_msg = await self.bot.send_audio(
                    chat_id=owner.telegram_id,
                    audio=media_file_id,
                    caption=cap,
                    parse_mode="HTML",
                )
            elif content_type == "animation":
                cap = f"{header}\n\n{caption or ''}".strip()
                delivered_msg = await self.bot.send_animation(
                    chat_id=owner.telegram_id,
                    animation=media_file_id,
                    caption=cap,
                    parse_mode="HTML",
                )
            elif content_type == "sticker":
                await self.bot.send_message(
                    chat_id=owner.telegram_id,
                    text=header,
                    parse_mode="HTML",
                )
                delivered_msg = await self.bot.send_sticker(
                    chat_id=owner.telegram_id,
                    sticker=media_file_id,
                )

            if delivered_msg:
                # Attach inline reply button directly to the delivered message
                kb = get_reply_to_message_inline_keyboard(delivered_msg.message_id, str(conversation.id))
                await self.bot.edit_message_reply_markup(
                    chat_id=owner.telegram_id,
                    message_id=delivered_msg.message_id,
                    reply_markup=kb,
                )

                # Persist message record
                db_msg = await self.conv_repo.add_message(
                    conversation_id=conversation.id,
                    sender_role=MessageSenderRole.SENDER,
                    content_type=content_type,
                    text_content=text_content,
                    media_file_id=media_file_id,
                    caption=caption,
                    recipient_telegram_message_id=delivered_msg.message_id,
                    sender_telegram_message_id=sender_tg_msg_id,
                )
                return True, db_msg
        except Exception:
            return False, None

        return False, None

    async def deliver_owner_reply(
        self,
        conversation: Conversation,
        owner_user: User,
        content_type: str,
        text_content: Optional[str] = None,
        media_file_id: Optional[str] = None,
        caption: Optional[str] = None,
        owner_tg_msg_id: Optional[int] = None,
    ) -> Tuple[bool, Optional[ConversationMessage]]:
        """
        Deliver message from owner to the anonymous sender.
        Routes solely to this conversation.
        """
        sender = await self.user_repo.get_by_id(conversation.sender_id)
        if not sender or sender.is_globally_banned:
            return False, None

        delivered_msg = None
        header = "💬 <b>پاسخ مخاطب به پیام ناشناس شما:</b>"

        try:
            if content_type == "text":
                formatted_text = f"{header}\n\n{text_content}"
                delivered_msg = await self.bot.send_message(
                    chat_id=sender.telegram_id,
                    text=formatted_text,
                    parse_mode="HTML",
                )
            elif content_type == "photo":
                cap = f"{header}\n\n{caption or ''}".strip()
                delivered_msg = await self.bot.send_photo(
                    chat_id=sender.telegram_id,
                    photo=media_file_id,
                    caption=cap,
                    parse_mode="HTML",
                )
            elif content_type == "voice":
                delivered_msg = await self.bot.send_voice(
                    chat_id=sender.telegram_id,
                    voice=media_file_id,
                    caption=header,
                    parse_mode="HTML",
                )
            elif content_type == "video":
                cap = f"{header}\n\n{caption or ''}".strip()
                delivered_msg = await self.bot.send_video(
                    chat_id=sender.telegram_id,
                    video=media_file_id,
                    caption=cap,
                    parse_mode="HTML",
                )
            elif content_type == "document":
                cap = f"{header}\n\n{caption or ''}".strip()
                delivered_msg = await self.bot.send_document(
                    chat_id=sender.telegram_id,
                    document=media_file_id,
                    caption=cap,
                    parse_mode="HTML",
                )
            elif content_type == "sticker":
                await self.bot.send_message(
                    chat_id=sender.telegram_id,
                    text=header,
                    parse_mode="HTML",
                )
                delivered_msg = await self.bot.send_sticker(
                    chat_id=sender.telegram_id,
                    sticker=media_file_id,
                )

            if delivered_msg:
                db_msg = await self.conv_repo.add_message(
                    conversation_id=conversation.id,
                    sender_role=MessageSenderRole.OWNER,
                    content_type=content_type,
                    text_content=text_content,
                    media_file_id=media_file_id,
                    caption=caption,
                    recipient_telegram_message_id=delivered_msg.message_id,
                    sender_telegram_message_id=owner_tg_msg_id,
                )
                return True, db_msg
        except Exception:
            return False, None

        return False, None
