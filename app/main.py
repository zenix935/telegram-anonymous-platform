"""Application entry point, dispatcher assembly, and lifecycle management."""

import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from app.config.settings import settings
from app.bot.handlers import general, personal_links, personal_chat, channels, nicknames, admin
from app.bot.middlewares.core import DatabaseMiddleware, RateLimitMiddleware
from app.utils.logger import logger
from app.utils.redis import get_redis_pool, close_redis_pool
from app.database.session import engine, Base


async def init_db():
    """Create tables if not using migrations in dev mode."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def main():
    """Start Telegram Anonymous Platform bot."""
    logger.info("Initializing Telegram Anonymous Platform...")

    # Initialize Redis connection and FSM storage
    redis = await get_redis_pool()
    storage = RedisStorage(redis=redis)

    # Initialize Bot instance
    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # Initialize Dispatcher
    dp = Dispatcher(storage=storage)

    # Register Middlewares
    dp.update.middleware(DatabaseMiddleware())
    dp.message.middleware(RateLimitMiddleware())

    # Register Handler Routers
    dp.include_router(general.router)
    dp.include_router(personal_links.router)
    dp.include_router(personal_chat.router)
    dp.include_router(channels.router)
    dp.include_router(nicknames.router)
    dp.include_router(admin.router)

    # Run DB schema check
    await init_db()

    logger.info("Bot starting polling loop...")
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        logger.info("Shutting down bot...")
        await bot.session.close()
        await close_redis_pool()
        await engine.dispose()
        logger.info("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
