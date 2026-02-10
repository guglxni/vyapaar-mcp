"""Redis client for atomic budget tracking and idempotency.

CRITICAL: All budget operations MUST use atomic Redis commands (INCRBY).
Never use Read-Modify-Write patterns — they cause race conditions
when multiple agents spend concurrently.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date
from typing import Any

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class RedisClient:
    """Async Redis client wrapping atomic financial operations."""

    def __init__(self, url: str = "redis://localhost:6379/0") -> None:
        self._url = url
        self._client: aioredis.Redis | None = None  # type: ignore[type-arg]

    async def connect(self) -> None:
        """Establish Redis connection."""
        self._client = aioredis.from_url(
            self._url,
            decode_responses=True,
            socket_connect_timeout=5,
        )
        logger.info("Redis connected: %s", self._url)

    async def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            await self._client.aclose()
            logger.info("Redis disconnected")

    @property
    def client(self) -> aioredis.Redis:  # type: ignore[type-arg]
        """Get the Redis client, raising if not connected."""
        if self._client is None:
            raise RuntimeError("Redis not connected. Call connect() first.")
        return self._client

    async def ping(self) -> bool:
        """Check if Redis is reachable."""
        try:
            return bool(await self.client.ping())
        except Exception:
            return False

    # ================================================================
    # Budget Operations (ATOMIC — per SPEC §4 constraint #2)
    # ================================================================

    def _budget_key(self, agent_id: str) -> str:
        """Generate daily budget key: vyapaar:budget:{agent_id}:{YYYYMMDD}."""
        today = date.today().strftime("%Y%m%d")
        return f"vyapaar:budget:{agent_id}:{today}"

    async def check_budget_atomic(
        self, agent_id: str, amount: int, daily_limit: int
    ) -> bool:
        """Atomically check and update budget.

        Uses INCRBY (atomic) — never Read-Modify-Write.
        If the new total exceeds the limit, rolls back with DECRBY.

        Returns True if budget allows the spend, False if limit exceeded.
        """
        key = self._budget_key(agent_id)

        # Atomic increment
        new_total = await self.client.incrby(key, amount)

        if new_total > daily_limit:
            # Rollback — budget exceeded
            await self.client.decrby(key, amount)
            logger.warning(
                "Budget exceeded for %s: %d + %d > %d",
                agent_id, new_total - amount, amount, daily_limit,
            )
            return False

        # Set TTL to 25 hours (covers timezone edge cases)
        await self.client.expire(key, 90000)
        logger.info(
            "Budget OK for %s: spent %d/%d paise",
            agent_id, new_total, daily_limit,
        )
        return True

    async def get_daily_spend(self, agent_id: str) -> int:
        """Get current daily spend for an agent."""
        key = self._budget_key(agent_id)
        value = await self.client.get(key)
        return int(value) if value else 0

    # ================================================================
    # Idempotency (per SPEC §4 constraint #3)
    # ================================================================

    async def check_idempotency(self, webhook_id: str) -> bool:
        """Check if webhook has already been processed.

        Uses SETNX (atomic) — returns True if this is a NEW webhook.
        Returns False if already processed (idempotent skip).
        """
        key = f"vyapaar:idempotent:{webhook_id}"
        # SETNX returns True if key was set (new), False if exists
        is_new = await self.client.setnx(key, "processed")
        if is_new:
            # Set 48h TTL for idempotency window
            await self.client.expire(key, 172800)
        return bool(is_new)

    # ================================================================
    # Reputation Cache
    # ================================================================

    def _reputation_key(self, url: str) -> str:
        """Generate cache key for reputation check."""
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
        return f"vyapaar:reputation:{url_hash}"

    async def get_cached_reputation(self, url: str) -> dict[str, Any] | None:
        """Get cached Safe Browsing result for a URL."""
        key = self._reputation_key(url)
        cached = await self.client.get(key)
        if cached:
            return json.loads(cached)  # type: ignore[no-any-return]
        return None

    async def cache_reputation(
        self, url: str, result: dict[str, Any], ttl: int = 300
    ) -> None:
        """Cache Safe Browsing result (default 5 min TTL)."""
        key = self._reputation_key(url)
        await self.client.setex(key, ttl, json.dumps(result))
