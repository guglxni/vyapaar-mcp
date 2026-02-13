"""Tests for the governance engine decision matrix.

Tests every row of SPEC §8 Decision Matrix.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from vyapaar_mcp.db.redis_client import RedisClient
from vyapaar_mcp.governance.engine import GovernanceEngine
from vyapaar_mcp.models import (
    Decision,
    PayoutEntity,
    ReasonCode,
    SafeBrowsingResponse,
)


@pytest.fixture
def safe_browsing_safe() -> MagicMock:
    """Mock Safe Browsing that always returns SAFE."""
    mock = MagicMock()
    mock.check_url = AsyncMock(return_value=SafeBrowsingResponse())
    return mock


@pytest.fixture
def safe_browsing_unsafe() -> MagicMock:
    """Mock Safe Browsing that always returns UNSAFE (MALWARE)."""
    mock = MagicMock()
    mock.check_url = AsyncMock(
        return_value=SafeBrowsingResponse(
            matches=[
                {  # type: ignore[list-item]
                    "threatType": "MALWARE",
                    "platformType": "ANY_PLATFORM",
                    "threatEntryType": "URL",
                    "threat": {"url": "http://evil.com"},
                }
            ]
        )
    )
    return mock


def make_payout(
    payout_id: str = "pout_test_001",
    amount: int = 50000,
) -> PayoutEntity:
    """Create a test PayoutEntity."""
    return PayoutEntity(
        id=payout_id,
        amount=amount,
        status="queued",
    )


@pytest.mark.asyncio
class TestGovernanceEngine:
    """Test the full governance decision engine."""

    async def test_no_policy_rejects(
        self, fake_redis: RedisClient, safe_browsing_safe: MagicMock
    ) -> None:
        """Agent with no policy should be REJECTED (SPEC §8 row 3)."""
        mock_pg = MagicMock()
        mock_pg.get_agent_policy = AsyncMock(return_value=None)

        engine = GovernanceEngine(fake_redis, mock_pg, safe_browsing_safe)
        result = await engine.evaluate(make_payout(), "unknown-agent")

        assert result.decision == Decision.REJECTED
        assert result.reason_code == ReasonCode.NO_POLICY

    async def test_per_txn_limit_exceeded(
        self, fake_redis: RedisClient, mock_postgres: MagicMock, safe_browsing_safe: MagicMock
    ) -> None:
        """Amount exceeding per-txn limit should be REJECTED (SPEC §8 row 5)."""
        # Policy has per_txn_limit = 100000 (₹1,000)
        engine = GovernanceEngine(fake_redis, mock_postgres, safe_browsing_safe)
        result = await engine.evaluate(make_payout(amount=200000), "test-agent-001")

        assert result.decision == Decision.REJECTED
        assert result.reason_code == ReasonCode.TXN_LIMIT_EXCEEDED

    async def test_daily_limit_exceeded(
        self, fake_redis: RedisClient, mock_postgres: MagicMock, safe_browsing_safe: MagicMock
    ) -> None:
        """Cumulative spend exceeding daily limit should be REJECTED (SPEC §8 row 4)."""
        engine = GovernanceEngine(fake_redis, mock_postgres, safe_browsing_safe)

        # Spend up to the limit first (policy daily_limit = 500000)
        for _ in range(5):
            await engine.evaluate(make_payout(amount=100000), "test-agent-001")

        # This should fail
        result = await engine.evaluate(
            make_payout(payout_id="pout_over", amount=100000), "test-agent-001"
        )
        assert result.decision == Decision.REJECTED
        assert result.reason_code == ReasonCode.LIMIT_EXCEEDED

    async def test_domain_blocked_rejects(
        self, fake_redis: RedisClient, mock_postgres: MagicMock, safe_browsing_safe: MagicMock
    ) -> None:
        """Vendor on blocklist should be REJECTED (SPEC §8 row 7)."""
        engine = GovernanceEngine(fake_redis, mock_postgres, safe_browsing_safe)
        result = await engine.evaluate(
            make_payout(amount=10000), "test-agent-001",
            vendor_url="https://evil.com/pay",
        )

        assert result.decision == Decision.REJECTED
        assert result.reason_code == ReasonCode.DOMAIN_BLOCKED

    async def test_safe_browsing_unsafe_rejects(
        self, fake_redis: RedisClient, mock_postgres: MagicMock, safe_browsing_unsafe: MagicMock
    ) -> None:
        """URL flagged by Safe Browsing should be REJECTED (SPEC §8 row 6)."""
        engine = GovernanceEngine(fake_redis, mock_postgres, safe_browsing_unsafe)
        result = await engine.evaluate(
            make_payout(amount=10000), "test-agent-001",
            vendor_url="https://legit-looking.com",
        )

        assert result.decision == Decision.REJECTED
        assert result.reason_code == ReasonCode.RISK_HIGH
        assert "MALWARE" in result.threat_types

    async def test_approval_threshold_holds(
        self, fake_redis: RedisClient, mock_postgres: MagicMock, safe_browsing_safe: MagicMock
    ) -> None:
        """Amount above approval threshold should be HELD (SPEC §8 row 8)."""
        engine = GovernanceEngine(fake_redis, mock_postgres, safe_browsing_safe)
        # Policy has require_approval_above = 50000 (₹500)
        result = await engine.evaluate(
            make_payout(amount=75000), "test-agent-001",
            vendor_url="https://safe-vendor.com",
        )

        assert result.decision == Decision.HELD
        assert result.reason_code == ReasonCode.APPROVAL_REQUIRED

    async def test_all_checks_pass_approves(
        self, fake_redis: RedisClient, mock_postgres: MagicMock, safe_browsing_safe: MagicMock
    ) -> None:
        """All checks passing should APPROVE (SPEC §8 row 9)."""
        engine = GovernanceEngine(fake_redis, mock_postgres, safe_browsing_safe)
        result = await engine.evaluate(
            make_payout(amount=10000), "test-agent-001",
            vendor_url="https://safe-vendor.com",
        )

        assert result.decision == Decision.APPROVED
        assert result.reason_code == ReasonCode.POLICY_OK

    async def test_processing_time_tracked(
        self, fake_redis: RedisClient, mock_postgres: MagicMock, safe_browsing_safe: MagicMock
    ) -> None:
        """Processing time should be tracked in milliseconds."""
        engine = GovernanceEngine(fake_redis, mock_postgres, safe_browsing_safe)
        result = await engine.evaluate(
            make_payout(amount=10000), "test-agent-001",
        )

        assert result.processing_ms is not None
        assert result.processing_ms >= 0
