"""
Background task scheduler using APScheduler.

Jobs
----
expired_subscription_sweeper   — runs every hour
discord_state_reconciler       — runs every day at midnight UTC
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

# Module-level scheduler instance
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """Return the global ``AsyncIOScheduler`` instance."""
    global _scheduler  # noqa: PLW0603
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(timezone="UTC")
    return _scheduler


# ── Job implementations ───────────────────────────────────────────────────────


async def expired_subscription_sweeper() -> None:
    """
    Hourly job: find expired subscriptions and revoke Discord access.

    Queries for all ``Subscription`` documents where
    ``current_period_end < now`` and ``status != canceled``, then:

    1. Marks the subscription as ``canceled`` in the database.
    2. Removes all associated Discord roles via ``DiscordService``.
    3. Kicks the member if they have no remaining active subscriptions.
    """
    from app.database.models import (
        DiscordServer,
        Subscription,
        SubscriptionStatus,
        SubscriptionTier,
        User,
    )
    from app.services.discord_service import DiscordService

    now = datetime.now(timezone.utc)
    logger.info("Running expired_subscription_sweeper at %s", now)

    expired = await Subscription.find(
        Subscription.current_period_end < now,
        Subscription.status != SubscriptionStatus.CANCELED,
    ).to_list()

    logger.info("Found %d expired subscription(s)", len(expired))

    for sub in expired:
        sub.status = SubscriptionStatus.CANCELED
        sub.updated_at = now
        await sub.save()

        user = await User.get(sub.user_id)
        if not user or not user.discord_id:
            continue

        tier = await SubscriptionTier.get(sub.tier_id)
        if not tier:
            continue

        server = await DiscordServer.get(tier.server_id)
        if not server:
            continue

        service = DiscordService()
        try:
            for role_id in tier.discord_role_ids:
                try:
                    await service.remove_role_from_member(
                        server.guild_id, user.discord_id, role_id
                    )
                except Exception:
                    logger.exception(
                        "Sweeper: failed to remove role %s from user %s",
                        role_id,
                        user.discord_id,
                    )

            # Kick if no active subscriptions remain
            remaining = await Subscription.find(
                Subscription.user_id == str(user.id),
                Subscription.status == SubscriptionStatus.ACTIVE,
            ).to_list()
            if not remaining:
                try:
                    await service.kick_member(server.guild_id, user.discord_id)
                    logger.info(
                        "Sweeper: kicked user %s from guild %s",
                        user.discord_id,
                        server.guild_id,
                    )
                except Exception:
                    logger.exception(
                        "Sweeper: failed to kick user %s", user.discord_id
                    )
        finally:
            await service.close()


async def discord_state_reconciler() -> None:
    """
    Daily job: reconcile Discord role state against the database.

    For each active subscription, fetches the guild member's current roles
    from Discord and re-applies any roles that are missing (e.g. manually
    removed by a server admin).
    """
    from app.database.models import (
        DiscordServer,
        Subscription,
        SubscriptionStatus,
        SubscriptionTier,
        User,
    )
    from app.services.discord_service import DiscordService

    now = datetime.now(timezone.utc)
    logger.info("Running discord_state_reconciler at %s", now)

    active_subs = await Subscription.find(
        Subscription.status == SubscriptionStatus.ACTIVE,
    ).to_list()

    logger.info("Reconciling %d active subscription(s)", len(active_subs))

    for sub in active_subs:
        user = await User.get(sub.user_id)
        if not user or not user.discord_id:
            continue

        tier = await SubscriptionTier.get(sub.tier_id)
        if not tier:
            continue

        server = await DiscordServer.get(tier.server_id)
        if not server:
            continue

        service = DiscordService()
        try:
            member = await service.get_guild_member(server.guild_id, user.discord_id)
            if member is None:
                # User is not in the guild — add them if they have an access token
                if user.discord_access_token:
                    try:
                        await service.add_member_to_guild(
                            server.guild_id,
                            user.discord_id,
                            user.discord_access_token,
                        )
                    except Exception:
                        logger.exception(
                            "Reconciler: failed to add user %s to guild %s",
                            user.discord_id,
                            server.guild_id,
                        )
                continue

            current_roles: set[str] = set(member.get("roles", []))
            for role_id in tier.discord_role_ids:
                if role_id not in current_roles:
                    try:
                        await service.add_role_to_member(
                            server.guild_id, user.discord_id, role_id
                        )
                        logger.info(
                            "Reconciler: re-assigned role %s to user %s",
                            role_id,
                            user.discord_id,
                        )
                    except Exception:
                        logger.exception(
                            "Reconciler: failed to add role %s to user %s",
                            role_id,
                            user.discord_id,
                        )
        finally:
            await service.close()


# ── Scheduler lifecycle ───────────────────────────────────────────────────────


def start_scheduler() -> AsyncIOScheduler:
    """
    Register all background jobs and start the scheduler.

    Returns:
        The started ``AsyncIOScheduler`` instance.
    """
    scheduler = get_scheduler()

    scheduler.add_job(
        expired_subscription_sweeper,
        trigger=IntervalTrigger(hours=1),
        id="expired_subscription_sweeper",
        name="Expired Subscription Sweeper",
        replace_existing=True,
        misfire_grace_time=300,
    )
    scheduler.add_job(
        discord_state_reconciler,
        trigger=CronTrigger(hour=0, minute=0, timezone="UTC"),
        id="discord_state_reconciler",
        name="Discord State Reconciler",
        replace_existing=True,
        misfire_grace_time=600,
    )

    scheduler.start()
    logger.info("APScheduler started with %d job(s)", len(scheduler.get_jobs()))
    return scheduler


def stop_scheduler() -> None:
    """Stop the global scheduler if it is running."""
    global _scheduler  # noqa: PLW0603
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
    _scheduler = None
