"""Anti-spam, flood control, and rate limiting service using Redis."""

import hashlib
from typing import Optional, Tuple
import redis.asyncio as aioredis

from app.config.settings import settings


class RateLimitService:
    """Redis-backed sliding window rate limiter and duplicate message detector."""

    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    async def check_rate_limit(self, user_telegram_id: int) -> Tuple[bool, Optional[str]]:
        """
        Check minute, hour, and daily limits for a user.
        Returns (is_allowed, failure_reason).
        """
        key_min = f"rl:m:{user_telegram_id}"
        key_hr = f"rl:h:{user_telegram_id}"
        key_day = f"rl:d:{user_telegram_id}"

        pipe = self.redis.pipeline()
        pipe.incr(key_min)
        pipe.expire(key_min, 60, nx=True)
        pipe.incr(key_hr)
        pipe.expire(key_hr, 3600, nx=True)
        pipe.incr(key_day)
        pipe.expire(key_day, 86400, nx=True)

        results = await pipe.execute()
        count_min = results[0]
        count_hr = results[2]
        count_day = results[4]

        if count_min > settings.rate_limit_messages_per_minute:
            return False, "rate_limit_minute"
        if count_hr > settings.rate_limit_messages_per_hour:
            return False, "rate_limit_hour"
        if count_day > settings.rate_limit_messages_per_day:
            return False, "rate_limit_day"

        return True, None

    async def check_duplicate_message(
        self, user_telegram_id: int, content_text: str
    ) -> bool:
        """
        Detect rapid identical messages from the same user within cooldown window.
        Returns True if duplicate detected, False otherwise.
        """
        if not content_text:
            return False

        content_hash = hashlib.sha256(content_text.strip().encode("utf-8")).hexdigest()
        key = f"dup:{user_telegram_id}:{content_hash}"

        # set with NX and EX
        is_new = await self.redis.set(
            key, "1", ex=settings.duplicate_message_cooldown_seconds, nx=True
        )
        return not bool(is_new)
