"""Structured logging configuration."""

import logging
import sys
from app.config.settings import settings


def setup_logging() -> logging.Logger:
    """Configure structured logging without leaking sensitive information."""
    log_format = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    # Silence noisy loggers
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.log_level == "DEBUG" else logging.WARNING
    )
    return logging.getLogger("telegram_anonymous_platform")


logger = setup_logging()
