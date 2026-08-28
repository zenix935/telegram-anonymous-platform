"""Active reply target management backed by Redis."""

import json
from typing import Optional
import redis.asyncio as aioredis
from app.config.settings import settings


class ReplyTargetService:
    """
    Manages explicit message-level active reply targeting for owners.
    Prevents cross-conversation message leakage.
    """

    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    def _key(self, owner_telegram_id: int) -> str:
        return f"reply_target:{owner_telegram_id}"

    async def set_active_target(
        self,
        owner_telegram_id: int,
        recipient_telegram_message_id: int,
        conversation_id: str,
        sender_alias: str,
    ) -> None:
        """Set message-level reply target with TTL."""
        data = {
            "msg_id": recipient_telegram_message_id,
            "conv_id": conversation_id,
            "alias": sender_alias,
        }
        await self.redis.set(
            self._key(owner_telegram_id),
            json.dumps(data),
            ex=settings.reply_target_ttl_seconds,
        )

    async def get_active_target(self, owner_telegram_id: int) -> Optional[dict]:
        """Retrieve current active reply target if not expired."""
        raw = await self.redis.get(self._key(owner_telegram_id))
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    async def clear_active_target(self, owner_telegram_id: int) -> None:
        """Clear active reply target when exiting reply mode or closing conversation."""
        await self.redis.delete(self._key(owner_telegram_id))
