"""
Admin endpoints (requires admin JWT role).

Routes
------
POST /servers              — register a Discord server
POST /tiers                — create a subscription tier
POST /sync-user/{user_id}  — force-sync a user's Discord roles
POST /messages/send        — send a message to a Discord channel
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import get_current_admin
from app.database.models import (
    DiscordServer,
    SendMessageRequest,
    ServerRegisterRequest,
    Subscription,
    SubscriptionStatus,
    SubscriptionTier,
    TierCreateRequest,
    User,
)
from app.models.responses import StandardResponse
from app.services.discord_service import DiscordService

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


@router.post(
    "/servers",
    response_model=StandardResponse[dict],
    status_code=status.HTTP_201_CREATED,
)
async def register_server(
    body: ServerRegisterRequest,
    current_admin: dict = Depends(get_current_admin),
):
    """
    Register a new Discord server for management.

    Args:
        body: Guild registration payload.
        current_admin: JWT payload of the authenticated admin.

    Returns:
        Created server document summary.

    Raises:
        HTTPException 409: If the guild is already registered.
    """
    existing = await DiscordServer.find_one(DiscordServer.guild_id == body.guild_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Server already registered",
        )
    server = DiscordServer(
        guild_id=body.guild_id,
        guild_name=body.guild_name,
        owner_id=current_admin["user_id"],
        welcome_channel_id=body.welcome_channel_id,
    )
    await server.insert()
    return StandardResponse(
        success=True,
        message="Server registered",
        data={"id": str(server.id), "guild_id": server.guild_id},
    )


@router.post(
    "/tiers",
    response_model=StandardResponse[dict],
    status_code=status.HTTP_201_CREATED,
)
async def create_tier(
    body: TierCreateRequest,
    current_admin: dict = Depends(get_current_admin),
):
    """
    Create a subscription tier linked to a Discord server.

    Args:
        body: Tier creation payload.
        current_admin: JWT payload of the authenticated admin.

    Returns:
        Created tier document summary.

    Raises:
        HTTPException 404: If the referenced server does not exist.
    """
    server = await DiscordServer.get(body.server_id)
    if not server:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Server not found",
        )
    tier = SubscriptionTier(
        server_id=body.server_id,
        tier_name=body.tier_name,
        price_id=body.price_id,
        discord_role_ids=body.discord_role_ids,
        allowed_channels=body.allowed_channels,
    )
    await tier.insert()
    return StandardResponse(
        success=True,
        message="Tier created",
        data={"id": str(tier.id), "tier_name": tier.tier_name},
    )


@router.post("/sync-user/{user_id}", response_model=StandardResponse[dict])
async def sync_user(
    user_id: str,
    current_admin: dict = Depends(get_current_admin),
):
    """
    Force-sync a user's Discord roles to match their active subscriptions.

    Iterates over all active subscriptions for the given user and ensures
    the corresponding Discord roles are assigned.

    Args:
        user_id: Internal User document ID.
        current_admin: JWT payload of the authenticated admin.

    Returns:
        Summary of roles synced.

    Raises:
        HTTPException 404: If the user is not found.
        HTTPException 400: If the user has no linked Discord account.
    """
    user = await User.get(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    if not user.discord_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User has no linked Discord account",
        )

    active_subs = await Subscription.find(
        Subscription.user_id == user_id,
        Subscription.status == SubscriptionStatus.ACTIVE,
    ).to_list()

    synced_roles: list[str] = []
    service = DiscordService()
    try:
        for sub in active_subs:
            tier = await SubscriptionTier.get(sub.tier_id)
            if not tier:
                continue
            server = await DiscordServer.get(tier.server_id)
            if not server:
                continue
            for role_id in tier.discord_role_ids:
                try:
                    await service.add_role_to_member(
                        server.guild_id, user.discord_id, role_id
                    )
                    synced_roles.append(role_id)
                except Exception:
                    logger.exception(
                        "Failed to sync role %s for user %s", role_id, user_id
                    )
    finally:
        await service.close()

    return StandardResponse(
        success=True,
        message=f"Synced {len(synced_roles)} role(s) for user {user_id}",
        data={"user_id": user_id, "roles_synced": synced_roles},
    )


@router.post("/messages/send", response_model=StandardResponse[dict])
async def send_message(
    body: SendMessageRequest,
    current_admin: dict = Depends(get_current_admin),
):
    """
    Send a message to a Discord channel via the bot.

    Args:
        body: Message payload (channel ID + content).
        current_admin: JWT payload of the authenticated admin.

    Returns:
        Discord message object summary.

    Raises:
        HTTPException 502: If the Discord API call fails.
    """
    service = DiscordService()
    try:
        message = await service.send_message(body.channel_id, body.content)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to send message: {exc}",
        )
    finally:
        await service.close()

    return StandardResponse(
        success=True,
        message="Message sent",
        data={"message_id": message.get("id"), "channel_id": body.channel_id},
    )
