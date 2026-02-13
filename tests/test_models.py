"""Tests for Pydantic V2 data model validation.

SPEC §4 Constraint #5: All code must pass mypy --strict.
"""

from __future__ import annotations

from vyapaar_mcp.models import (
    AgentPolicy,
    BudgetStatus,
    Decision,
    GovernanceResult,
    HealthStatus,
    PayoutEntity,
    PayoutNotes,
    ReasonCode,
    SafeBrowsingResponse,
)


class TestPayoutModels:
    """Test Razorpay webhook payload models."""

    def test_payout_entity_basic(self) -> None:
        """Basic payout entity should parse correctly."""
        entity = PayoutEntity(
            id="pout_123",
            amount=50000,
            status="queued",
        )
        assert entity.id == "pout_123"
        assert entity.amount == 50000
        assert entity.currency == "INR"

    def test_payout_notes_extraction(self) -> None:
        """Notes should be extractable from dict or PayoutNotes."""
        entity = PayoutEntity(
            id="pout_123",
            amount=50000,
            status="queued",
            notes={"agent_id": "agent-001", "vendor_url": "https://example.com"},
        )
        notes = entity.get_notes()
        assert notes.agent_id == "agent-001"
        assert notes.vendor_url == "https://example.com"

    def test_payout_notes_defaults(self) -> None:
        """Missing notes should use defaults."""
        notes = PayoutNotes()
        assert notes.agent_id == "unknown"
        assert notes.vendor_url == ""

    def test_amount_is_integer(self) -> None:
        """Amount must be integer (paise), not float."""
        entity = PayoutEntity(id="pout_123", amount=50000, status="queued")
        assert isinstance(entity.amount, int)


class TestSafeBrowsingModels:
    """Test Google Safe Browsing response models."""

    def test_empty_response_is_safe(self) -> None:
        """Empty response (no matches) means URL is safe."""
        response = SafeBrowsingResponse()
        assert response.is_safe is True
        assert response.threat_types == []

    def test_response_with_matches_is_unsafe(self) -> None:
        """Response with matches means URL is unsafe."""
        response = SafeBrowsingResponse(
            matches=[
                {  # type: ignore[list-item]
                    "threatType": "MALWARE",
                    "platformType": "ANY_PLATFORM",
                    "threatEntryType": "URL",
                    "threat": {"url": "http://evil.com"},
                }
            ]
        )
        assert response.is_safe is False
        assert "MALWARE" in response.threat_types


class TestGovernanceModels:
    """Test internal governance result models."""

    def test_governance_result(self) -> None:
        """GovernanceResult should serialize correctly."""
        result = GovernanceResult(
            decision=Decision.REJECTED,
            reason_code=ReasonCode.RISK_HIGH,
            reason_detail="MALWARE detected",
            payout_id="pout_123",
            agent_id="agent-001",
            amount=50000,
            threat_types=["MALWARE"],
            processing_ms=42,
        )
        assert result.decision == Decision.REJECTED
        assert result.reason_code == ReasonCode.RISK_HIGH
        assert result.processing_ms == 42

    def test_budget_status(self) -> None:
        """BudgetStatus should compute remaining correctly."""
        status = BudgetStatus(
            agent_id="agent-001",
            daily_limit=500000,
            spent_today=200000,
            remaining=300000,
        )
        assert status.remaining == 300000

    def test_agent_policy_defaults(self) -> None:
        """Default policy should have sensible defaults."""
        policy = AgentPolicy(agent_id="agent-001")
        assert policy.daily_limit == 500000  # ₹5,000
        assert policy.per_txn_limit is None
        assert policy.blocked_domains == []

    def test_health_status(self) -> None:
        """HealthStatus should track all services."""
        health = HealthStatus(
            redis="ok",
            postgres="ok",
            razorpay="error",
            uptime_seconds=3600,
        )
        assert health.redis == "ok"
        assert health.razorpay == "error"


class TestEnums:
    """Test enum values match SPEC §8 decision matrix."""

    def test_decision_values(self) -> None:
        """Decision enum should have APPROVED, REJECTED, HELD."""
        assert Decision.APPROVED.value == "APPROVED"
        assert Decision.REJECTED.value == "REJECTED"
        assert Decision.HELD.value == "HELD"

    def test_reason_codes(self) -> None:
        """All SPEC §8 reason codes should exist."""
        codes = [rc.value for rc in ReasonCode]
        assert "POLICY_OK" in codes
        assert "INVALID_SIGNATURE" in codes
        assert "LIMIT_EXCEEDED" in codes
        assert "RISK_HIGH" in codes
        assert "DOMAIN_BLOCKED" in codes
        assert "APPROVAL_REQUIRED" in codes
