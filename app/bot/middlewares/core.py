"""Aiogram middlewares for DB session injection, user sync, and rate-limiting."""

from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from app.config.settings import settings
from app.config.messages import get_text
from app.database.session import async_session_factory
from app.database.repositories import UserRepository
from app.services.moderation.rate_limiter import RateLimitService
from app.utils.redis import get_redis_pool
from app.utils.logger import logger


class DatabaseMiddleware(BaseMiddleware):
    """Injects async SQLAlchemy session and current user record into event data."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        async with async_session_factory() as session:
            data["db_session"] = session

            # Extract Telegram user
            from_user = getattr(event, "from_user", None)
            if from_user and not from_user.is_bot:
                user_repo = UserRepository(session)
                is_admin = from_user.id in settings.admin_ids
                db_user, _ = await user_repo.get_or_create(
                    telegram_id=from_user.id,
                    first_name=from_user.first_name,
                    username=from_user.username,
                    is_admin=is_admin,
                )
                data["db_user"] = db_user

                # Reject globally banned users
                if db_user.is_globally_banned:
                    if isinstance(event, Message):
                        await event.answer("⛔ حساب شما در این ربات مسدود شده است.")
                    elif isinstance(event, CallbackQuery):
                        await event.answer("⛔ حساب شما در این ربات مسدود شده است.", show_alert=True)
                    return

            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception as e:
                await session.rollback()
                logger.error(f"Error handling event: {e}", exc_info=True)
                raise


class RateLimitMiddleware(BaseMiddleware):
    """Applies Redis-backed sliding window rate limits on incoming messages."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if isinstance(event, Message) and event.from_user and not event.from_user.is_bot:
            # Bypass rate limit for global admins
            if event.from_user.id in settings.admin_ids:
                return await handler(event, data)

            redis = await get_redis_pool()
            limiter = RateLimitService(redis)
            is_allowed, _ = await limiter.check_rate_limit(event.from_user.id)
            if not is_allowed:
                await event.answer(get_text("rate_limit_exceeded"))
                return

        return await handler(event, data)
