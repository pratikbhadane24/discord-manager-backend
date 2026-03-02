"""
Webhook endpoints for external payment provider integration.

Routes
------
POST /external-payment — receive and process payment provider webhooks
"""

import hashlib
import hmac
import logging

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.core.config import get_settings
from app.database.models import (
    PaymentWebhookPayload,
    Subscription,
    SubscriptionStatus,
    SubscriptionTier,
    User,
)
from app.models.responses import StandardResponse
from app.services.discord_service import DiscordService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)
settings = get_settings()


def _verify_signature(payload: bytes, signature: str | None, secret: str) -> bool:
    """
    Validate an HMAC-SHA256 webhook signature.

    Args:
        payload: Raw request body bytes.
        signature: Signature header value sent by the provider.
        secret: Shared webhook secret.

    Returns:
        ``True`` if the signature matches, ``False`` otherwise.
    """
    if not signature or not secret:
        return False
    expected = hmac.new(
        secret.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/external-payment", response_model=StandardResponse[dict])
async def external_payment_webhook(
    request: Request,
    x_webhook_signature: str | None = Header(None, alias="X-Webhook-Signature"),
):
    """
    Receive an external payment webhook and synchronise subscription state.

    Validates the request signature, updates the ``Subscription`` document,
    and triggers ``DiscordService`` to assign or remove Discord roles.

    Args:
        request: Raw FastAPI request (used to read the body for signature
            verification).
        x_webhook_signature: HMAC-SHA256 signature from the payment provider.

    Returns:
        Acknowledgement response.

    Raises:
        HTTPException 400: If the request body is malformed.
        HTTPException 401: If the signature is invalid (when a secret is set).
    """
    raw_body = await request.body()

    # Verify signature when a secret is configured
    if settings.WEBHOOK_SECRET:
        valid = _verify_signature(
            raw_body, x_webhook_signature, settings.WEBHOOK_SECRET
        )
        if not valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )

    try:
        payload = PaymentWebhookPayload.model_validate_json(raw_body)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook payload: {exc}",
        )

    subscription = await Subscription.find_one(
        Subscription.external_subscription_id == payload.subscription_id
    )
    if not subscription:
        logger.warning(
            "Received webhook for unknown subscription %s", payload.subscription_id
        )
        return StandardResponse(
            success=True,
            message="Subscription not found; ignoring event",
            data={"subscription_id": payload.subscription_id},
        )

    # Map provider status to internal enum
    status_map = {
        "active": SubscriptionStatus.ACTIVE,
        "trialing": SubscriptionStatus.TRIALING,
        "past_due": SubscriptionStatus.PAST_DUE,
        "canceled": SubscriptionStatus.CANCELED,
        "cancelled": SubscriptionStatus.CANCELED,
        "unpaid": SubscriptionStatus.PAST_DUE,
    }
    new_status = status_map.get(payload.status, SubscriptionStatus.PAST_DUE)
    old_status = subscription.status
    subscription.status = new_status

    if payload.current_period_end:
        subscription.current_period_end = payload.current_period_end

    from datetime import datetime, timezone

    subscription.updated_at = datetime.now(timezone.utc)
    await subscription.save()

    # Sync Discord roles based on new status
    await _sync_discord_roles(subscription, old_status, new_status)

    return StandardResponse(
        success=True,
        message=f"Subscription {payload.subscription_id} updated to {new_status}",
        data={
            "subscription_id": payload.subscription_id,
            "new_status": new_status,
        },
    )


async def _sync_discord_roles(
    subscription: Subscription,
    old_status: SubscriptionStatus,
    new_status: SubscriptionStatus,
) -> None:
    """
    Assign or remove Discord roles based on subscription status change.

    Args:
        subscription: The updated ``Subscription`` document.
        old_status: Previous subscription status.
        new_status: New subscription status.
    """
    tier = await SubscriptionTier.get(subscription.tier_id)
    user = await User.get(subscription.user_id)

    if not tier or not user or not user.discord_id:
        return

    server = None
    from app.database.models import DiscordServer
    server = await DiscordServer.get(tier.server_id)
    if not server:
        return

    service = DiscordService()
    try:
        if new_status == SubscriptionStatus.ACTIVE:
            for role_id in tier.discord_role_ids:
                try:
                    await service.add_role_to_member(
                        server.guild_id, user.discord_id, role_id
                    )
                except Exception:
                    logger.exception(
                        "Failed to add role %s to user %s", role_id, user.discord_id
                    )
        elif new_status in (SubscriptionStatus.CANCELED,):
            for role_id in tier.discord_role_ids:
                try:
                    await service.remove_role_from_member(
                        server.guild_id, user.discord_id, role_id
                    )
                except Exception:
                    logger.exception(
                        "Failed to remove role %s from user %s",
                        role_id,
                        user.discord_id,
                    )
            # Kick member if they have no other active subscriptions
            active_subs = await Subscription.find(
                Subscription.user_id == str(user.id),
                Subscription.status == SubscriptionStatus.ACTIVE,
            ).to_list()
            if not active_subs:
                try:
                    await service.kick_member(server.guild_id, user.discord_id)
                except Exception:
                    logger.exception(
                        "Failed to kick user %s from guild %s",
                        user.discord_id,
                        server.guild_id,
                    )
    finally:
        await service.close()
