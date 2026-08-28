"""Security, cryptographic token generation, and validation utilities."""

import re
import secrets
import hashlib
from typing import Optional, Tuple
from app.config.settings import settings

RESERVED_SLUGS = {
    "admin", "administrator", "root", "support", "help", "bot", "channel",
    "system", "null", "undefined", "official", "moderator", "mod", "owner",
    "start", "settings", "inbox", "link", "chat", "anonymous", "direct",
    "config", "test", "dev", "api", "webhook", "telegram", "auth",
}

# Regex for safe slug: 3 to 32 alphanumeric and underscores
SLUG_PATTERN = re.compile(r"^[a-zA-Z0-9_]{3,32}$")


def generate_secure_token(prefix: str = "p", entropy_bytes: int = 16) -> str:
    """
    Generate a cryptographically secure, unguessable token with prefix.
    e.g., p_a8f9c1e4d2... or c_9b3e1f7a...
    Uses secrets.token_urlsafe to ensure high entropy.
    """
    token_entropy = secrets.token_urlsafe(entropy_bytes)
    # Sanitize token_entropy to safe urlsafe chars
    token_clean = re.sub(r"[^a-zA-Z0-9_]", "", token_entropy)
    if len(token_clean) < 12:
        token_clean = secrets.token_hex(entropy_bytes)
    return f"{prefix}_{token_clean}"


def validate_custom_slug(slug: str) -> Tuple[bool, Optional[str]]:
    """
    Validate user-provided slug against length, safe character set, and reserved keywords.
    Returns (is_valid, error_reason).
    """
    slug_clean = slug.strip().lower()
    min_len = settings.slug_min_length
    max_len = settings.slug_max_length

    if len(slug_clean) < min_len or len(slug_clean) > max_len:
        return False, f"Slug length must be between {min_len} and {max_len} characters."

    if not SLUG_PATTERN.match(slug_clean):
        return False, "Slug contains invalid characters. Use only a-z, 0-9, and _."

    if slug_clean in RESERVED_SLUGS:
        return False, f"'{slug_clean}' is a reserved system keyword."

    return True, None


def sanitize_nickname(nickname: str) -> Optional[str]:
    """
    Sanitize and validate user anonymous nickname.
    Strips dangerous characters, prevents impersonation, clamps length.
    """
    if not nickname:
        return None
    cleaned = nickname.strip()
    # Remove newlines and control characters
    cleaned = re.sub(r"[\r\n\t\x00-\x1f]", "", cleaned)
    # Clamp length
    if len(cleaned) > settings.max_nickname_length:
        cleaned = cleaned[: settings.max_nickname_length]
    
    # Check reserved names
    lower = cleaned.lower()
    if any(res in lower for res in ["admin", "official", "telegram", "مدیر", "سیستم", "پشتیبانی"]):
        return None
    return cleaned if cleaned else None


def compute_content_hash(text: str) -> str:
    """Compute sha256 hash of message text for duplicate detection."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def generate_opaque_user_id(user_uuid: str) -> str:
    """Generate a masked, pseudonymized opaque ID for users (e.g. Anon#A1B2C3D4)."""
    digest = hashlib.sha256(str(user_uuid).encode("utf-8")).hexdigest()[:8].upper()
    return f"Anon#{digest}"
