"""Redis connection client and factory."""

from typing import Optional
import redis.asyncio as aioredis
from app.config.settings import settings

redis_client: Optional[aioredis.Redis] = None


async def get_redis_pool() -> aioredis.Redis:
    """Initialize or return existing Redis client."""
    global redis_client
    if redis_client is None:
        redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return redis_client


async def close_redis_pool() -> None:
    """Close Redis pool gracefully."""
    global redis_client
    if redis_client is not None:
        await redis_client.aclose()
        redis_client = None
