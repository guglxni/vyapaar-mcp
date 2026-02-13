"""Core Governance Engine — orchestrates the entire decision pipeline.

Implements the Decision Matrix from SPEC §8:
1. Verify signature (ingress layer handles this)
2. Check idempotency (Redis SETNX)
3. Fetch agent policy (PostgreSQL)
4. Check budget (Redis INCRBY atomic)
5. Check per-transaction limit
6. Check domain blacklist/whitelist
7. Check vendor reputation (Google Safe Browsing)
8. Check approval threshold (human-in-the-loop trigger)
9. Final decision: APPROVE / REJECT / HOLD
"""

from __future__ import annotations

import logging
import time
from urllib.parse import urlparse

from vyapaar_mcp.db.postgres import PostgresClient
from vyapaar_mcp.db.redis_client import RedisClient
from vyapaar_mcp.models import (
    Decision,
    GovernanceResult,
    PayoutEntity,
    ReasonCode,
)
from vyapaar_mcp.observability import metrics
from vyapaar_mcp.reputation.safe_browsing import SafeBrowsingChecker

logger = logging.getLogger(__name__)


class GovernanceEngine:
    """Core decision engine for payout governance.

    Evaluates a payout against all policy checks and returns
    a final APPROVE / REJECT / HOLD decision.
    """

    def __init__(
        self,
        redis: RedisClient,
        postgres: PostgresClient,
        safe_browsing: SafeBrowsingChecker,
        rate_limit_max: int = 10,
        rate_limit_window: int = 60,
    ) -> None:
        self._redis = redis
        self._postgres = postgres
        self._safe_browsing = safe_browsing
        self._rate_limit_max = rate_limit_max
        self._rate_limit_window = rate_limit_window

    async def evaluate(
        self,
        payout: PayoutEntity,
        agent_id: str,
        vendor_url: str | None = None,
    ) -> GovernanceResult:
        """Run the full governance pipeline on a payout.

        Returns a GovernanceResult with the decision, reason, and metadata.
        """
        start_time = time.monotonic()

        # --- Step 1: Fetch agent policy ---
        policy = await self._postgres.get_agent_policy(agent_id)
        if policy is None:
            return self._result(
                payout, agent_id, start_time,
                Decision.REJECTED, ReasonCode.NO_POLICY,
                f"No spending policy found for agent '{agent_id}'",
            )

        # --- Step 2: Per-transaction limit check ---
        if policy.per_txn_limit is not None and payout.amount > policy.per_txn_limit:
            return self._result(
                payout, agent_id, start_time,
                Decision.REJECTED, ReasonCode.TXN_LIMIT_EXCEEDED,
                f"Amount {payout.amount} paise exceeds per-txn limit"
                f" of {policy.per_txn_limit} paise",
            )

        # --- Step 2.5: Rate limit check (sliding window) ---
        if self._rate_limit_max > 0:
            allowed, count = await self._redis.check_rate_limit(
                agent_id,
                max_requests=self._rate_limit_max,
                window_seconds=self._rate_limit_window,
            )
            metrics.record_rate_limit_check(allowed=allowed)
            if not allowed:
                return self._result(
                    payout, agent_id, start_time,
                    Decision.REJECTED, ReasonCode.RATE_LIMITED,
                    f"Rate limit exceeded: {count}/{self._rate_limit_max}"
                    f" requests in {self._rate_limit_window}s window",
                )

        # --- Step 3: Daily budget check (ATOMIC Redis) ---
        budget_ok = await self._redis.check_budget_atomic(
            agent_id, payout.amount, policy.daily_limit
        )
        metrics.record_budget_check(ok=budget_ok)
        if not budget_ok:
            current_spend = await self._redis.get_daily_spend(agent_id)
            return self._result(
                payout, agent_id, start_time,
                Decision.REJECTED, ReasonCode.LIMIT_EXCEEDED,
                f"Daily budget exceeded: spent {current_spend}"
                f" + {payout.amount} > limit {policy.daily_limit} paise",
            )

        # --- Step 4: Domain blacklist/whitelist check ---
        if vendor_url:
            domain = self._extract_domain(vendor_url)

            # Check blacklist
            if domain and policy.blocked_domains and domain in policy.blocked_domains:
                # Rollback budget since we're rejecting
                await self._redis.rollback_budget(agent_id, payout.amount)
                return self._result(
                    payout, agent_id, start_time,
                    Decision.REJECTED, ReasonCode.DOMAIN_BLOCKED,
                    f"Vendor domain '{domain}' is on the blocklist",
                )

            # Check whitelist (if set, domain must be in it)
            if domain and policy.allowed_domains and domain not in policy.allowed_domains:
                await self._redis.rollback_budget(agent_id, payout.amount)
                return self._result(
                    payout, agent_id, start_time,
                    Decision.REJECTED, ReasonCode.DOMAIN_BLOCKED,
                    f"Vendor domain '{domain}' not in allowlist",
                )

        # --- Step 5: Google Safe Browsing reputation check ---
        if vendor_url:
            sb_result = await self._safe_browsing.check_url(vendor_url)
            metrics.record_reputation_check(safe=sb_result.is_safe)
            if not sb_result.is_safe:
                # Rollback budget since we're rejecting
                await self._redis.rollback_budget(agent_id, payout.amount)
                threat_types = sb_result.threat_types
                return self._result(
                    payout, agent_id, start_time,
                    Decision.REJECTED, ReasonCode.RISK_HIGH,
                    f"Google Safe Browsing flagged URL as unsafe: {', '.join(threat_types)}",
                    threat_types=threat_types,
                )

        # --- Step 6: Approval threshold check ---
        if (
            policy.require_approval_above is not None
            and payout.amount > policy.require_approval_above
        ):
            return self._result(
                payout, agent_id, start_time,
                Decision.HELD, ReasonCode.APPROVAL_REQUIRED,
                f"Amount {payout.amount} paise exceeds approval"
                f" threshold of {policy.require_approval_above} paise",
            )

        # --- Step 7: All checks passed → APPROVE ---
        return self._result(
            payout, agent_id, start_time,
            Decision.APPROVED, ReasonCode.POLICY_OK,
            "All governance checks passed",
        )

    @staticmethod
    def _extract_domain(url: str) -> str | None:
        """Extract domain from a URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc or parsed.path.split("/")[0]
        except Exception:
            return None

    @staticmethod
    def _result(
        payout: PayoutEntity,
        agent_id: str,
        start_time: float,
        decision: Decision,
        reason_code: ReasonCode,
        reason_detail: str,
        threat_types: list[str] | None = None,
    ) -> GovernanceResult:
        """Create a GovernanceResult with processing time."""
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        result = GovernanceResult(
            decision=decision,
            reason_code=reason_code,
            reason_detail=reason_detail,
            payout_id=payout.id,
            agent_id=agent_id,
            amount=payout.amount,
            threat_types=threat_types or [],
            processing_ms=elapsed_ms,
        )

        log_level = logging.WARNING if decision != Decision.APPROVED else logging.INFO
        logger.log(
            log_level,
            "DECISION: %s | payout=%s agent=%s amount=%d reason=%s (%dms)",
            decision.value, payout.id, agent_id, payout.amount,
            reason_code.value, elapsed_ms,
        )
        return result
