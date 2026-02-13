"""Tests for circuit breaker, rate limiting, and Slack interactive buttons.

Covers:
- CircuitBreaker state transitions (CLOSED → OPEN → HALF_OPEN → CLOSED)
- CircuitOpenError raised when circuit is open
- CircuitBreaker.reset() and snapshot()
- Redis sliding-window rate limiter
- GovernanceEngine rate limit integration
- Slack interactive approve/reject buttons in Block Kit
- SlackNotifier.update_approval_message()
"""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vyapaar_mcp.db.redis_client import RedisClient
from vyapaar_mcp.governance.engine import GovernanceEngine
from vyapaar_mcp.models import (
    Decision,
    PayoutEntity,
    ReasonCode,
    SafeBrowsingResponse,
)
from vyapaar_mcp.resilience import CircuitBreaker, CircuitOpenError, CircuitState


# ================================================================
# Circuit Breaker Tests
# ================================================================


@pytest.mark.asyncio
class TestCircuitBreaker:
    """Circuit breaker state-machine tests."""

    async def test_starts_closed(self) -> None:
        """New circuit breaker should be CLOSED."""
        cb = CircuitBreaker("test", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    async def test_success_keeps_closed(self) -> None:
        """Successful calls keep the circuit CLOSED."""
        cb = CircuitBreaker("test", failure_threshold=3)

        async def ok() -> str:
            return "ok"

        result = await cb.call(ok)
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    async def test_failures_below_threshold_stay_closed(self) -> None:
        """Fewer failures than threshold keep circuit CLOSED."""
        cb = CircuitBreaker("test", failure_threshold=3)

        async def fail() -> None:
            raise RuntimeError("boom")

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(fail)

        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 2

    async def test_threshold_opens_circuit(self) -> None:
        """Reaching failure threshold transitions to OPEN."""
        cb = CircuitBreaker("test", failure_threshold=3)

        async def fail() -> None:
            raise RuntimeError("boom")

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await cb.call(fail)

        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 3

    async def test_open_circuit_rejects_calls(self) -> None:
        """OPEN circuit raises CircuitOpenError immediately."""
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=60.0)

        async def fail() -> None:
            raise RuntimeError("boom")

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(fail)

        with pytest.raises(CircuitOpenError) as exc_info:
            await cb.call(fail)

        assert exc_info.value.name == "test"
        assert exc_info.value.retry_after > 0

    async def test_half_open_after_recovery_timeout(self) -> None:
        """Circuit transitions to HALF_OPEN after recovery timeout."""
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)

        async def fail() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await cb.call(fail)

        assert cb.state == CircuitState.OPEN

        # Wait for recovery
        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    async def test_half_open_success_closes(self) -> None:
        """Successful call in HALF_OPEN transitions to CLOSED."""
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)

        async def fail() -> None:
            raise RuntimeError("boom")

        async def ok() -> str:
            return "recovered"

        with pytest.raises(RuntimeError):
            await cb.call(fail)

        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        result = await cb.call(ok)
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED

    async def test_half_open_failure_reopens(self) -> None:
        """Failed call in HALF_OPEN transitions back to OPEN."""
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)

        async def fail() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await cb.call(fail)

        await asyncio.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        with pytest.raises(RuntimeError):
            await cb.call(fail)

        assert cb.state == CircuitState.OPEN

    async def test_success_resets_failure_count(self) -> None:
        """A success resets the consecutive failure counter."""
        cb = CircuitBreaker("test", failure_threshold=3)

        async def fail() -> None:
            raise RuntimeError("boom")

        async def ok() -> str:
            return "ok"

        # 2 failures, then 1 success
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(fail)
        assert cb.failure_count == 2

        await cb.call(ok)
        assert cb.failure_count == 0

    async def test_reset(self) -> None:
        """Manual reset returns circuit to CLOSED."""
        cb = CircuitBreaker("test", failure_threshold=1)

        async def fail() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await cb.call(fail)
        assert cb.state == CircuitState.OPEN

        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    async def test_snapshot(self) -> None:
        """Snapshot returns correct metadata."""
        cb = CircuitBreaker("razorpay", failure_threshold=5, recovery_timeout=30.0)
        snap = cb.snapshot()

        assert snap["name"] == "razorpay"
        assert snap["state"] == "CLOSED"
        assert snap["failure_count"] == 0
        assert snap["failure_threshold"] == 5
        assert snap["recovery_timeout_s"] == 30.0

    async def test_snapshot_reflects_open_state(self) -> None:
        """Snapshot shows OPEN state after threshold reached."""
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=60.0)

        async def fail() -> None:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await cb.call(fail)

        snap = cb.snapshot()
        assert snap["state"] == "OPEN"
        assert snap["failure_count"] == 1


