"""MongoDB connection and Beanie ODM initialisation."""

from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import get_settings

settings = get_settings()

# Module-level Motor client so it can be replaced in tests
_motor_client: AsyncIOMotorClient | None = None


def get_motor_client() -> AsyncIOMotorClient:
    """Return the current Motor client instance."""
    return _motor_client


async def init_database(motor_client: AsyncIOMotorClient | None = None) -> None:
    """
    Initialise the MongoDB connection and register Beanie document models.

    Args:
        motor_client: Optional pre-built Motor client (used in tests for
            mongomock-motor injection). When ``None`` a real Motor client is
            created from ``settings.DATABASE_URL``.
    """
    # Defer Beanie import so tests can swap the motor client first
    from beanie import init_beanie

    from app.database.models import (
        AuditLog,
        DiscordServer,
        Subscription,
        SubscriptionTier,
        User,
    )

    global _motor_client  # noqa: PLW0603

    if motor_client is not None:
        _motor_client = motor_client
    else:
        _motor_client = AsyncIOMotorClient(settings.DATABASE_URL)  # pragma: no cover

    await init_beanie(
        database=_motor_client[settings.DATABASE_NAME],
        document_models=[User, DiscordServer, SubscriptionTier, Subscription, AuditLog],
    )


async def close_database() -> None:
    """Close the MongoDB Motor client connection."""
    global _motor_client  # noqa: PLW0603
    if _motor_client is not None:
        _motor_client.close()
        _motor_client = None


async def get_database_session():
    """
    Yield the Motor database handle (for dependency injection).

    Yields:
        AsyncIOMotorDatabase instance
    """
    if _motor_client is None:
        yield None
    else:
        yield _motor_client[settings.DATABASE_NAME]

