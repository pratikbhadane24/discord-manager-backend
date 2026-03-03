"""
Tests for the new Discord-manager API endpoints:

- POST /api/v1/auth/register
- POST /api/v1/auth/login
- GET  /api/v1/auth/discord/login
- GET  /api/v1/auth/discord/callback
- GET  /api/v1/users/me
- PATCH /api/v1/users/me
- GET  /api/v1/users/me/subscriptions
- POST /api/v1/admin/servers
- POST /api/v1/admin/tiers
- POST /api/v1/admin/sync-user/{user_id}
- POST /api/v1/admin/messages/send
- POST /api/v1/webhooks/external-payment
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx
import pytest
import respx

from app.core.security import hash_password
from app.database.models import (
    DiscordServer,
    Subscription,
    SubscriptionStatus,
    SubscriptionTier,
    User,
)

# ── Helpers ───────────────────────────────────────────────────────────────────


async def _create_user(
    email: str = "test@example.com",
    password: str = "password123",
    is_admin: bool = False,
    discord_id: str | None = None,
) -> User:
    user = User(
        email=email,
        hashed_password=hash_password(password),
        is_admin=is_admin,
        discord_id=discord_id,
    )
    await user.insert()
    return user


# ── Auth: register ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_success(async_client, mock_db):
    """Successful registration returns 201 with user profile."""
    resp = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.com", "password": "password123"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["success"] is True
    assert data["data"]["email"] == "new@example.com"


@pytest.mark.asyncio
async def test_register_duplicate_email(async_client, mock_db):
    """Duplicate email returns 409."""
    await _create_user("dup@example.com")
    resp = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "dup@example.com", "password": "password123"},
    )
    assert resp.status_code == 409


# ── Auth: login ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_success(async_client, mock_db):
    """Valid credentials return a JWT token."""
    await _create_user("login@example.com", "password123")
    resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "login@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["data"]["access_token"] is not None
    assert data["data"]["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(async_client, mock_db):
    """Wrong password returns 401."""
    await _create_user("wrongpw@example.com", "correct")
    resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpw@example.com", "password": "wrong"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_nonexistent_user(async_client, mock_db):
    """Non-existent user returns 401."""
    resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "password123"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_inactive_user(async_client, mock_db):
    """Inactive user returns 403."""
    user = await _create_user("inactive@example.com")
    user.is_active = False
    await user.save()
    resp = await async_client.post(
        "/api/v1/auth/login",
        json={"email": "inactive@example.com", "password": "password123"},
    )
    assert resp.status_code == 403


# ── Auth: Discord OAuth ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_discord_login_redirect(async_client):
    """GET /discord/login should return a redirect response."""
    resp = await async_client.get("/api/v1/auth/discord/login", follow_redirects=False)
    assert resp.status_code == 307


@pytest.mark.asyncio
@respx.mock
async def test_discord_callback_success(async_client, mock_db, auth_headers):
    """Successful OAuth callback links Discord account to user."""
    # Create user matching the JWT sub
    user = User(
        email="test_user",
        hashed_password=hash_password("pw"),
    )
    await user.insert()

    respx.post("https://discord.com/api/oauth2/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "acc",
                "refresh_token": "ref",
                "expires_in": 604800,
            },
        )
    )
    respx.get("https://discord.com/api/v10/users/@me").mock(
        return_value=httpx.Response(200, json={"id": "discord_123"})
    )

    resp = await async_client.get(
        "/api/v1/auth/discord/callback?code=authcode",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["discord_id"] == "discord_123"


@pytest.mark.asyncio
@respx.mock
async def test_discord_callback_oauth_failure(async_client, mock_db, auth_headers):
    """OAuth exchange failure returns 400."""
    respx.post("https://discord.com/api/oauth2/token").mock(
        return_value=httpx.Response(400, json={"error": "invalid_code"})
    )

    resp = await async_client.get(
        "/api/v1/auth/discord/callback?code=badcode",
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
@respx.mock
async def test_discord_callback_conflict(async_client, mock_db, auth_headers):
    """Discord ID already linked to another user returns 409."""
    # Create the user that owns the JWT
    owner = User(email="test_user", hashed_password=hash_password("pw"))
    await owner.insert()

    # Another user already linked to this discord_id
    other = User(
        email="other@example.com",
        hashed_password=hash_password("pw"),
        discord_id="discord_taken",
    )
    await other.insert()

    respx.post("https://discord.com/api/oauth2/token").mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "acc", "refresh_token": "ref", "expires_in": 604800},
        )
    )
    respx.get("https://discord.com/api/v10/users/@me").mock(
        return_value=httpx.Response(200, json={"id": "discord_taken"})
    )

    resp = await async_client.get(
        "/api/v1/auth/discord/callback?code=code",
        headers=auth_headers,
    )
    assert resp.status_code == 409


# ── Users: /me ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_me(async_client, mock_db, auth_headers):
    """GET /me returns user profile for authenticated user."""
    # The JWT sub is "test_user"
    user = User(email="test_user", hashed_password=hash_password("pw"))
    await user.insert()

    resp = await async_client.get("/api/v1/users/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == "test_user"


@pytest.mark.asyncio
async def test_get_me_not_found(async_client, mock_db, auth_headers):
    """GET /me returns 404 if user not in DB."""
    resp = await async_client.get("/api/v1/users/me", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_me(async_client, mock_db, auth_headers):
    """PATCH /me updates user email."""
    user = User(email="test_user", hashed_password=hash_password("pw"))
    await user.insert()

    resp = await async_client.patch(
        "/api/v1/users/me",
        json={"email": "updated@example.com"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == "updated@example.com"


@pytest.mark.asyncio
async def test_update_me_password(async_client, mock_db, auth_headers):
    """PATCH /me updates password."""
    user = User(email="test_user", hashed_password=hash_password("old"))
    await user.insert()

    resp = await async_client.patch(
        "/api/v1/users/me",
        json={"password": "newpassword123"},
        headers=auth_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_me_email_conflict(async_client, mock_db, auth_headers):
    """PATCH /me with already-used email returns 409."""
    user = User(email="test_user", hashed_password=hash_password("pw"))
    await user.insert()
    other = User(email="taken@example.com", hashed_password=hash_password("pw"))
    await other.insert()

    resp = await async_client.patch(
        "/api/v1/users/me",
        json={"email": "taken@example.com"},
        headers=auth_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_update_me_not_found(async_client, mock_db, auth_headers):
    """PATCH /me returns 404 if user not in DB."""
    resp = await async_client.patch(
        "/api/v1/users/me",
        json={"email": "new@example.com"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_my_subscriptions(async_client, mock_db, auth_headers):
    """GET /me/subscriptions returns list of subscriptions."""
    # No subscriptions → empty list
    resp = await async_client.get("/api/v1/users/me/subscriptions", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["data"] == []


# ── Admin: servers ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_register_server(async_client, mock_db, admin_headers):
    """Admin can register a new server."""
    resp = await async_client.post(
        "/api/v1/admin/servers",
        json={"guild_id": "guild123", "guild_name": "My Server"},
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["guild_id"] == "guild123"


@pytest.mark.asyncio
async def test_admin_register_server_duplicate(async_client, mock_db, admin_headers):
    """Registering the same guild twice returns 409."""
    await async_client.post(
        "/api/v1/admin/servers",
        json={"guild_id": "guild123", "guild_name": "My Server"},
        headers=admin_headers,
    )
    resp = await async_client.post(
        "/api/v1/admin/servers",
        json={"guild_id": "guild123", "guild_name": "My Server"},
        headers=admin_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_admin_register_server_forbidden(async_client, mock_db, auth_headers):
    """Non-admin cannot register a server."""
    resp = await async_client.post(
        "/api/v1/admin/servers",
        json={"guild_id": "guild123", "guild_name": "My Server"},
        headers=auth_headers,
    )
    assert resp.status_code == 403


# ── Admin: tiers ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_admin_create_tier(async_client, mock_db, admin_headers):
    """Admin can create a tier linked to an existing server."""
    server = DiscordServer(
        guild_id="guild1", guild_name="Test Guild", owner_id="admin1"
    )
    await server.insert()

    resp = await async_client.post(
        "/api/v1/admin/tiers",
        json={
            "server_id": str(server.id),
            "tier_name": "Gold",
            "price_id": "price_123",
            "discord_role_ids": ["role1"],
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["tier_name"] == "Gold"


@pytest.mark.asyncio
async def test_admin_create_tier_server_not_found(async_client, mock_db, admin_headers):
    """Creating a tier for non-existent server returns 404."""
    resp = await async_client.post(
        "/api/v1/admin/tiers",
        json={
            "server_id": "000000000000000000000001",
            "tier_name": "Gold",
            "price_id": "price_123",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 404


# ── Admin: sync-user ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_admin_sync_user(async_client, mock_db, admin_headers):
    """Admin can sync Discord roles for a user."""
    user = User(
        email="synced@example.com",
        hashed_password=hash_password("pw"),
        discord_id="discord_u1",
    )
    await user.insert()

    server = DiscordServer(
        guild_id="guild1", guild_name="Test Guild", owner_id=str(user.id)
    )
    await server.insert()

    tier = SubscriptionTier(
        server_id=str(server.id),
        tier_name="Gold",
        price_id="price_1",
        discord_role_ids=["role_1"],
    )
    await tier.insert()

    sub = Subscription(
        user_id=str(user.id),
        tier_id=str(tier.id),
        external_subscription_id="sub_abc",
        status=SubscriptionStatus.ACTIVE,
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
    )
    await sub.insert()

    respx.put(
        "https://discord.com/api/v10/guilds/guild1/members/discord_u1/roles/role_1"
    ).mock(return_value=httpx.Response(204))

    resp = await async_client.post(
        f"/api/v1/admin/sync-user/{user.id}",
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["roles_synced"] == ["role_1"]


@pytest.mark.asyncio
async def test_admin_sync_user_not_found(async_client, mock_db, admin_headers):
    """Syncing non-existent user returns 404."""
    resp = await async_client.post(
        "/api/v1/admin/sync-user/000000000000000000000001",
        headers=admin_headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_admin_sync_user_no_discord(async_client, mock_db, admin_headers):
    """Syncing user without linked Discord returns 400."""
    user = User(email="nodiscord@example.com", hashed_password=hash_password("pw"))
    await user.insert()

    resp = await async_client.post(
        f"/api/v1/admin/sync-user/{user.id}",
        headers=admin_headers,
    )
    assert resp.status_code == 400


# ── Admin: send message ───────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_admin_send_message(async_client, mock_db, admin_headers):
    """Admin can send a message to a Discord channel."""
    respx.post(
        "https://discord.com/api/v10/channels/chan1/messages"
    ).mock(return_value=httpx.Response(200, json={"id": "msg1", "content": "hello"}))

    resp = await async_client.post(
        "/api/v1/admin/messages/send",
        json={"channel_id": "chan1", "content": "hello"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["message_id"] == "msg1"


@pytest.mark.asyncio
@respx.mock
async def test_admin_send_message_failure(async_client, mock_db, admin_headers):
    """Discord API failure returns 502."""
    respx.post(
        "https://discord.com/api/v10/channels/chan1/messages"
    ).mock(return_value=httpx.Response(403, json={"message": "Missing Permissions"}))

    resp = await async_client.post(
        "/api/v1/admin/messages/send",
        json={"channel_id": "chan1", "content": "hello"},
        headers=admin_headers,
    )
    assert resp.status_code == 502


# ── Webhooks ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_webhook_unknown_subscription(async_client, mock_db):
    """Webhook for unknown subscription returns 200 with graceful message."""
    payload = {
        "event_type": "subscription.updated",
        "subscription_id": "sub_unknown",
        "status": "active",
    }
    resp = await async_client.post(
        "/api/v1/webhooks/external-payment",
        json=payload,
    )
    assert resp.status_code == 200
    assert "not found" in resp.json()["message"].lower()


@pytest.mark.asyncio
async def test_webhook_invalid_payload(async_client, mock_db):
    """Malformed webhook payload returns 400."""
    resp = await async_client.post(
        "/api/v1/webhooks/external-payment",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_webhook_invalid_signature(async_client, mock_db):
    """Webhook with wrong signature returns 401 when secret is set."""
    from app.core import config

    payload = json.dumps({
        "event_type": "subscription.updated",
        "subscription_id": "sub_test",
        "status": "active",
    }).encode()

    with patch.object(config.get_settings(), "WEBHOOK_SECRET", "supersecret"):
        resp = await async_client.post(
            "/api/v1/webhooks/external-payment",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": "wrongsig",
            },
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
@respx.mock
async def test_webhook_activates_subscription(async_client, mock_db):
    """Webhook status=active assigns Discord roles."""
    user = User(
        email="member@example.com",
        hashed_password=hash_password("pw"),
        discord_id="d_user1",
    )
    await user.insert()

    server = DiscordServer(
        guild_id="guild_wh", guild_name="WH Guild", owner_id=str(user.id)
    )
    await server.insert()

    tier = SubscriptionTier(
        server_id=str(server.id),
        tier_name="Gold",
        price_id="price_1",
        discord_role_ids=["role_wh"],
    )
    await tier.insert()

    sub = Subscription(
        user_id=str(user.id),
        tier_id=str(tier.id),
        external_subscription_id="sub_activate",
        status=SubscriptionStatus.PAST_DUE,
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
    )
    await sub.insert()

    respx.put(
        "https://discord.com/api/v10/guilds/guild_wh/members/d_user1/roles/role_wh"
    ).mock(return_value=httpx.Response(204))

    payload = {
        "event_type": "subscription.updated",
        "subscription_id": "sub_activate",
        "status": "active",
        "current_period_end": (
            datetime.now(timezone.utc) + timedelta(days=30)
        ).isoformat(),
    }
    resp = await async_client.post(
        "/api/v1/webhooks/external-payment", json=payload
    )
    assert resp.status_code == 200
    assert "sub_activate" in resp.json()["message"]


@pytest.mark.asyncio
@respx.mock
async def test_webhook_cancels_subscription_and_kicks(async_client, mock_db):
    """Webhook status=canceled removes roles and kicks user with no remaining subs."""
    user = User(
        email="ex_member@example.com",
        hashed_password=hash_password("pw"),
        discord_id="d_user2",
    )
    await user.insert()

    server = DiscordServer(
        guild_id="guild_cancel", guild_name="C Guild", owner_id=str(user.id)
    )
    await server.insert()

    tier = SubscriptionTier(
        server_id=str(server.id),
        tier_name="Silver",
        price_id="price_2",
        discord_role_ids=["role_c"],
    )
    await tier.insert()

    sub = Subscription(
        user_id=str(user.id),
        tier_id=str(tier.id),
        external_subscription_id="sub_cancel",
        status=SubscriptionStatus.ACTIVE,
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
    )
    await sub.insert()

    respx.delete(
        "https://discord.com/api/v10/guilds/guild_cancel/members/d_user2/roles/role_c"
    ).mock(return_value=httpx.Response(204))
    respx.delete(
        "https://discord.com/api/v10/guilds/guild_cancel/members/d_user2"
    ).mock(return_value=httpx.Response(204))

    payload = {
        "event_type": "subscription.updated",
        "subscription_id": "sub_cancel",
        "status": "canceled",
    }
    resp = await async_client.post(
        "/api/v1/webhooks/external-payment", json=payload
    )
    assert resp.status_code == 200


# ── Auth: discord_callback user not in DB ────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_discord_callback_user_deleted(async_client, mock_db, auth_headers):
    """discord_callback returns 404 when the JWT user no longer exists in the DB."""
    # The JWT sub is "test_user" but we do NOT create the User document
    respx.post("https://discord.com/api/oauth2/token").mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "acc", "refresh_token": "ref", "expires_in": 604800},
        )
    )
    respx.get("https://discord.com/api/v10/users/@me").mock(
        return_value=httpx.Response(200, json={"id": "discord_xyz"})
    )

    resp = await async_client.get(
        "/api/v1/auth/discord/callback?code=code",
        headers=auth_headers,
    )
    assert resp.status_code == 404


# ── Webhooks: _sync_discord_roles edge cases ─────────────────────────────────


@pytest.mark.asyncio
async def test_webhook_sync_no_user(async_client, mock_db):
    """Webhook gracefully handles a subscription with no matching user."""
    from app.database.models import (
        DiscordServer,
        Subscription,
        SubscriptionStatus,
        SubscriptionTier,
        User,
    )

    user = User(email="gone@example.com", hashed_password=hash_password("pw"), discord_id="d1")
    await user.insert()
    server = DiscordServer(guild_id="g_nouser", guild_name="G", owner_id=str(user.id))
    await server.insert()
    tier = SubscriptionTier(
        server_id=str(server.id), tier_name="T", price_id="p", discord_role_ids=["r"]
    )
    await tier.insert()
    sub = Subscription(
        user_id="000000000000000000000099",  # valid ObjectId that doesn't exist
        tier_id=str(tier.id),
        external_subscription_id="sub_nouser",
        status=SubscriptionStatus.PAST_DUE,
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
    )
    await sub.insert()

    payload = {
        "event_type": "subscription.updated",
        "subscription_id": "sub_nouser",
        "status": "active",
    }
    resp = await async_client.post("/api/v1/webhooks/external-payment", json=payload)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_webhook_sync_no_server(async_client, mock_db):
    """Webhook gracefully handles a tier with no matching Discord server."""
    from app.database.models import (
        Subscription,
        SubscriptionStatus,
        SubscriptionTier,
        User,
    )

    user = User(email="ns@example.com", hashed_password=hash_password("pw"), discord_id="d_ns")
    await user.insert()
    # Create tier referencing a server_id that doesn't exist in DB
    tier = SubscriptionTier(
        server_id="000000000000000000000001",
        tier_name="T",
        price_id="p",
        discord_role_ids=["r"],
    )
    await tier.insert()
    sub = Subscription(
        user_id=str(user.id),
        tier_id=str(tier.id),
        external_subscription_id="sub_noserver",
        status=SubscriptionStatus.PAST_DUE,
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
    )
    await sub.insert()

    payload = {
        "event_type": "subscription.updated",
        "subscription_id": "sub_noserver",
        "status": "active",
    }
    resp = await async_client.post("/api/v1/webhooks/external-payment", json=payload)
    assert resp.status_code == 200


@pytest.mark.asyncio
@respx.mock
async def test_webhook_role_add_failure_is_logged(async_client, mock_db):
    """Exception in add_role_to_member during webhook sync is logged, not raised."""
    user = User(
        email="rolefail@example.com",
        hashed_password=hash_password("pw"),
        discord_id="d_rf",
    )
    await user.insert()
    server = DiscordServer(
        guild_id="g_rf", guild_name="G", owner_id=str(user.id)
    )
    await server.insert()
    tier = SubscriptionTier(
        server_id=str(server.id),
        tier_name="T",
        price_id="p",
        discord_role_ids=["role_fail"],
    )
    await tier.insert()
    sub = Subscription(
        user_id=str(user.id),
        tier_id=str(tier.id),
        external_subscription_id="sub_rf",
        status=SubscriptionStatus.PAST_DUE,
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
    )
    await sub.insert()

    # Discord returns 403 — DiscordService will raise HTTPStatusError
    respx.put(
        "https://discord.com/api/v10/guilds/g_rf/members/d_rf/roles/role_fail"
    ).mock(return_value=httpx.Response(403, json={"message": "Missing Permissions"}))

    payload = {
        "event_type": "subscription.updated",
        "subscription_id": "sub_rf",
        "status": "active",
    }
    resp = await async_client.post("/api/v1/webhooks/external-payment", json=payload)
    assert resp.status_code == 200


@pytest.mark.asyncio
@respx.mock
async def test_webhook_role_remove_failure_is_logged(async_client, mock_db):
    """Exception in remove_role_from_member during webhook sync is logged, not raised."""
    user = User(
        email="removerf@example.com",
        hashed_password=hash_password("pw"),
        discord_id="d_rmrf",
    )
    await user.insert()
    server = DiscordServer(guild_id="g_rmrf", guild_name="G", owner_id=str(user.id))
    await server.insert()
    tier = SubscriptionTier(
        server_id=str(server.id),
        tier_name="T",
        price_id="p",
        discord_role_ids=["role_rmfail"],
    )
    await tier.insert()
    sub = Subscription(
        user_id=str(user.id),
        tier_id=str(tier.id),
        external_subscription_id="sub_rmrf",
        status=SubscriptionStatus.ACTIVE,
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
    )
    await sub.insert()

    respx.delete(
        "https://discord.com/api/v10/guilds/g_rmrf/members/d_rmrf/roles/role_rmfail"
    ).mock(return_value=httpx.Response(403, json={"message": "Missing Permissions"}))
    # Kick won't happen since another active sub exists in itself (after status update is
    # applied the sub becomes canceled and there are no other active subs, but we also mock
    # the kick to avoid hanging)
    respx.delete(
        "https://discord.com/api/v10/guilds/g_rmrf/members/d_rmrf"
    ).mock(return_value=httpx.Response(204))

    payload = {
        "event_type": "subscription.updated",
        "subscription_id": "sub_rmrf",
        "status": "canceled",
    }
    resp = await async_client.post("/api/v1/webhooks/external-payment", json=payload)
    assert resp.status_code == 200


@pytest.mark.asyncio
@respx.mock
async def test_webhook_kick_failure_is_logged(async_client, mock_db):
    """Exception in kick_member during webhook sync is logged, not raised."""
    user = User(
        email="kickfail@example.com",
        hashed_password=hash_password("pw"),
        discord_id="d_kf",
    )
    await user.insert()
    server = DiscordServer(guild_id="g_kf", guild_name="G", owner_id=str(user.id))
    await server.insert()
    tier = SubscriptionTier(
        server_id=str(server.id),
        tier_name="T",
        price_id="p",
        discord_role_ids=["role_kf"],
    )
    await tier.insert()
    sub = Subscription(
        user_id=str(user.id),
        tier_id=str(tier.id),
        external_subscription_id="sub_kf",
        status=SubscriptionStatus.ACTIVE,
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
    )
    await sub.insert()

    respx.delete(
        "https://discord.com/api/v10/guilds/g_kf/members/d_kf/roles/role_kf"
    ).mock(return_value=httpx.Response(204))
    # Kick returns 403 — should be caught and logged
    respx.delete(
        "https://discord.com/api/v10/guilds/g_kf/members/d_kf"
    ).mock(return_value=httpx.Response(403, json={"message": "Missing Permissions"}))

    payload = {
        "event_type": "subscription.updated",
        "subscription_id": "sub_kf",
        "status": "canceled",
    }
    resp = await async_client.post("/api/v1/webhooks/external-payment", json=payload)
    assert resp.status_code == 200


# ── Admin: sync_user edge cases ───────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_admin_sync_user_tier_not_found(async_client, mock_db, admin_headers):
    """sync_user skips subscriptions whose tier document no longer exists."""
    user = User(
        email="tiergone@example.com",
        hashed_password=hash_password("pw"),
        discord_id="d_tg",
    )
    await user.insert()

    sub = Subscription(
        user_id=str(user.id),
        tier_id="000000000000000000000001",  # non-existent tier
        external_subscription_id="sub_tiergone",
        status=SubscriptionStatus.ACTIVE,
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
    )
    await sub.insert()

    resp = await async_client.post(
        f"/api/v1/admin/sync-user/{user.id}", headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["roles_synced"] == []


@pytest.mark.asyncio
@respx.mock
async def test_admin_sync_user_server_not_found(async_client, mock_db, admin_headers):
    """sync_user skips subscriptions whose server document no longer exists."""
    user = User(
        email="servergone@example.com",
        hashed_password=hash_password("pw"),
        discord_id="d_sg",
    )
    await user.insert()

    tier = SubscriptionTier(
        server_id="000000000000000000000001",  # non-existent server
        tier_name="T",
        price_id="p",
        discord_role_ids=["r1"],
    )
    await tier.insert()

    sub = Subscription(
        user_id=str(user.id),
        tier_id=str(tier.id),
        external_subscription_id="sub_servergone",
        status=SubscriptionStatus.ACTIVE,
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
    )
    await sub.insert()

    resp = await async_client.post(
        f"/api/v1/admin/sync-user/{user.id}", headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["roles_synced"] == []


@pytest.mark.asyncio
@respx.mock
async def test_admin_sync_user_role_failure_is_logged(async_client, mock_db, admin_headers):
    """sync_user logs role-assignment failures and continues without raising."""
    user = User(
        email="syncrole_fail@example.com",
        hashed_password=hash_password("pw"),
        discord_id="d_srf",
    )
    await user.insert()
    server = DiscordServer(guild_id="g_srf", guild_name="G", owner_id=str(user.id))
    await server.insert()
    tier = SubscriptionTier(
        server_id=str(server.id),
        tier_name="T",
        price_id="p",
        discord_role_ids=["role_srf"],
    )
    await tier.insert()
    sub = Subscription(
        user_id=str(user.id),
        tier_id=str(tier.id),
        external_subscription_id="sub_srf",
        status=SubscriptionStatus.ACTIVE,
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
    )
    await sub.insert()

    # Discord returns 403 for the role assignment
    respx.put(
        "https://discord.com/api/v10/guilds/g_srf/members/d_srf/roles/role_srf"
    ).mock(return_value=httpx.Response(403, json={"message": "Missing Permissions"}))

    resp = await async_client.post(
        f"/api/v1/admin/sync-user/{user.id}", headers=admin_headers
    )
    assert resp.status_code == 200
    # Role was NOT successfully synced
    assert resp.json()["data"]["roles_synced"] == []
