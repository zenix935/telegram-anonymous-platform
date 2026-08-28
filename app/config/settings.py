"""Application configuration and settings using Pydantic Settings."""

from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Production application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Telegram Bot
    bot_token: str = Field(default="mock_token_for_env_test", description="Telegram Bot API Token from @BotFather")
    bot_username: str = Field(default="anonymous_bot", description="Bot username without @")
    admin_ids: List[int] = Field(default_factory=list, description="List of Telegram User IDs for system administrators")

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/telegram_anonymous_db",
        description="Async SQLAlchemy database URL (postgresql+asyncpg://...)",
    )
    db_pool_size: int = Field(default=20, description="Database connection pool size")
    db_max_overflow: int = Field(default=10, description="Database connection pool max overflow")

    # Redis
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis connection URL",
    )

    # Cryptographic / Security
    secret_key: str = Field(
        default="change-this-in-production-to-a-super-secret-key-32-chars-min",
        description="Cryptographic secret key for internal token signing/hashing",
    )

    # Link Configurations
    slug_min_length: int = Field(default=3, description="Minimum length for custom slugs")
    slug_max_length: int = Field(default=32, description="Maximum length for custom slugs")
    token_entropy_bytes: int = Field(default=16, description="Entropy bytes for random tokens")

    # Rate Limiting Defaults
    rate_limit_messages_per_minute: int = Field(default=5, description="Max messages per minute per user")
    rate_limit_messages_per_hour: int = Field(default=50, description="Max messages per hour per user")
    rate_limit_messages_per_day: int = Field(default=200, description="Max messages per day per user")
    duplicate_message_cooldown_seconds: int = Field(default=30, description="Cooldown for identical messages")

    # Content Limits
    max_message_length: int = Field(default=4000, description="Maximum allowed text message length")
    max_nickname_length: int = Field(default=30, description="Maximum allowed nickname length")
    reply_target_ttl_seconds: int = Field(default=1800, description="TTL for active reply target in seconds (30m)")

    # Environment / Debug
    environment: str = Field(default="production", description="Environment: development, staging, production")
    log_level: str = Field(default="INFO", description="Logging level: DEBUG, INFO, WARNING, ERROR")

    @field_validator("admin_ids", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                return []
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        elif isinstance(v, (int, float)):
            return [int(v)]
        return v or []

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


settings = Settings()
