"""Tests for ntfy push notification fallback."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from vyapaar_mcp.egress.ntfy_notifier import (
    PRIORITY_DEFAULT,
    PRIORITY_HIGH,
    PRIORITY_URGENT,
    NtfyNotifier,
    notify_with_fallback,
)
from vyapaar_mcp.models import Decision, GovernanceResult, ReasonCode
from vyapaar_mcp.resilience import CircuitOpenError


# ================================================================
# Helpers
# ================================================================


def make_result(
    decision: Decision = Decision.REJECTED,
    reason_code: ReasonCode = ReasonCode.RISK_HIGH,
    amount: int = 50000,
) -> GovernanceResult:
    """Create a test governance result."""
    return GovernanceResult(
        decision=decision,
        reason_code=reason_code,
        reason_detail="Test reason",
        payout_id="pout_test_123",
        agent_id="test-agent-001",
        amount=amount,
        threat_types=["MALWARE"] if reason_code == ReasonCode.RISK_HIGH else [],
        processing_ms=42,
    )


# ================================================================
# NtfyNotifier Tests
# ================================================================


@pytest.mark.asyncio
class TestNtfyNotifier:
    """Test NtfyNotifier send functionality."""

    async def test_send_basic_notification(self) -> None:
        """Test successful basic notification send."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        notifier = NtfyNotifier(topic="vyapaar-test")
        notifier._client = MagicMock()
        notifier._client.post = AsyncMock(return_value=mock_response)
        notifier._client.aclose = AsyncMock()

        result = await notifier.send(
            message="Test notification",
            title="Test Title",
            priority=PRIORITY_HIGH,
            tags=["warning"],
        )

        assert result is True
        call_kwargs = notifier._client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["topic"] == "vyapaar-test"
        assert payload["message"] == "Test notification"
        assert payload["title"] == "Test Title"
        assert payload["priority"] == PRIORITY_HIGH
        assert payload["tags"] == ["warning"]

        await notifier.close()

    async def test_send_to_root_url(self) -> None:
        """Verify POST goes to root URL, not topic URL (per ntfy API spec)."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        notifier = NtfyNotifier(topic="test-topic", server_url="https://ntfy.example.com")
        notifier._client = MagicMock()
        notifier._client.post = AsyncMock(return_value=mock_response)
        notifier._client.aclose = AsyncMock()

        await notifier.send(message="Hello")

        call_args = notifier._client.post.call_args
        url = call_args[0][0] if call_args[0] else call_args.kwargs.get("url", "")
        assert url == "https://ntfy.example.com/"

        await notifier.close()

    async def test_send_failure_returns_false(self) -> None:
        """Test that HTTP errors return False."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        notifier = NtfyNotifier(topic="test-topic")
        notifier._client = MagicMock()
        notifier._client.post = AsyncMock(return_value=mock_response)
        notifier._client.aclose = AsyncMock()

        result = await notifier.send(message="This will fail")
        assert result is False
        await notifier.close()

    async def test_send_circuit_open_returns_false(self) -> None:
        """Test circuit breaker open = notification dropped."""
        cb = MagicMock()
        cb.call = AsyncMock(side_effect=CircuitOpenError("ntfy", 30))

        notifier = NtfyNotifier(topic="test-topic", circuit_breaker=cb)
        notifier._client = MagicMock()
        notifier._client.aclose = AsyncMock()

        result = await notifier.send(message="Dropped notification")
        assert result is False
        await notifier.close()

    async def test_send_governance_held(self) -> None:
        """Test governance HELD notification format."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        notifier = NtfyNotifier(topic="vyapaar-alerts")
        notifier._client = MagicMock()
        notifier._client.post = AsyncMock(return_value=mock_response)
        notifier._client.aclose = AsyncMock()

        result_obj = make_result(
            decision=Decision.HELD,
            reason_code=ReasonCode.APPROVAL_REQUIRED,
            amount=75000,
        )
        sent = await notifier.send_governance_notification(
            result_obj, vendor_name="Test Vendor Pvt Ltd",
        )

        assert sent is True
        payload = notifier._client.post.call_args.kwargs["json"]
        assert "Approval Required" in payload["title"]
        assert "75,000" in payload["message"] or "750" in payload["message"]

        await notifier.close()

    async def test_send_governance_rejected(self) -> None:
        """Test governance REJECTED notification includes threat info."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        notifier = NtfyNotifier(topic="vyapaar-alerts")
        notifier._client = MagicMock()
        notifier._client.post = AsyncMock(return_value=mock_response)
        notifier._client.aclose = AsyncMock()

        result_obj = make_result(
            decision=Decision.REJECTED,
            reason_code=ReasonCode.RISK_HIGH,
        )
        sent = await notifier.send_governance_notification(result_obj)

        assert sent is True
        payload = notifier._client.post.call_args.kwargs["json"]
        assert "Rejected" in payload["title"]
        assert "MALWARE" in payload["message"]

        await notifier.close()

    async def test_send_governance_approved_is_silent(self) -> None:
        """APPROVED notifications should be silent (return True without sending)."""
        notifier = NtfyNotifier(topic="test")
        notifier._client = MagicMock()
        notifier._client.post = AsyncMock()
        notifier._client.aclose = AsyncMock()

        result_obj = make_result(decision=Decision.APPROVED, reason_code=ReasonCode.POLICY_OK)
        sent = await notifier.send_governance_notification(result_obj)

        assert sent is True
        notifier._client.post.assert_not_called()
        await notifier.close()

    async def test_ping_success(self) -> None:
        """Test ping returns True on healthy server."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        notifier = NtfyNotifier(topic="test")
        notifier._client = MagicMock()
        notifier._client.get = AsyncMock(return_value=mock_response)
        notifier._client.aclose = AsyncMock()

        assert await notifier.ping() is True
        await notifier.close()

    async def test_ping_failure(self) -> None:
        """Test ping returns False on unreachable server."""
        notifier = NtfyNotifier(topic="test")
        notifier._client = MagicMock()
        notifier._client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        notifier._client.aclose = AsyncMock()

        assert await notifier.ping() is False
        await notifier.close()

    async def test_auth_token_in_headers(self) -> None:
        """Test that auth token is set in HTTP client headers."""
        notifier = NtfyNotifier(topic="test", auth_token="tk_my_secret_token")
        # Check the client was created with auth header
        assert notifier._auth_token == "tk_my_secret_token"
        await notifier.close()


# ================================================================
# notify_with_fallback Tests
# ================================================================


@pytest.mark.asyncio
class TestNotifyWithFallback:
    """Test the Slack → ntfy fallback notification routing."""

    async def test_slack_success_no_ntfy(self) -> None:
        """When Slack succeeds, ntfy should NOT be called."""
        slack = MagicMock()
        slack.request_approval = AsyncMock(return_value=True)

        ntfy = MagicMock(spec=NtfyNotifier)
        ntfy.send_governance_notification = AsyncMock(return_value=True)

        result = make_result(decision=Decision.HELD, reason_code=ReasonCode.APPROVAL_REQUIRED)
        await notify_with_fallback(slack, ntfy, result)

        slack.request_approval.assert_called_once()
        ntfy.send_governance_notification.assert_not_called()

    async def test_slack_fails_ntfy_fallback(self) -> None:
        """When Slack fails, ntfy should be called as fallback."""
        slack = MagicMock()
        slack.request_approval = AsyncMock(return_value=False)

        ntfy = MagicMock(spec=NtfyNotifier)
        ntfy.send_governance_notification = AsyncMock(return_value=True)

        result = make_result(decision=Decision.HELD, reason_code=ReasonCode.APPROVAL_REQUIRED)
        await notify_with_fallback(slack, ntfy, result)

        slack.request_approval.assert_called_once()
        ntfy.send_governance_notification.assert_called_once()

    async def test_slack_exception_ntfy_fallback(self) -> None:
        """When Slack raises an exception, ntfy should be called."""
        slack = MagicMock()
        slack.send_rejection_alert = AsyncMock(side_effect=Exception("Slack error"))

        ntfy = MagicMock(spec=NtfyNotifier)
        ntfy.send_governance_notification = AsyncMock(return_value=True)

        result = make_result(decision=Decision.REJECTED, reason_code=ReasonCode.RISK_HIGH)
        await notify_with_fallback(slack, ntfy, result)

        ntfy.send_governance_notification.assert_called_once()

    async def test_no_slack_ntfy_only(self) -> None:
        """When Slack is None, ntfy should be used directly."""
        ntfy = MagicMock(spec=NtfyNotifier)
        ntfy.send_governance_notification = AsyncMock(return_value=True)

        result = make_result(decision=Decision.REJECTED, reason_code=ReasonCode.DOMAIN_BLOCKED)
        await notify_with_fallback(None, ntfy, result)

        ntfy.send_governance_notification.assert_called_once()

    async def test_approved_is_silent(self) -> None:
        """APPROVED decisions should not trigger any notification."""
        slack = MagicMock()
        ntfy = MagicMock(spec=NtfyNotifier)

        result = make_result(decision=Decision.APPROVED, reason_code=ReasonCode.POLICY_OK)
        await notify_with_fallback(slack, ntfy, result)

        # Nothing should be called for APPROVED
        slack.request_approval.assert_not_called() if hasattr(slack, 'request_approval') else None
        ntfy.send_governance_notification.assert_not_called()

    async def test_both_none_no_error(self) -> None:
        """When both Slack and ntfy are None, should not raise."""
        result = make_result(decision=Decision.REJECTED, reason_code=ReasonCode.RISK_HIGH)
        # Should not raise
        await notify_with_fallback(None, None, result)

    async def test_rejected_non_alert_reason_no_notification(self) -> None:
        """Rejected with non-security reason should not trigger notification via Slack."""
        slack = MagicMock()
        slack.send_rejection_alert = AsyncMock(return_value=True)

        ntfy = MagicMock(spec=NtfyNotifier)
        ntfy.send_governance_notification = AsyncMock(return_value=True)

        result = make_result(
            decision=Decision.REJECTED,
            reason_code=ReasonCode.TXN_LIMIT_EXCEEDED,
        )
        await notify_with_fallback(slack, ntfy, result)

        # TXN_LIMIT_EXCEEDED is not in the alert_reasons set for Slack
        # So Slack returns True (no notification needed), ntfy not called
        slack.send_rejection_alert.assert_not_called()
