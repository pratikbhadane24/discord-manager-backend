"""MongoDB/Beanie document models for the Discord Manager platform."""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated

from beanie import Document, Indexed
from pydantic import BaseModel, EmailStr, Field
from pymongo import IndexModel


class SubscriptionStatus(str, Enum):
    """Possible states for a subscription."""

    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    TRIALING = "trialing"


class AuditAction(str, Enum):
    """Audit log action types for Discord operations."""

    ROLE_ADDED = "role_added"
    ROLE_REMOVED = "role_removed"
    MEMBER_KICKED = "member_kicked"
    MEMBER_ADDED = "member_added"
    MESSAGE_SENT = "message_sent"
    SUBSCRIPTION_ACTIVATED = "subscription_activated"
    SUBSCRIPTION_CANCELED = "subscription_canceled"


class User(Document):
    """
    Internal user document.

    Represents a platform user who may have a linked Discord account
    and one or more active subscriptions.
    """

    email: Annotated[str, Indexed(unique=True)] = Field(
        ..., description="User email address"
    )
    hashed_password: str = Field(..., description="Bcrypt-hashed password")
    discord_id: str | None = Field(
        None, description="Discord user snowflake ID linked via OAuth"
    )
    discord_access_token: str | None = Field(
        None, description="Discord OAuth access token"
    )
    discord_refresh_token: str | None = Field(
        None, description="Discord OAuth refresh token"
    )
    discord_token_expires_at: datetime | None = Field(
        None, description="Expiry datetime for the Discord access token"
    )
    is_admin: bool = Field(False, description="Whether this user has admin privileges")
    is_active: bool = Field(True, description="Whether this user account is active")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Account creation timestamp (UTC)",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last account update timestamp (UTC)",
    )

    class Settings:
        """Beanie settings for the User collection."""

        name = "users"
        indexes = [
            IndexModel([("email", 1)], unique=True),
            IndexModel([("discord_id", 1)]),
        ]


class DiscordServer(Document):
    """
    Managed Discord guild (server) document.

    Represents a Discord server registered for management by the platform.
    """

    guild_id: Annotated[str, Indexed(unique=True)] = Field(
        ..., description="Discord guild snowflake ID"
    )
    guild_name: str = Field(..., description="Human-readable guild name")
    owner_id: str = Field(
        ..., description="Internal User ID (str) of the server owner"
    )
    bot_token: str | None = Field(
        None, description="Per-guild bot token if using per-server bots"
    )
    welcome_channel_id: str | None = Field(
        None, description="Channel ID for sending welcome messages"
    )
    is_active: bool = Field(True, description="Whether this server is actively managed")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Registration timestamp (UTC)",
    )

    class Settings:
        """Beanie settings for the DiscordServer collection."""

        name = "discord_servers"
        indexes = [IndexModel([("guild_id", 1)], unique=True)]


class SubscriptionTier(Document):
    """
    Subscription tier configuration document.

    Maps an external payment plan to specific Discord roles and channel permissions.
    """

    server_id: str = Field(
        ..., description="Reference to DiscordServer document ID (str)"
    )
    tier_name: str = Field(
        ..., description="Human-readable tier name (e.g. 'Gold', 'Premium')"
    )
    price_id: str = Field(
        ...,
        description="External payment provider price ID (e.g. Stripe price_xxx)",
    )
    discord_role_ids: list[str] = Field(
        default_factory=list,
        description="List of Discord role snowflake IDs granted for this tier",
    )
    allowed_channels: list[str] = Field(
        default_factory=list,
        description="Optional list of channel IDs accessible only to this tier",
    )
    is_active: bool = Field(True, description="Whether this tier is currently offered")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Tier creation timestamp (UTC)",
    )

    class Settings:
        """Beanie settings for the SubscriptionTier collection."""

        name = "subscription_tiers"


class Subscription(Document):
    """
    Individual user subscription document.

    Tracks the relationship between a user, a tier, and the external payment provider.
    """

    user_id: str = Field(..., description="Reference to User document ID (str)")
    tier_id: str = Field(
        ..., description="Reference to SubscriptionTier document ID (str)"
    )
    external_subscription_id: str = Field(
        ..., description="External payment provider subscription ID"
    )
    status: SubscriptionStatus = Field(
        SubscriptionStatus.ACTIVE, description="Current subscription status"
    )
    current_period_end: datetime = Field(
        ...,
        description="UTC datetime when the current billing period ends",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Subscription creation timestamp (UTC)",
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last subscription update timestamp (UTC)",
    )

    class Settings:
        """Beanie settings for the Subscription collection."""

        name = "subscriptions"
        indexes = [
            IndexModel([("user_id", 1)]),
            IndexModel([("external_subscription_id", 1)], unique=True),
            IndexModel([("status", 1), ("current_period_end", 1)]),
        ]


