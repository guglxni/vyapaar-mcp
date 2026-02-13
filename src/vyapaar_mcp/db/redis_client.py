"""Redis client for atomic budget tracking, rate limiting, and idempotency.

CRITICAL: All budget operations MUST use atomic Redis commands.
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

    # Lua script: atomically check budget limit and increment if within bounds.
    # Returns 1 (OK) or 0 (exceeded). Never leaves partial state.
    _BUDGET_LUA = """
local key = KEYS[1]
local amount = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local ttl = tonumber(ARGV[3])
local current = tonumber(redis.call('GET', key) or '0')
if current + amount > limit then
    return 0
end
redis.call('INCRBY', key, amount)
redis.call('EXPIRE', key, ttl)
return 1
"""

    def _budget_key(self, agent_id: str) -> str:
        """Generate daily budget key: vyapaar:budget:{agent_id}:{YYYYMMDD}."""
        today = date.today().strftime("%Y%m%d")
        return f"vyapaar:budget:{agent_id}:{today}"

    async def check_budget_atomic(
        self, agent_id: str, amount: int, daily_limit: int
    ) -> bool:
        """Atomically check and update budget using a Lua script.

        The entire check-and-increment is a single atomic Redis op.
        No rollback needed — if the limit would be exceeded, the
        increment never happens.

        Returns True if budget allows the spend, False if limit exceeded.
        """
        key = self._budget_key(agent_id)

        result = await self.client.eval(
            self._BUDGET_LUA,
            1,       # number of KEYS
            key,     # KEYS[1]
            str(amount),       # ARGV[1]
            str(daily_limit),  # ARGV[2]
            str(90000),        # ARGV[3] — TTL 25 hours
        )

        if result == 1:
            logger.info(
                "Budget OK for %s: +%d paise (limit %d)",
                agent_id, amount, daily_limit,
            )
            return True
        else:
            logger.warning(
                "Budget exceeded for %s: +%d would exceed limit %d",
                agent_id, amount, daily_limit,
            )
            return False

    async def get_daily_spend(self, agent_id: str) -> int:
        """Get current daily spend for an agent."""
        key = self._budget_key(agent_id)
        value = await self.client.get(key)
        return int(value) if value else 0

    async def rollback_budget(self, agent_id: str, amount: int) -> None:
        """Roll back a previously committed budget increment.

        Used when a payout is rejected AFTER the budget check
        passed (e.g., domain blocked, reputation fail).
        """
        key = self._budget_key(agent_id)
        await self.client.decrby(key, amount)
        logger.info("Budget rollback for %s: -%d paise", agent_id, amount)

    # ================================================================
    # Rate Limiting (sliding window per CODE_REVIEW §5.2)
    # ================================================================

    # Lua script: sliding window rate limiter.
    # Removes expired entries, counts current, adds new if under limit.
    # Returns: [allowed (0/1), current_count, ttl_remaining]
    _RATE_LIMIT_LUA = """
local key = KEYS[1]
local window = tonumber(ARGV[1])
local max_requests = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local window_start = now - window

-- Remove expired entries
redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

-- Count current entries in window
local current = redis.call('ZCARD', key)

if current >= max_requests then
    local ttl = redis.call('TTL', key)
    return {0, current, ttl}
end

-- Add new entry with current timestamp as score
redis.call('ZADD', key, now, now .. ':' .. math.random(1000000))
redis.call('EXPIRE', key, window + 1)

return {1, current + 1, window}
"""

    def _rate_limit_key(self, agent_id: str) -> str:
        """Generate rate limit key: vyapaar:ratelimit:{agent_id}."""
        return f"vyapaar:ratelimit:{agent_id}"

    async def check_rate_limit(
        self,
        agent_id: str,
        max_requests: int,
        window_seconds: int = 60,
    ) -> tuple[bool, int]:
        """Check if an agent is within their rate limit.

        Uses a Redis sorted set as a sliding window counter.
        Fully atomic via Lua script.

        Args:
            agent_id: The agent to check.
            max_requests: Maximum requests allowed in window.
            window_seconds: Sliding window size in seconds.

        Returns:
            Tuple of (allowed: bool, current_count: int).
        """
        import time as _time

        key = self._rate_limit_key(agent_id)
        now = _time.time()

        result = await self.client.eval(
            self._RATE_LIMIT_LUA,
            1,
            key,
            str(window_seconds),
            str(max_requests),
            str(now),
        )

        allowed = bool(result[0])
        current_count = int(result[1])

        if not allowed:
            logger.warning(
                "Rate limit exceeded for %s: %d/%d in %ds window",
                agent_id, current_count, max_requests, window_seconds,
            )
        return allowed, current_count

    # ================================================================
    # Idempotency (per SPEC §4 constraint #3)
    # ================================================================

    async def check_idempotency(self, webhook_id: str) -> bool:
        """Check if webhook has already been processed.

        Uses atomic SET with NX+EX — returns True if this is a NEW webhook.
        Returns False if already processed (idempotent skip).

        The NX and EX flags are set in a single command to avoid a
        race where the key is created but the TTL is never applied.
        """
        key = f"vyapaar:idempotent:{webhook_id}"
        # Atomic: set only if not exists, with 48h TTL
        is_new = await self.client.set(key, "processed", nx=True, ex=172800)
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