# ================================================================
# Rate Limiting Tests (Redis sliding window)
# ================================================================


@pytest.mark.asyncio
class TestRateLimiting:
    """Rate limiting via Redis sorted-set sliding window."""

    async def test_within_limit_allowed(self, fake_redis: RedisClient) -> None:
        """Requests within the limit should be allowed."""
        allowed, count = await fake_redis.check_rate_limit(
            "agent-a", max_requests=5, window_seconds=60
        )
        assert allowed is True
        assert count == 1

    async def test_reaches_limit_still_allowed(self, fake_redis: RedisClient) -> None:
        """Request at the exact limit should still be allowed."""
        for _ in range(4):
            await fake_redis.check_rate_limit(
                "agent-a", max_requests=5, window_seconds=60
            )

        allowed, count = await fake_redis.check_rate_limit(
            "agent-a", max_requests=5, window_seconds=60
        )
        assert allowed is True
        assert count == 5

    async def test_exceeds_limit_blocked(self, fake_redis: RedisClient) -> None:
        """Requests beyond the limit should be blocked."""
        for _ in range(5):
            await fake_redis.check_rate_limit(
                "agent-a", max_requests=5, window_seconds=60
            )

        allowed, count = await fake_redis.check_rate_limit(
            "agent-a", max_requests=5, window_seconds=60
        )
        assert allowed is False
        assert count >= 5

    async def test_different_agents_independent(self, fake_redis: RedisClient) -> None:
        """Rate limits should be independent per agent."""
        for _ in range(5):
            await fake_redis.check_rate_limit(
                "agent-a", max_requests=5, window_seconds=60
            )

        # Agent B should still be allowed
        allowed, count = await fake_redis.check_rate_limit(
            "agent-b", max_requests=5, window_seconds=60
        )
        assert allowed is True
        assert count == 1


# ================================================================
# Governance Engine — Rate Limit Integration
# ================================================================


@pytest.mark.asyncio
class TestGovernanceRateLimit:
    """GovernanceEngine rejects when rate limit is exceeded."""

    async def test_rate_limited_rejects(
        self, fake_redis: RedisClient, mock_postgres: MagicMock
    ) -> None:
        """Agent exceeding rate limit gets RATE_LIMITED rejection."""
        safe_browsing = MagicMock()
        safe_browsing.check_url = AsyncMock(return_value=SafeBrowsingResponse())

        engine = GovernanceEngine(
            fake_redis, mock_postgres, safe_browsing,
            rate_limit_max=3, rate_limit_window=60,
        )

        payout = PayoutEntity(id="pout_rl_1", amount=1000, status="queued")

        # Use up the rate limit
        for i in range(3):
            p = PayoutEntity(id=f"pout_rl_{i}", amount=1000, status="queued")
            result = await engine.evaluate(p, "test-agent-001")
            assert result.decision != Decision.REJECTED or result.reason_code != ReasonCode.RATE_LIMITED

        # Next one should be rate limited
        result = await engine.evaluate(
            PayoutEntity(id="pout_rl_over", amount=1000, status="queued"),
            "test-agent-001",
        )
        assert result.decision == Decision.REJECTED
        assert result.reason_code == ReasonCode.RATE_LIMITED
        assert "Rate limit exceeded" in (result.reason_detail or "")

    async def test_rate_limit_disabled_when_zero(
        self, fake_redis: RedisClient, mock_postgres: MagicMock
    ) -> None:
        """rate_limit_max=0 disables rate limiting entirely."""
        safe_browsing = MagicMock()
        safe_browsing.check_url = AsyncMock(return_value=SafeBrowsingResponse())

        engine = GovernanceEngine(
            fake_redis, mock_postgres, safe_browsing,
            rate_limit_max=0, rate_limit_window=60,
        )

        payout = PayoutEntity(id="pout_nrl", amount=1000, status="queued")
        result = await engine.evaluate(payout, "test-agent-001")
        assert result.reason_code != ReasonCode.RATE_LIMITED


