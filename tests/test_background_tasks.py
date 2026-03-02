"""Tests for background scheduler jobs."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

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


async def _make_active_sub(discord_id: str = "d1", guild_id: str = "g1") -> tuple:
    user = User(
        email=f"{discord_id}@example.com",
        hashed_password=hash_password("pw"),
        discord_id=discord_id,
    )
    await user.insert()

    server = DiscordServer(
        guild_id=guild_id, guild_name="Test", owner_id=str(user.id)
    )
    await server.insert()

    tier = SubscriptionTier(
        server_id=str(server.id),
        tier_name="Gold",
        price_id="price_1",
        discord_role_ids=["role1"],
    )
    await tier.insert()

    sub = Subscription(
        user_id=str(user.id),
        tier_id=str(tier.id),
        external_subscription_id=f"sub_{discord_id}",
        status=SubscriptionStatus.ACTIVE,
        current_period_end=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    await sub.insert()
    return user, server, tier, sub


# ── expired_subscription_sweeper ─────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_sweeper_cancels_expired_subscription(mock_db):
    """Sweeper should cancel expired subscriptions and remove roles."""
    from app.core.scheduler import expired_subscription_sweeper

    user, server, tier, sub = await _make_active_sub("d_sweep1", "g_sweep1")

    respx.delete(
        "https://discord.com/api/v10/guilds/g_sweep1/members/d_sweep1/roles/role1"
    ).mock(return_value=httpx.Response(204))
    respx.delete(
        "https://discord.com/api/v10/guilds/g_sweep1/members/d_sweep1"
    ).mock(return_value=httpx.Response(204))

    await expired_subscription_sweeper()

    refreshed = await Subscription.get(sub.id)
    assert refreshed.status == SubscriptionStatus.CANCELED


@pytest.mark.asyncio
async def test_sweeper_no_expired_subscriptions(mock_db):
    """Sweeper does nothing when no subscriptions are expired."""
    from app.core.scheduler import expired_subscription_sweeper

    user = User(email="active@example.com", hashed_password=hash_password("pw"))
    await user.insert()
    server = DiscordServer(guild_id="g_active", guild_name="G", owner_id=str(user.id))
    await server.insert()
    tier = SubscriptionTier(
        server_id=str(server.id), tier_name="T", price_id="p", discord_role_ids=[]
    )
    await tier.insert()
    sub = Subscription(
        user_id=str(user.id),
        tier_id=str(tier.id),
        external_subscription_id="sub_active_ok",
        status=SubscriptionStatus.ACTIVE,
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
    )
    await sub.insert()

    await expired_subscription_sweeper()  # Should be a no-op

    refreshed = await Subscription.get(sub.id)
    assert refreshed.status == SubscriptionStatus.ACTIVE


@pytest.mark.asyncio
@respx.mock
async def test_sweeper_skips_user_without_discord(mock_db):
    """Sweeper skips users with no linked Discord account."""
    from app.core.scheduler import expired_subscription_sweeper

    user = User(email="nodiscord@example.com", hashed_password=hash_password("pw"))
    await user.insert()
    server = DiscordServer(guild_id="g_nd", guild_name="G", owner_id=str(user.id))
    await server.insert()
    tier = SubscriptionTier(
        server_id=str(server.id), tier_name="T", price_id="p", discord_role_ids=["r1"]
    )
    await tier.insert()
    sub = Subscription(
        user_id=str(user.id),
        tier_id=str(tier.id),
        external_subscription_id="sub_nd",
        status=SubscriptionStatus.ACTIVE,
        current_period_end=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    await sub.insert()

    await expired_subscription_sweeper()

    refreshed = await Subscription.get(sub.id)
    assert refreshed.status == SubscriptionStatus.CANCELED  # Status still updated


# ── discord_state_reconciler ──────────────────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_reconciler_reassigns_missing_role(mock_db):
    """Reconciler re-assigns a role that was manually removed."""
    from app.core.scheduler import discord_state_reconciler

    user = User(
        email="reconcile@example.com",
        hashed_password=hash_password("pw"),
        discord_id="d_rec1",
    )
    await user.insert()
    server = DiscordServer(
        guild_id="g_rec1", guild_name="G", owner_id=str(user.id)
    )
    await server.insert()
    tier = SubscriptionTier(
        server_id=str(server.id),
        tier_name="Gold",
        price_id="price_r",
        discord_role_ids=["role_missing"],
    )
    await tier.insert()
    sub = Subscription(
        user_id=str(user.id),
        tier_id=str(tier.id),
        external_subscription_id="sub_rec1",
        status=SubscriptionStatus.ACTIVE,
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
    )
    await sub.insert()

    # Member exists but does NOT have the role
    respx.get(
        "https://discord.com/api/v10/guilds/g_rec1/members/d_rec1"
    ).mock(
        return_value=httpx.Response(
            200, json={"user": {"id": "d_rec1"}, "roles": []}
        )
    )
    respx.put(
        "https://discord.com/api/v10/guilds/g_rec1/members/d_rec1/roles/role_missing"
    ).mock(return_value=httpx.Response(204))

    await discord_state_reconciler()


@pytest.mark.asyncio
@respx.mock
async def test_reconciler_adds_missing_member(mock_db):
    """Reconciler adds member to guild when not present."""
    from app.core.scheduler import discord_state_reconciler

    user = User(
        email="missing@example.com",
        hashed_password=hash_password("pw"),
        discord_id="d_missing",
        discord_access_token="acc_token",
    )
    await user.insert()
    server = DiscordServer(
        guild_id="g_miss", guild_name="G", owner_id=str(user.id)
    )
    await server.insert()
    tier = SubscriptionTier(
        server_id=str(server.id),
        tier_name="Gold",
        price_id="price_m",
        discord_role_ids=["role_m"],
    )
    await tier.insert()
    sub = Subscription(
        user_id=str(user.id),
        tier_id=str(tier.id),
        external_subscription_id="sub_miss",
        status=SubscriptionStatus.ACTIVE,
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
    )
    await sub.insert()

    # Member not in guild
    respx.get(
        "https://discord.com/api/v10/guilds/g_miss/members/d_missing"
    ).mock(return_value=httpx.Response(404))
    respx.put(
        "https://discord.com/api/v10/guilds/g_miss/members/d_missing"
    ).mock(return_value=httpx.Response(201))

    await discord_state_reconciler()


@pytest.mark.asyncio
async def test_reconciler_skips_no_discord_id(mock_db):
    """Reconciler skips users with no discord_id."""
    from app.core.scheduler import discord_state_reconciler

    user = User(email="nd@example.com", hashed_password=hash_password("pw"))
    await user.insert()
    server = DiscordServer(guild_id="g_nd2", guild_name="G", owner_id=str(user.id))
    await server.insert()
    tier = SubscriptionTier(
        server_id=str(server.id), tier_name="T", price_id="p", discord_role_ids=["r"]
    )
    await tier.insert()
    sub = Subscription(
        user_id=str(user.id),
        tier_id=str(tier.id),
        external_subscription_id="sub_nd2",
        status=SubscriptionStatus.ACTIVE,
        current_period_end=datetime.now(timezone.utc) + timedelta(days=30),
    )
    await sub.insert()

    # Should complete without error
    await discord_state_reconciler()


# ── Scheduler lifecycle ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_and_stop_scheduler():
    """start_scheduler / stop_scheduler should not raise."""
    from app.core import scheduler as sched_module
    from app.core.scheduler import start_scheduler, stop_scheduler

    scheduler = start_scheduler()
    assert scheduler.running
    jobs = scheduler.get_jobs()
    job_ids = [j.id for j in jobs]
    assert "expired_subscription_sweeper" in job_ids
    assert "discord_state_reconciler" in job_ids
    stop_scheduler()
    # After stop_scheduler, the module-level _scheduler is reset to None
    assert sched_module._scheduler is None