class AuditLog(Document):
    """
    Audit log document for Discord API actions.

    Records all significant actions performed on Discord for accountability.
    """

    action: AuditAction = Field(..., description="Type of Discord action performed")
    performed_by: str = Field(
        ..., description="ID (user or 'system') that triggered the action"
    )
    target_user_id: str | None = Field(
        None, description="Discord user ID that was affected"
    )
    guild_id: str | None = Field(
        None, description="Discord guild ID where action occurred"
    )
    role_id: str | None = Field(
        None, description="Discord role ID involved in the action"
    )
    channel_id: str | None = Field(
        None, description="Discord channel ID involved in the action"
    )
    details: dict = Field(
        default_factory=dict, description="Additional action-specific metadata"
    )
    success: bool = Field(True, description="Whether the action succeeded")
    error_message: str | None = Field(
        None, description="Error details if the action failed"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the action",
    )

    class Settings:
        """Beanie settings for the AuditLog collection."""

        name = "audit_logs"
        indexes = [
            IndexModel([("timestamp", -1)]),
            IndexModel([("guild_id", 1), ("timestamp", -1)]),
        ]


# ── Pydantic request/response schemas ────────────────────────────────────────


class UserRegisterRequest(BaseModel):
    """Request body for user registration."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(
        ..., min_length=8, description="Plain-text password (min 8 chars)"
    )


class UserLoginRequest(BaseModel):
    """Request body for user login."""

    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., description="Plain-text password")


class UserProfileResponse(BaseModel):
    """Public user profile returned by the API."""

    id: str = Field(..., description="Internal user ID")
    email: str = Field(..., description="User email address")
    discord_id: str | None = Field(None, description="Linked Discord user ID")
    is_admin: bool = Field(..., description="Admin flag")
    is_active: bool = Field(..., description="Account active flag")
    created_at: datetime = Field(..., description="Account creation timestamp")


class UserUpdateRequest(BaseModel):
    """Request body for updating a user profile."""

    email: EmailStr | None = Field(None, description="New email address")
    password: str | None = Field(None, min_length=8, description="New password")


class ServerRegisterRequest(BaseModel):
    """Request body for registering a new Discord server."""

    guild_id: str = Field(..., description="Discord guild snowflake ID")
    guild_name: str = Field(..., description="Human-readable guild name")
    welcome_channel_id: str | None = Field(
        None, description="Default welcome channel ID"
    )


class TierCreateRequest(BaseModel):
    """Request body for creating a subscription tier."""

    server_id: str = Field(..., description="DiscordServer document ID")
    tier_name: str = Field(..., description="Human-readable tier name")
    price_id: str = Field(..., description="External payment plan price ID")
    discord_role_ids: list[str] = Field(
        default_factory=list, description="Discord role IDs for this tier"
    )
    allowed_channels: list[str] = Field(
        default_factory=list, description="Restricted channel IDs"
    )


class SendMessageRequest(BaseModel):
    """Request body for sending a message to a Discord channel."""

    channel_id: str = Field(..., description="Target Discord channel snowflake ID")
    content: str = Field(
        ..., max_length=2000, description="Message content (max 2000 chars)"
    )


class PaymentWebhookPayload(BaseModel):
    """Payload received from external payment provider webhook."""

    event_type: str = Field(
        ..., description="Payment event type (e.g. 'subscription.updated')"
    )
    subscription_id: str = Field(..., description="External subscription ID")
    status: str = Field(..., description="New subscription status from provider")
    current_period_end: datetime | None = Field(
        None, description="New period end datetime from provider"
    )
    customer_email: str | None = Field(
        None, description="Customer email for lookup"
    )
    price_id: str | None = Field(None, description="Price ID of the subscription")


class SubscriptionResponse(BaseModel):
    """Public subscription data returned by the API."""

    id: str = Field(..., description="Internal subscription ID")
    tier_id: str = Field(..., description="Subscription tier ID")
    external_subscription_id: str = Field(..., description="External subscription ID")
    status: SubscriptionStatus = Field(..., description="Current subscription status")
    current_period_end: datetime = Field(..., description="Period end datetime")
    created_at: datetime = Field(..., description="Subscription creation timestamp")