# ================================================================
# Slack Interactive Buttons Tests
# ================================================================


class TestSlackInteractiveButtons:
    """Verify Slack Block Kit messages include approve/reject buttons."""

    def _make_held_result(self, payout_id: str = "pout_test_btn_001", amount: int = 50000) -> Any:
        """Create a HELD GovernanceResult for testing."""
        from vyapaar_mcp.models import GovernanceResult
        return GovernanceResult(
            payout_id=payout_id,
            agent_id="agent-x",
            amount=amount,
            decision=Decision.HELD,
            reason_code=ReasonCode.APPROVAL_REQUIRED,
            reason_detail="Above approval threshold",
            processing_ms=5,
        )

    def test_approval_blocks_have_buttons(self) -> None:
        """Approval blocks should include approve and reject buttons."""
        from vyapaar_mcp.egress.slack_notifier import SlackNotifier

        result = self._make_held_result()
        blocks = SlackNotifier._build_approval_blocks(
            result=result,
            amount_rupees=500.0,
            vendor_name="Test Vendor",
            vendor_url="https://test-vendor.com",
        )

        # Find the actions block
        actions_block = None
        for block in blocks:
            if block.get("type") == "actions":
                actions_block = block
                break

        assert actions_block is not None, "No actions block found in approval blocks"

        elements = actions_block["elements"]
        action_ids = [el["action_id"] for el in elements]

        assert "approve_payout" in action_ids
        assert "reject_payout" in action_ids

        # Verify button values contain the payout ID
        for el in elements:
            assert el["value"] == "pout_test_btn_001"

    def test_approval_buttons_have_correct_styles(self) -> None:
        """Approve button should be 'primary', reject should be 'danger'."""
        from vyapaar_mcp.egress.slack_notifier import SlackNotifier

        result = self._make_held_result(payout_id="pout_style_001", amount=75000)
        blocks = SlackNotifier._build_approval_blocks(
            result=result,
            amount_rupees=750.0,
            vendor_name=None,
            vendor_url=None,
        )

        actions_block = next(b for b in blocks if b.get("type") == "actions")
        elements = actions_block["elements"]

        approve_btn = next(e for e in elements if e["action_id"] == "approve_payout")
        reject_btn = next(e for e in elements if e["action_id"] == "reject_payout")

        assert approve_btn.get("style") == "primary"
        assert reject_btn.get("style") == "danger"

    @pytest.mark.asyncio
    async def test_update_approval_message(self) -> None:
        """update_approval_message should call Slack chat.update API."""
        from vyapaar_mcp.egress.slack_notifier import SlackNotifier

        notifier = SlackNotifier(
            bot_token="xoxb-test-token",
            channel_id="C1234567890",
        )

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"ok": True}
            mock_post.return_value = mock_response

            result = await notifier.update_approval_message(
                channel="C1234567890",
                message_ts="1234567890.123456",
                payout_id="pout_update_001",
                action="approve",
                user_name="test-user",
            )

            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "chat.update" in str(call_args)
