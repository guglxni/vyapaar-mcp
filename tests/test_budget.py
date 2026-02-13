"""Tests for atomic budget tracking and race condition prevention.

SPEC §4 Constraint #2: Use Redis INCRBY (atomic).
SPEC §15.2: Concurrent budget enforcement test.
"""

from __future__ import annotations

import asyncio

import pytest

from vyapaar_mcp.db.redis_client import RedisClient


@pytest.mark.asyncio
class TestAtomicBudget:
    """Test atomic budget operations with Redis."""

    async def test_basic_budget_check(self, fake_redis: RedisClient) -> None:
        """A single valid spend within budget should succeed."""
        result = await fake_redis.check_budget_atomic(
            agent_id="agent-001",
            amount=10000,  # ₹100
            daily_limit=500000,  # ₹5,000
        )
        assert result is True

    async def test_budget_exceeded_rejected(self, fake_redis: RedisClient) -> None:
        """Spend exceeding the daily limit should be rejected."""
        # Spend up to the limit
        await fake_redis.check_budget_atomic("agent-001", 500000, 500000)
        # This should fail
        result = await fake_redis.check_budget_atomic("agent-001", 1, 500000)
        assert result is False

    async def test_budget_tracks_cumulative(self, fake_redis: RedisClient) -> None:
        """Multiple spends should accumulate correctly."""
        await fake_redis.check_budget_atomic("agent-001", 100000, 500000)
        await fake_redis.check_budget_atomic("agent-001", 100000, 500000)
        await fake_redis.check_budget_atomic("agent-001", 100000, 500000)

        spent = await fake_redis.get_daily_spend("agent-001")
        assert spent == 300000  # 3 x 1,000 paise

    async def test_budget_rollback_on_exceed(self, fake_redis: RedisClient) -> None:
        """When budget is exceeded, the amount should be rolled back."""
        await fake_redis.check_budget_atomic("agent-001", 400000, 500000)
        # This should fail and rollback
        result = await fake_redis.check_budget_atomic("agent-001", 200000, 500000)
        assert result is False

        # Budget should still show only the first spend
        spent = await fake_redis.get_daily_spend("agent-001")
        assert spent == 400000

    async def test_concurrent_budget_enforcement(self, fake_redis: RedisClient) -> None:
        """Multiple concurrent requests should not exceed budget.

        This is the CRITICAL race condition test per SPEC §15.2.
        """
        daily_limit = 100000  # ₹1,000

        # Simulate 20 concurrent ₹100 (10000 paise) requests
        results = await asyncio.gather(
            *[
                fake_redis.check_budget_atomic("agent-race", 10000, daily_limit)
                for _ in range(20)
            ]
        )

        approved = sum(1 for r in results if r is True)
        rejected = sum(1 for r in results if r is False)

        # Exactly 10 should be approved (10 x 10000 = 100000 = limit)
        assert approved == 10
        assert rejected == 10

        # Final spend should equal the limit exactly
        spent = await fake_redis.get_daily_spend("agent-race")
        assert spent == 100000

    async def test_different_agents_independent(self, fake_redis: RedisClient) -> None:
        """Each agent should have an independent budget."""
        await fake_redis.check_budget_atomic("agent-A", 400000, 500000)
        result = await fake_redis.check_budget_atomic("agent-B", 400000, 500000)
        assert result is True  # Agent B has its own budget

    async def test_zero_amount_succeeds(self, fake_redis: RedisClient) -> None:
        """Zero-amount transaction should succeed."""
        result = await fake_redis.check_budget_atomic("agent-001", 0, 500000)
        assert result is True


@pytest.mark.asyncio
class TestIdempotency:
    """Test webhook idempotency checking."""

    async def test_new_webhook_is_new(self, fake_redis: RedisClient) -> None:
        """First time seeing a webhook should return True (new)."""
        result = await fake_redis.check_idempotency("webhook-001")
        assert result is True

    async def test_replay_detected(self, fake_redis: RedisClient) -> None:
        """Second time seeing same webhook should return False (replay)."""
        await fake_redis.check_idempotency("webhook-002")
        result = await fake_redis.check_idempotency("webhook-002")
        assert result is False

    async def test_different_webhooks_independent(self, fake_redis: RedisClient) -> None:
        """Different webhook IDs should be independent."""
        await fake_redis.check_idempotency("webhook-A")
        result = await fake_redis.check_idempotency("webhook-B")
        assert result is True


@pytest.mark.asyncio
class TestReputationCache:
    """Test reputation result caching."""

    async def test_cache_miss_returns_none(self, fake_redis: RedisClient) -> None:
        """Non-cached URL should return None."""
        result = await fake_redis.get_cached_reputation("https://unknown.com")
        assert result is None

    async def test_cache_hit_returns_data(self, fake_redis: RedisClient) -> None:
        """Cached URL should return stored data."""
        data = {"safe": True, "threats": []}
        await fake_redis.cache_reputation("https://safe.com", data, ttl=300)

        result = await fake_redis.get_cached_reputation("https://safe.com")
        assert result == data
