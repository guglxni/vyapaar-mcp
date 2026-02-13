"""Tests for Slack notifier — human-in-the-loop approval workflow.

Tests message formatting, API calls, and notification logic.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vyapaar_mcp.egress.slack_notifier import SlackNotifier, notify_slack
from vyapaar_mcp.models import Decision, GovernanceResult, ReasonCode


def make_result(
    decision: Decision = Decision.HELD,
    reason_code: ReasonCode = ReasonCode.APPROVAL_REQUIRED,
    amount: int = 75000,
    payout_id: str = "pout_test_slack_001",
    agent_id: str = "test-agent-001",
) -> GovernanceResult:
    """Create a GovernanceResult for testing."""
    return GovernanceResult(
        decision=decision,
        reason_code=reason_code,
        reason_detail=f"Test: {reason_code.value}",
        payout_id=payout_id,
        agent_id=agent_id,
        amount=amount,
        processing_ms=42,
    )


class TestSlackNotifierInit:
    def test_init(self) -> None:
        notifier = SlackNotifier(
            bot_token="xoxb-test-token",
            channel_id="C12345",
        )
        assert notifier._channel_id == "C12345"
        assert notifier._bot_token == "xoxb-test-token"


class TestApprovalBlocks:
    def test_approval_blocks_structure(self) -> None:
        result = make_result()
        blocks = SlackNotifier._build_approval_blocks(
            result, 750.0, "Test Vendor", "https://vendor.com"
        )
        assert len(blocks) >= 4
        assert blocks[0]["type"] == "header"
        assert "Approval Required" in blocks[0]["text"]["text"]

    def test_approval_blocks_with_no_vendor(self) -> None:
        result = make_result()
        blocks = SlackNotifier._build_approval_blocks(
            result, 750.0, None, None
        )
        # Should use "Unknown Vendor" fallback
        found_vendor = False
        for block in blocks:
            if block.get("type") == "section" and "fields" in block:
                for field in block["fields"]:
                    if "Unknown Vendor" in field.get("text", ""):
                        found_vendor = True
        assert found_vendor


class TestRejectionBlocks:
    def test_rejection_blocks_structure(self) -> None:
        result = make_result(
            decision=Decision.REJECTED,
            reason_code=ReasonCode.RISK_HIGH,
        )
        result.threat_types = ["MALWARE"]
        blocks = SlackNotifier._build_rejection_blocks(
            result, 750.0, "Evil Corp", "https://evil.com"
        )
        assert len(blocks) >= 4
        assert blocks[0]["type"] == "header"
        assert "Rejected" in blocks[0]["text"]["text"]

    def test_rejection_blocks_with_threats(self) -> None:
        result = make_result(
            decision=Decision.REJECTED,
            reason_code=ReasonCode.RISK_HIGH,
        )
        result.threat_types = ["MALWARE", "SOCIAL_ENGINEERING"]
        blocks = SlackNotifier._build_rejection_blocks(
            result, 100.0, None, "https://evil.com"
        )
        # Check that threats appear somewhere in blocks
        block_text = str(blocks)
        assert "MALWARE" in block_text


@pytest.mark.asyncio
class TestNotifySlackFunction:
    async def test_notify_none_notifier_does_nothing(self) -> None:
        """No error when notifier is None."""
        result = make_result()
        await notify_slack(None, result)  # Should not raise

    async def test_notify_held_calls_request_approval(self) -> None:
        notifier = MagicMock(spec=SlackNotifier)
        notifier.request_approval = AsyncMock(return_value=True)
        notifier.send_rejection_alert = AsyncMock(return_value=True)

        result = make_result(decision=Decision.HELD)
        await notify_slack(notifier, result, vendor_name="Test")

        notifier.request_approval.assert_awaited_once()
        notifier.send_rejection_alert.assert_not_awaited()

    async def test_notify_rejected_risk_sends_alert(self) -> None:
        notifier = MagicMock(spec=SlackNotifier)
        notifier.request_approval = AsyncMock(return_value=True)
        notifier.send_rejection_alert = AsyncMock(return_value=True)

        result = make_result(
            decision=Decision.REJECTED,
            reason_code=ReasonCode.RISK_HIGH,
        )
        await notify_slack(notifier, result)

        notifier.send_rejection_alert.assert_awaited_once()
        notifier.request_approval.assert_not_awaited()

    async def test_notify_approved_no_notification(self) -> None:
        notifier = MagicMock(spec=SlackNotifier)
        notifier.request_approval = AsyncMock()
        notifier.send_rejection_alert = AsyncMock()

        result = make_result(
            decision=Decision.APPROVED,
            reason_code=ReasonCode.POLICY_OK,
        )
        await notify_slack(notifier, result)

        notifier.request_approval.assert_not_awaited()
        notifier.send_rejection_alert.assert_not_awaited()

    async def test_notify_rejected_txn_limit_sends_alert(self) -> None:
        notifier = MagicMock(spec=SlackNotifier)
        notifier.request_approval = AsyncMock()
        notifier.send_rejection_alert = AsyncMock(return_value=True)

        result = make_result(
            decision=Decision.REJECTED,
            reason_code=ReasonCode.LIMIT_EXCEEDED,
        )
        await notify_slack(notifier, result)

        notifier.send_rejection_alert.assert_awaited_once()

    async def test_slack_error_does_not_propagate(self) -> None:
        """Slack failures should be non-fatal."""
        notifier = MagicMock(spec=SlackNotifier)
        notifier.request_approval = AsyncMock(side_effect=RuntimeError("Slack down"))

        result = make_result(decision=Decision.HELD)
        # Should not raise
        await notify_slack(notifier, result)
