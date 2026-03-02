"""
Tests for the DiscordService.

All HTTP calls to Discord are intercepted by respx.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from app.services.discord_service import DiscordRateLimitError, DiscordService


@pytest.fixture
def service():
    """Return a DiscordService backed by a real (but intercepted) httpx client."""
    client = httpx.AsyncClient(base_url="https://discord.com/api/v10")
    svc = DiscordService(http_client=client)
    return svc


# ── OAuth2 ────────────────────────────────────────────────────────────────────


def test_get_oauth_authorization_url():
    """Authorization URL should contain required query params."""
    svc = DiscordService()
    url = svc.get_oauth_authorization_url(state="abc123")
    assert "client_id=" in url
    assert "redirect_uri=" in url
    assert "response_type=code" in url
    assert "scope=" in url
    assert "state=abc123" in url


def test_get_oauth_authorization_url_no_state():
    """Authorization URL without state should not include state param."""
    svc = DiscordService()
    url = svc.get_oauth_authorization_url()
    assert "state=" not in url


@pytest.mark.asyncio
@respx.mock
async def test_exchange_code_for_token(service):
    """Token exchange should return parsed JSON on 200."""
    respx.post("https://discord.com/api/oauth2/token").mock(
        return_value=httpx.Response(
            200,
            json={
                "access_token": "acc123",
                "refresh_token": "ref456",
                "expires_in": 604800,
                "token_type": "Bearer",
                "scope": "identify",
            },
        )
    )
    data = await service.exchange_code_for_token("mycode")
    assert data["access_token"] == "acc123"
    await service.close()


@pytest.mark.asyncio
@respx.mock
async def test_refresh_oauth_token(service):
    """Refresh token should return new token data on 200."""
    respx.post("https://discord.com/api/oauth2/token").mock(
        return_value=httpx.Response(
            200,
            json={"access_token": "new_acc", "expires_in": 604800},
        )
    )
    data = await service.refresh_oauth_token("old_ref")
    assert data["access_token"] == "new_acc"
    await service.close()


@pytest.mark.asyncio
@respx.mock
async def test_get_current_user_info(service):
    """Should fetch Discord user profile from /users/@me."""
    respx.get("https://discord.com/api/v10/users/@me").mock(
        return_value=httpx.Response(200, json={"id": "12345", "username": "testuser"})
    )
    user = await service.get_current_user_info("acc_token")
    assert user["id"] == "12345"
    await service.close()


# ── Guild member management ───────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_add_member_to_guild_201(service, mock_db):
    """add_member_to_guild should return True on 201 (user added)."""
    respx.put(
        "https://discord.com/api/v10/guilds/guild1/members/user1"
    ).mock(return_value=httpx.Response(201))
    result = await service.add_member_to_guild("guild1", "user1", "token")
    assert result is True
    await service.close()


@pytest.mark.asyncio
@respx.mock
async def test_add_member_to_guild_204(service, mock_db):
    """add_member_to_guild should return False on 204 (already member)."""
    respx.put(
        "https://discord.com/api/v10/guilds/guild1/members/user1"
    ).mock(return_value=httpx.Response(204))
    result = await service.add_member_to_guild("guild1", "user1", "token")
    assert result is False
    await service.close()


@pytest.mark.asyncio
@respx.mock
async def test_add_role_to_member(service, mock_db):
    """add_role_to_member should succeed silently on 204."""
    respx.put(
        "https://discord.com/api/v10/guilds/guild1/members/user1/roles/role1"
    ).mock(return_value=httpx.Response(204))
    await service.add_role_to_member("guild1", "user1", "role1")
    await service.close()


@pytest.mark.asyncio
@respx.mock
async def test_add_role_to_member_failure(service, mock_db):
    """add_role_to_member should raise on non-204 response."""
    respx.put(
        "https://discord.com/api/v10/guilds/guild1/members/user1/roles/role1"
    ).mock(return_value=httpx.Response(403, json={"message": "Missing Permissions"}))
    with pytest.raises(httpx.HTTPStatusError):
        await service.add_role_to_member("guild1", "user1", "role1")
    await service.close()


@pytest.mark.asyncio
@respx.mock
async def test_remove_role_from_member(service, mock_db):
    """remove_role_from_member should succeed silently on 204."""
    respx.delete(
        "https://discord.com/api/v10/guilds/guild1/members/user1/roles/role1"
    ).mock(return_value=httpx.Response(204))
    await service.remove_role_from_member("guild1", "user1", "role1")
    await service.close()


@pytest.mark.asyncio
@respx.mock
async def test_remove_role_from_member_failure(service, mock_db):
    """remove_role_from_member should raise on non-204 response."""
    respx.delete(
        "https://discord.com/api/v10/guilds/guild1/members/user1/roles/role1"
    ).mock(return_value=httpx.Response(403, json={"message": "Missing Permissions"}))
    with pytest.raises(httpx.HTTPStatusError):
        await service.remove_role_from_member("guild1", "user1", "role1")
    await service.close()


@pytest.mark.asyncio
@respx.mock
async def test_kick_member(service, mock_db):
    """kick_member should succeed silently on 204."""
    respx.delete(
        "https://discord.com/api/v10/guilds/guild1/members/user1"
    ).mock(return_value=httpx.Response(204))
    await service.kick_member("guild1", "user1")
    await service.close()


@pytest.mark.asyncio
@respx.mock
async def test_kick_member_failure(service, mock_db):
    """kick_member should raise on non-204 response."""
    respx.delete(
        "https://discord.com/api/v10/guilds/guild1/members/user1"
    ).mock(return_value=httpx.Response(403, json={"message": "Missing Permissions"}))
    with pytest.raises(httpx.HTTPStatusError):
        await service.kick_member("guild1", "user1")
    await service.close()


@pytest.mark.asyncio
@respx.mock
async def test_get_guild_member_found(service):
    """get_guild_member should return member dict on 200."""
    respx.get(
        "https://discord.com/api/v10/guilds/guild1/members/user1"
    ).mock(return_value=httpx.Response(200, json={"user": {"id": "user1"}, "roles": []}))
    member = await service.get_guild_member("guild1", "user1")
    assert member is not None
    assert member["user"]["id"] == "user1"
    await service.close()


@pytest.mark.asyncio
@respx.mock
async def test_get_guild_member_not_found(service):
    """get_guild_member should return None on 404."""
    respx.get(
        "https://discord.com/api/v10/guilds/guild1/members/unknown"
    ).mock(return_value=httpx.Response(404))
    member = await service.get_guild_member("guild1", "unknown")
    assert member is None
    await service.close()


@pytest.mark.asyncio
@respx.mock
async def test_list_guild_members(service):
    """list_guild_members should return list on 200."""
    respx.get(
        "https://discord.com/api/v10/guilds/guild1/members?limit=100&after=0"
    ).mock(return_value=httpx.Response(200, json=[{"user": {"id": "u1"}}]))
    members = await service.list_guild_members("guild1", limit=100)
    assert len(members) == 1
    await service.close()


# ── Channel messaging ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_send_message(service, mock_db):
    """send_message should return message dict on 200."""
    respx.post(
        "https://discord.com/api/v10/channels/chan1/messages"
    ).mock(return_value=httpx.Response(200, json={"id": "msg1", "content": "hello"}))
    msg = await service.send_message("chan1", "hello")
    assert msg["id"] == "msg1"
    await service.close()


@pytest.mark.asyncio
@respx.mock
async def test_send_message_failure(service, mock_db):
    """send_message should raise HTTPStatusError on non-200 response."""
    respx.post(
        "https://discord.com/api/v10/channels/chan1/messages"
    ).mock(return_value=httpx.Response(403, json={"message": "Missing Permissions"}))
    with pytest.raises(httpx.HTTPStatusError):
        await service.send_message("chan1", "hello")
    await service.close()


# ── Rate-limit handling ───────────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_rate_limit_retry_then_success(service):
    """Service should retry after 429 and succeed on subsequent attempt."""
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                429, json={"retry_after": 0.01, "global": False}
            )
        return httpx.Response(200, json={"id": "msg1"})

    respx.post(
        "https://discord.com/api/v10/channels/chan_rl/messages"
    ).mock(side_effect=side_effect)
    # Need mock_db for audit log
    # We skip audit log for rate limit test by using a service without DB
    msg = await service._request_with_retry("POST", "https://discord.com/api/v10/channels/chan_rl/messages")
    assert msg.status_code == 200
    assert call_count == 2
    await service.close()


@pytest.mark.asyncio
@respx.mock
async def test_rate_limit_exhausted(service):
    """After 5 retries still rate-limited, raise DiscordRateLimitError."""
    respx.post(
        "https://discord.com/api/v10/channels/chan_rl2/messages"
    ).mock(
        return_value=httpx.Response(429, json={"retry_after": 0.01, "global": False})
    )
    with pytest.raises(DiscordRateLimitError):
        await service._request_with_retry(
            "POST", "https://discord.com/api/v10/channels/chan_rl2/messages"
        )
    await service.close()
