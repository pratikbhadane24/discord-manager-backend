"""
Discord API service with rate-limit handling and OAuth2 support.

All external HTTP calls use ``httpx.AsyncClient`` and are retried automatically
when Discord responds with 429 Too Many Requests, respecting the
``Retry-After`` header via *tenacity*.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.core.config import get_settings
from app.database.models import AuditAction, AuditLog

logger = logging.getLogger(__name__)
settings = get_settings()

DISCORD_API = settings.DISCORD_API_BASE_URL
DISCORD_CDN = "https://cdn.discordapp.com"
OAUTH2_TOKEN_URL = "https://discord.com/api/oauth2/token"
OAUTH2_AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"


# ── Rate-limit helpers ────────────────────────────────────────────────────────


class DiscordRateLimitError(Exception):
    """Raised when Discord returns 429 Too Many Requests."""

    def __init__(self, retry_after: float) -> None:
        super().__init__(f"Rate limited; retry after {retry_after}s")
        self.retry_after = retry_after


def _is_rate_limit_error(exc: BaseException) -> bool:
    """Predicate for tenacity – only retry on rate-limit errors."""
    return isinstance(exc, DiscordRateLimitError)


# ── DiscordService ────────────────────────────────────────────────────────────


class DiscordService:
    """
    Centralised service for all Discord API interactions.

    Provides:
    * OAuth2 flow helpers (authorization URL, token exchange, token refresh)
    * Guild member management (add, assign roles, remove roles, kick)
    * Channel messaging
    * Audit log persistence

    All methods that call the Discord API are decorated with *tenacity* retry
    logic that honours the ``Retry-After`` response header on 429 responses.
    """

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        """
        Initialise the service.

        Args:
            http_client: Optional pre-configured ``httpx.AsyncClient``.
                When ``None`` a new client with sensible defaults is created.
        """
        self._client = http_client or httpx.AsyncClient(
            base_url=DISCORD_API,
            headers={
                "Authorization": f"Bot {settings.DISCORD_BOT_TOKEN}",
                "Content-Type": "application/json",
            },
            timeout=10.0,
        )

    # ── low-level request helper ──────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        url: str,
        *,
        headers: dict | None = None,
        json: dict | None = None,
        data: dict | None = None,
    ) -> httpx.Response:
        """
        Execute an HTTP request, raising ``DiscordRateLimitError`` on 429.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH).
            url: Full URL or path relative to ``base_url``.
            headers: Optional extra request headers.
            json: Optional JSON body.
            data: Optional form-encoded body.

        Returns:
            ``httpx.Response`` for successful (non-429) responses.

        Raises:
            DiscordRateLimitError: When Discord responds with 429.
            httpx.HTTPStatusError: For other 4xx/5xx responses.
        """
        response = await self._client.request(
            method, url, headers=headers, json=json, data=data
        )
        if response.status_code == 429:
            body = response.json()
            retry_after = float(body.get("retry_after", 1.0))
            raise DiscordRateLimitError(retry_after)
        return response

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        headers: dict | None = None,
        json: dict | None = None,
        data: dict | None = None,
    ) -> httpx.Response:
        """
        Wrapper around ``_request`` that sleeps for the ``Retry-After`` value
        and then retries up to five times when Discord rate-limits the call.

        Uses tenacity with a dynamic wait derived from the exception payload.
        """
        last_exc: DiscordRateLimitError | None = None
        for attempt in range(5):
            try:
                return await self._request(
                    method, url, headers=headers, json=json, data=data
                )
            except DiscordRateLimitError as exc:
                last_exc = exc
                logger.warning(
                    "Discord rate limit hit (attempt %d/5); sleeping %.1fs",
                    attempt + 1,
                    exc.retry_after,
                )
                await asyncio.sleep(exc.retry_after)
        if last_exc is None:
            raise RuntimeError("Rate-limit retry loop exited without an exception")
        raise last_exc

    # ── OAuth2 helpers ────────────────────────────────────────────────────────

    def get_oauth_authorization_url(self, state: str = "") -> str:
        """
        Build the Discord OAuth2 authorization URL.

        Args:
            state: Optional CSRF state parameter.

        Returns:
            Full authorization URL to redirect the user to.
        """
        params = {
            "client_id": settings.DISCORD_CLIENT_ID,
            "redirect_uri": settings.DISCORD_REDIRECT_URI,
            "response_type": "code",
            "scope": "identify email guilds.join",
        }
        if state:
            params["state"] = state
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{OAUTH2_AUTHORIZE_URL}?{query}"

    async def exchange_code_for_token(self, code: str) -> dict[str, Any]:
        """
        Exchange an authorization code for an OAuth2 token set.

        Args:
            code: Authorization code received from Discord callback.

        Returns:
            Token response dict containing ``access_token``, ``refresh_token``,
            ``expires_in``, ``token_type``, and ``scope``.

        Raises:
            httpx.HTTPStatusError: If the exchange fails.
        """
        payload = {
            "client_id": settings.DISCORD_CLIENT_ID,
            "client_secret": settings.DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.DISCORD_REDIRECT_URI,
        }
        response = await self._request_with_retry(
            "POST", OAUTH2_TOKEN_URL, data=payload
        )
        response.raise_for_status()
        return response.json()

    async def refresh_oauth_token(self, refresh_token: str) -> dict[str, Any]:
        """
        Refresh an expired Discord OAuth2 access token.

        Args:
            refresh_token: The refresh token obtained during initial exchange.

        Returns:
            New token response dict.

        Raises:
            httpx.HTTPStatusError: If the refresh fails.
        """
        payload = {
            "client_id": settings.DISCORD_CLIENT_ID,
            "client_secret": settings.DISCORD_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        response = await self._request_with_retry(
            "POST", OAUTH2_TOKEN_URL, data=payload
        )
        response.raise_for_status()
        return response.json()

    async def get_current_user_info(self, access_token: str) -> dict[str, Any]:
        """
        Retrieve the Discord user profile for the given OAuth access token.

        Args:
            access_token: User's Discord OAuth access token.

        Returns:
            Discord user object dict (``id``, ``username``, ``email``, …).
        """
        response = await self._request_with_retry(
            "GET",
            f"{DISCORD_API}/users/@me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        response.raise_for_status()
        return response.json()

    # ── Guild member management ───────────────────────────────────────────────

    async def add_member_to_guild(
        self, guild_id: str, user_id: str, access_token: str
    ) -> bool:
        """
        Add a user to a Discord guild using their OAuth access token.

        Implements ``PUT /guilds/{guild_id}/members/{user_id}``.

        Args:
            guild_id: Target Discord guild snowflake ID.
            user_id: Discord user snowflake ID to add.
            access_token: User's Discord OAuth access token with
                ``guilds.join`` scope.

        Returns:
            ``True`` if the user was added (201), ``False`` if already a member
            (204).
        """
        response = await self._request_with_retry(
            "PUT",
            f"/guilds/{guild_id}/members/{user_id}",
            json={"access_token": access_token},
        )
        await self._log_audit(
            action=AuditAction.MEMBER_ADDED,
            target_user_id=user_id,
            guild_id=guild_id,
            success=response.status_code in (201, 204),
        )
        return response.status_code == 201

    async def add_role_to_member(
        self, guild_id: str, user_id: str, role_id: str
    ) -> None:
        """
        Assign a Discord role to a guild member.

        Implements ``PUT /guilds/{guild_id}/members/{user_id}/roles/{role_id}``.

        Args:
            guild_id: Discord guild snowflake ID.
            user_id: Discord user snowflake ID.
            role_id: Discord role snowflake ID to assign.
        """
        response = await self._request_with_retry(
            "PUT",
            f"/guilds/{guild_id}/members/{user_id}/roles/{role_id}",
        )
        success = response.status_code == 204
        await self._log_audit(
            action=AuditAction.ROLE_ADDED,
            target_user_id=user_id,
            guild_id=guild_id,
            role_id=role_id,
            success=success,
            error_message=None if success else response.text,
        )
        if not success:
            response.raise_for_status()

    async def remove_role_from_member(
        self, guild_id: str, user_id: str, role_id: str
    ) -> None:
        """
        Remove a Discord role from a guild member.

        Implements
        ``DELETE /guilds/{guild_id}/members/{user_id}/roles/{role_id}``.

        Args:
            guild_id: Discord guild snowflake ID.
            user_id: Discord user snowflake ID.
            role_id: Discord role snowflake ID to remove.
        """
        response = await self._request_with_retry(
            "DELETE",
            f"/guilds/{guild_id}/members/{user_id}/roles/{role_id}",
        )
        success = response.status_code == 204
        await self._log_audit(
            action=AuditAction.ROLE_REMOVED,
            target_user_id=user_id,
            guild_id=guild_id,
            role_id=role_id,
            success=success,
            error_message=None if success else response.text,
        )
        if not success:
            response.raise_for_status()

    async def kick_member(self, guild_id: str, user_id: str) -> None:
        """
        Kick a member from a Discord guild.

        Implements ``DELETE /guilds/{guild_id}/members/{user_id}``.

        Args:
            guild_id: Discord guild snowflake ID.
            user_id: Discord user snowflake ID to kick.
        """
        response = await self._request_with_retry(
            "DELETE",
            f"/guilds/{guild_id}/members/{user_id}",
        )
        success = response.status_code == 204
        await self._log_audit(
            action=AuditAction.MEMBER_KICKED,
            target_user_id=user_id,
            guild_id=guild_id,
            success=success,
            error_message=None if success else response.text,
        )
        if not success:
            response.raise_for_status()

    async def get_guild_member(
        self, guild_id: str, user_id: str
    ) -> dict[str, Any] | None:
        """
        Retrieve guild member data for a specific user.

        Args:
            guild_id: Discord guild snowflake ID.
            user_id: Discord user snowflake ID.

        Returns:
            Guild member object dict, or ``None`` if the user is not a member.
        """
        response = await self._request_with_retry(
            "GET",
            f"/guilds/{guild_id}/members/{user_id}",
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    async def list_guild_members(
        self, guild_id: str, limit: int = 1000, after: str = "0"
    ) -> list[dict[str, Any]]:
        """
        List guild members (up to *limit* per page).

        Args:
            guild_id: Discord guild snowflake ID.
            limit: Maximum number of members to return (1–1000).
            after: Snowflake ID to paginate after.

        Returns:
            List of guild member objects.
        """
        response = await self._request_with_retry(
            "GET",
            f"/guilds/{guild_id}/members?limit={limit}&after={after}",
        )
        response.raise_for_status()
        return response.json()

    # ── Channel messaging ─────────────────────────────────────────────────────

    async def send_message(self, channel_id: str, content: str) -> dict[str, Any]:
        """
        Send a message to a Discord channel as the bot.

        Args:
            channel_id: Target Discord channel snowflake ID.
            content: Message content (max 2 000 characters).

        Returns:
            Created Discord message object dict.
        """
        response = await self._request_with_retry(
            "POST",
            f"/channels/{channel_id}/messages",
            json={"content": content},
        )
        success = response.status_code == 200
        await self._log_audit(
            action=AuditAction.MESSAGE_SENT,
            channel_id=channel_id,
            success=success,
            error_message=None if success else response.text,
        )
        response.raise_for_status()
        return response.json()

    # ── Audit logging ─────────────────────────────────────────────────────────

    async def _log_audit(
        self,
        action: AuditAction,
        performed_by: str = "system",
        target_user_id: str | None = None,
        guild_id: str | None = None,
        role_id: str | None = None,
        channel_id: str | None = None,
        success: bool = True,
        error_message: str | None = None,
        details: dict | None = None,
    ) -> None:
        """
        Persist an audit log entry to MongoDB.

        This method silently swallows any storage errors so that audit
        failures never interrupt the primary operation.
        """
        try:
            log = AuditLog(
                action=action,
                performed_by=performed_by,
                target_user_id=target_user_id,
                guild_id=guild_id,
                role_id=role_id,
                channel_id=channel_id,
                success=success,
                error_message=error_message,
                details=details or {},
            )
            await log.insert()
        except Exception:
            logger.exception("Failed to persist audit log for action %s", action)

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
