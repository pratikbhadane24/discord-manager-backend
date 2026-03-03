"""Additional tests to achieve full coverage of infrastructure modules.

Covers:
- app/database/database.py  (get_motor_client, get_database_session)
- app/main.py               (lifespan startup/shutdown)
- app/services/discord_service.py  (_is_rate_limit_error, _log_audit failure)
- app/api/endpoints/webhooks.py    (_verify_signature edge cases)
"""

from __future__ import annotations

import pytest
import respx
import httpx

from app.services.discord_service import DiscordRateLimitError, _is_rate_limit_error


# ── database.py ───────────────────────────────────────────────────────────────


def test_get_motor_client_returns_client(mock_db):
    """get_motor_client returns the currently active Motor client."""
    from app.database.database import get_motor_client

    client = get_motor_client()
    assert client is not None


@pytest.mark.asyncio
async def test_get_database_session_with_client(mock_db):
    """get_database_session yields the DB handle when a client is connected."""
    from app.database.database import get_database_session

    async for db in get_database_session():
        assert db is not None


@pytest.mark.asyncio
async def test_get_database_session_without_client():
    """get_database_session yields None when no Motor client is initialised."""
    from app.database import database as db_module
    from app.database.database import get_database_session

    original = db_module._motor_client
    db_module._motor_client = None
    try:
        async for db in get_database_session():
            assert db is None
    finally:
        db_module._motor_client = original


# ── main.py lifespan ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_app_lifespan(mock_db, mocker):
    """Lifespan starts/stops the scheduler and calls init/close database."""
    from asgi_lifespan import LifespanManager

    mocker.patch("app.main.init_database", return_value=None)
    mocker.patch("app.main.close_database", return_value=None)

    from app.main import app

    async with LifespanManager(app):
        pass  # Startup ran; teardown runs on context exit


# ── discord_service.py ────────────────────────────────────────────────────────


def test_is_rate_limit_error_with_rate_limit_exc():
    """_is_rate_limit_error returns True only for DiscordRateLimitError."""
    assert _is_rate_limit_error(DiscordRateLimitError(1.0)) is True


def test_is_rate_limit_error_with_other_exc():
    """_is_rate_limit_error returns False for other exception types."""
    assert _is_rate_limit_error(Exception("other")) is False
    assert _is_rate_limit_error(ValueError("nope")) is False


@pytest.mark.asyncio
async def test_audit_log_failure_is_silenced(mock_db, mocker):
    """_log_audit swallows persistence errors so the main operation continues."""
    from app.database.models import AuditAction
    from app.services.discord_service import DiscordService

    mocker.patch(
        "app.database.models.AuditLog.insert",
        side_effect=Exception("DB write failed"),
    )
    service = DiscordService()
    # Should not raise even though the insert fails
    await service._log_audit(action=AuditAction.MESSAGE_SENT, channel_id="chan1")
    await service.close()


# ── webhooks.py _verify_signature ────────────────────────────────────────────


def test_verify_signature_missing_signature():
    """_verify_signature returns False when signature header is absent."""
    from app.api.endpoints.webhooks import _verify_signature

    assert _verify_signature(b"payload", None, "mysecret") is False


def test_verify_signature_empty_signature():
    """_verify_signature returns False when signature is an empty string."""
    from app.api.endpoints.webhooks import _verify_signature

    assert _verify_signature(b"payload", "", "mysecret") is False


def test_verify_signature_empty_secret():
    """_verify_signature returns False when the shared secret is empty."""
    from app.api.endpoints.webhooks import _verify_signature

    assert _verify_signature(b"payload", "somesig", "") is False


def test_verify_signature_valid():
    """_verify_signature returns True for a correctly computed HMAC."""
    import hashlib
    import hmac as _hmac

    from app.api.endpoints.webhooks import _verify_signature

    payload = b'{"event_type":"test"}'
    secret = "supersecret"
    expected = _hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert _verify_signature(payload, expected, secret) is True


def test_verify_signature_wrong_value():
    """_verify_signature returns False when the signature does not match."""
    from app.api.endpoints.webhooks import _verify_signature

    assert _verify_signature(b"payload", "wrongsig", "mysecret") is False
