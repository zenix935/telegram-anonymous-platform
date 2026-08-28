"""Pytest fixtures and test environment setup."""

import asyncio
import os
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database.session import Base
from app.database.models import User, AnonymousProfile, PersonalLink, Channel, ChannelLink, Conversation, ConversationStatus

# In-memory SQLite async test database
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide isolated in-memory test database session."""
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
def mock_bot():
    """Mock Aiogram Bot instance."""
    bot = AsyncMock()
    msg = AsyncMock()
    msg.message_id = 9999
    bot.send_message.return_value = msg
    bot.send_photo.return_value = msg
    bot.send_voice.return_value = msg
    bot.send_video.return_value = msg
    bot.send_document.return_value = msg
    bot.send_sticker.return_value = msg
    bot.edit_message_reply_markup.return_value = True
    return bot


@pytest_asyncio.fixture
async def mock_redis():
    """Mock Redis client with dict-based store for testing."""
    class MockRedisStore:
        def __init__(self):
            self.store = {}

        async def get(self, key):
            return self.store.get(key)

        async def set(self, key, value, ex=None, nx=False):
            if nx and key in self.store:
                return None
            self.store[key] = str(value)
            return True

        async def delete(self, key):
            if key in self.store:
                del self.store[key]
                return 1
            return 0

        def pipeline(self):
            return MockPipeline(self)

    class MockPipeline:
        def __init__(self, redis_store):
            self.redis_store = redis_store
            self.ops = []

        def incr(self, key):
            self.ops.append(("incr", key))
            return self

        def expire(self, key, seconds, nx=False):
            self.ops.append(("expire", key, seconds))
            return self

        async def execute(self):
            results = []
            for op in self.ops:
                if op[0] == "incr":
                    k = op[1]
                    val = int(self.redis_store.store.get(k, 0)) + 1
                    self.redis_store.store[k] = str(val)
                    results.append(val)
                elif op[0] == "expire":
                    results.append(True)
            self.ops = []
            return results

    return MockRedisStore()
