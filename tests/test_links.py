"""Unit and integration tests for personal and channel link management."""

import pytest
from app.services.links.link_service import LinkService
from app.database.repositories import UserRepository, ChannelRepository
from app.security.tokens import validate_custom_slug, generate_secure_token


@pytest.mark.asyncio
async def test_token_unpredictability_and_format():
    """Verify cryptographically generated tokens are high entropy, unique, and not derived from IDs."""
    tokens = set()
    for _ in range(100):
        tok = generate_secure_token(prefix="p", entropy_bytes=16)
        assert tok.startswith("p_")
        assert len(tok) >= 16
        assert tok not in tokens
        tokens.add(tok)


@pytest.mark.asyncio
async def test_slug_validation():
    """Test custom slug rules: alphanumeric, length, and reserved keywords."""
    # Valid slugs
    valid, _ = validate_custom_slug("ali_reza")
    assert valid is True
    valid, _ = validate_custom_slug("user123")
    assert valid is True

    # Too short
    valid, _ = validate_custom_slug("ab")
    assert valid is False

    # Invalid characters
    valid, _ = validate_custom_slug("ali-reza")
    assert valid is False
    valid, _ = validate_custom_slug("ali@reza")
    assert valid is False

    # Reserved keyword
    valid, err = validate_custom_slug("admin")
    assert valid is False
    assert "reserved" in err.lower()


@pytest.mark.asyncio
async def test_personal_link_lifecycle(db_session):
    """Test personal link creation, toggling, regeneration, and custom slug assignment."""
    user_repo = UserRepository(db_session)
    link_service = LinkService(db_session)

    user, _ = await user_repo.get_or_create(telegram_id=111222333, first_name="Arian")

    # 1. Create link
    link = await link_service.get_or_create_personal_link(user.id)
    assert link is not None
    assert link.random_token is not None
    assert link.is_active is True
    original_token = link.random_token

    # 2. Toggle link
    await link_service.toggle_personal_link(user.id, is_active=False)
    assert link.is_active is False

    # 3. Regenerate link
    new_link = await link_service.regenerate_personal_link(user.id)
    assert new_link.random_token != original_token

    # 4. Set custom slug
    ok, err, link = await link_service.set_personal_custom_slug(user.id, "my_custom_box")
    assert ok is True
    assert link.custom_slug == "my_custom_box"

    # 5. Prevent slug collision from another user
    user2, _ = await user_repo.get_or_create(telegram_id=444555666, first_name="Bob")
    ok2, err2, _ = await link_service.set_personal_custom_slug(user2.id, "my_custom_box")
    assert ok2 is False
    assert err2 == "taken"


@pytest.mark.asyncio
async def test_personal_vs_channel_link_separation(db_session):
    """Ensure strict isolation between personal ('p_') and channel ('c_') start links."""
    user_repo = UserRepository(db_session)
    ch_repo = ChannelRepository(db_session)
    link_service = LinkService(db_session)

    user, _ = await user_repo.get_or_create(telegram_id=1001, first_name="Alice")
    p_link = await link_service.get_or_create_personal_link(user.id)

    channel = await ch_repo.create_channel(
        telegram_channel_id=-100123456789,
        title="Test Channel",
        admin_user_id=user.id,
        random_token="secret_channel_tok",
    )

    # 1. Resolve personal link with valid prefix
    mode, resolved_p, resolved_c = await link_service.resolve_start_payload(f"p_{p_link.random_token}")
    assert mode == "personal"
    assert resolved_p.id == p_link.id
    assert resolved_c is None

    # 2. Attempting to resolve personal link with channel prefix must fail
    mode, resolved_p, resolved_c = await link_service.resolve_start_payload(f"c_{p_link.random_token}")
    assert mode == "invalid"

    # 3. Resolve channel link with valid prefix
    mode, resolved_p, resolved_c = await link_service.resolve_start_payload("c_secret_channel_tok")
    assert mode == "channel"
    assert resolved_c.id == channel.id
    assert resolved_p is None
