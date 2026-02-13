"""ntfy.sh push notification fallback.

Sends push notifications via ntfy (https://ntfy.sh) as a fallback
when Slack is unavailable (circuit open, not configured, or errors).

Reference: .reference/ntfy/docs/publish.md — JSON publish format
API:       POST https://ntfy.sh/ with JSON body containing "topic"

Key design choices:
  • Simple HTTP POST — ntfy has the simplest API of any notification service
  • No auth required for public ntfy.sh topics (topic name IS the password)
  • Supports priority (1-5), tags, title, and click actions
  • Circuit breaker for resilience
  • Can use self-hosted ntfy or the public ntfy.sh
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from vyapaar_mcp.models import Decision, GovernanceResult, ReasonCode
from vyapaar_mcp.resilience import CircuitBreaker, CircuitOpenError

logger = logging.getLogger("vyapaar_mcp.egress.ntfy")

# ntfy priority levels (reference: .reference/ntfy/docs/publish.md)
PRIORITY_MIN = 1
PRIORITY_LOW = 2
PRIORITY_DEFAULT = 3
PRIORITY_HIGH = 4
PRIORITY_URGENT = 5

# Default ntfy server (public)
_DEFAULT_NTFY_URL = "https://ntfy.sh"


class NtfyNotifier:
    """Async ntfy push notification client.

    Sends governance notifications via ntfy.sh as a Slack fallback.

    Usage:
        notifier = NtfyNotifier(topic="vyapaar-alerts")
        await notifier.send(
            title="Payout Rejected",
            message="Agent agent-001 payout ₹5,000 rejected: DOMAIN_BLOCKED",
            priority=PRIORITY_HIGH,
            tags=["warning", "moneybag"],
        )
    """

    def __init__(
        self,
        topic: str,
        server_url: str = _DEFAULT_NTFY_URL,
        circuit_breaker: CircuitBreaker | None = None,
        timeout: float = 10.0,
        auth_token: str | None = None,
    ) -> None:
        self._topic = topic
        self._server_url = server_url.rstrip("/")
        self._circuit = circuit_breaker
        self._auth_token = auth_token

        headers: dict[str, str] = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers=headers,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def ping(self) -> bool:
        """Test connectivity to the ntfy server."""
        try:
            resp = await self._client.get(f"{self._server_url}/v1/health")
            return resp.status_code == 200
        except Exception:
            return False

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    async def send(
        self,
        message: str,
        title: str | None = None,
        priority: int = PRIORITY_DEFAULT,
        tags: list[str] | None = None,
        click: str | None = None,
    ) -> bool:
        """Send a push notification via ntfy.

        Reference: .reference/ntfy/docs/publish.md — "Publish as JSON"
        Must POST to the ROOT URL with "topic" in JSON body.

        Args:
            message: Notification body text.
            title: Notification title (optional).
            priority: Priority level 1-5 (default 3).
            tags: List of tags/emojis (optional).
            click: URL to open when notification is clicked (optional).

        Returns:
            True if notification was sent successfully.
        """
        payload: dict[str, Any] = {
            "topic": self._topic,
            "message": message,
            "priority": priority,
        }
        if title:
            payload["title"] = title
        if tags:
            payload["tags"] = tags
        if click:
            payload["click"] = click

        try:
            if self._circuit:
                result = await self._circuit.call(self._post_notification, payload)
            else:
                result = await self._post_notification(payload)
            return result

        except CircuitOpenError:
            logger.error("ntfy circuit OPEN — notification dropped")
            return False
        except Exception as e:
            logger.error("ntfy send failed: %s", e)
            return False

    async def send_governance_notification(
        self,
        result: GovernanceResult,
        vendor_name: str | None = None,
        vendor_url: str | None = None,
    ) -> bool:
        """Send a formatted governance notification via ntfy.

        Maps governance decisions to ntfy priority and tags.
        """
        amount_rupees = result.amount / 100
        vendor_display = vendor_name or vendor_url or "Unknown"

        if result.decision == Decision.HELD:
            title = "🔔 Payout Approval Required"
            priority = PRIORITY_HIGH
            tags = ["warning", "moneybag"]
            message = (
                f"Payout {result.payout_id}\n"
                f"Amount: ₹{amount_rupees:,.2f}\n"
                f"Agent: {result.agent_id}\n"
                f"Vendor: {vendor_display}\n"
                f"Reason: {result.reason_detail}\n"
                f"\n⚠️ Requires human approval"
            )
        elif result.decision == Decision.REJECTED:
            reason_tags = {
                ReasonCode.RISK_HIGH: ["skull", "warning"],
                ReasonCode.DOMAIN_BLOCKED: ["no_entry", "warning"],
                ReasonCode.LIMIT_EXCEEDED: ["moneybag", "x"],
                ReasonCode.TXN_LIMIT_EXCEEDED: ["money_with_wings", "x"],
                ReasonCode.NO_POLICY: ["clipboard", "x"],
                ReasonCode.RATE_LIMITED: ["hourglass", "x"],
            }
            title = f"❌ Payout Rejected — {result.reason_code.value}"
            priority = PRIORITY_HIGH
            tags = reason_tags.get(result.reason_code, ["x"])

            threat_info = ""
            if result.threat_types:
                threat_info = f"\nThreats: {', '.join(result.threat_types)}"

            message = (
                f"Payout {result.payout_id}\n"
                f"Amount: ₹{amount_rupees:,.2f}\n"
                f"Agent: {result.agent_id}\n"
                f"Vendor: {vendor_display}\n"
                f"Reason: {result.reason_detail}{threat_info}"
            )
        elif result.decision == Decision.APPROVED:
            # Approvals are silent by default — don't notify
            return True
        else:
            return True

        return await self.send(
            message=message,
            title=title,
            priority=priority,
            tags=tags,
        )

    # ----------------------------------------------------------------
    # Private
    # ----------------------------------------------------------------

    async def _post_notification(self, payload: dict[str, Any]) -> bool:
        """POST JSON payload to ntfy server root.

        Per ntfy docs: JSON publish must POST to the ROOT URL,
        not to the topic URL. Topic is specified in the JSON body.
        """
        resp = await self._client.post(
            f"{self._server_url}/",
            json=payload,
        )
        if resp.status_code in (200, 201):
            logger.info(
                "ntfy notification sent: topic=%s priority=%d",
                payload.get("topic"),
                payload.get("priority", 3),
            )
            return True
        else:
            logger.error(
                "ntfy notification failed: status=%d body=%s",
                resp.status_code,
                resp.text[:200],
            )
            return False


# ================================================================
# Notification Routing with ntfy Fallback
# ================================================================


async def notify_with_fallback(
    slack_notifier: Any | None,
    ntfy_notifier: NtfyNotifier | None,
    result: GovernanceResult,
    vendor_name: str | None = None,
    vendor_url: str | None = None,
) -> None:
    """Send notification via Slack, falling back to ntfy on failure.

    Routing logic:
    1. If Slack is available → try Slack first
    2. If Slack fails (or circuit open) → fall back to ntfy
    3. If neither is available → log warning

    APPROVED decisions are silent regardless of notification channel.
    """
    from vyapaar_mcp.observability import metrics

    if result.decision == Decision.APPROVED:
        return

    slack_sent = False
    ntfy_sent = False

    # --- Try Slack first ---
    if slack_notifier is not None:
        try:
            if result.decision == Decision.HELD:
                slack_sent = await slack_notifier.request_approval(
                    result, vendor_name=vendor_name, vendor_url=vendor_url,
                )
            elif result.decision == Decision.REJECTED:
                alert_reasons = {
                    ReasonCode.RISK_HIGH, ReasonCode.DOMAIN_BLOCKED,
                    ReasonCode.LIMIT_EXCEEDED, ReasonCode.NO_POLICY,
                }
                if result.reason_code in alert_reasons:
                    slack_sent = await slack_notifier.send_rejection_alert(
                        result, vendor_name=vendor_name, vendor_url=vendor_url,
                    )
                else:
                    slack_sent = True  # Not a notifiable rejection

            metrics.record_slack_notification(success=slack_sent)
        except Exception as e:
            metrics.record_slack_notification(success=False)
            logger.warning("Slack notification failed, trying ntfy fallback: %s", e)
            slack_sent = False

    # --- Fallback to ntfy ---
    if not slack_sent and ntfy_notifier is not None:
        try:
            ntfy_sent = await ntfy_notifier.send_governance_notification(
                result, vendor_name=vendor_name, vendor_url=vendor_url,
            )
            if ntfy_sent:
                logger.info("ntfy fallback notification sent for %s", result.payout_id)
        except Exception as e:
            logger.error("ntfy fallback also failed: %s", e)

    if not slack_sent and not ntfy_sent:
        if slack_notifier is None and ntfy_notifier is None:
            # No notification channels configured — not an error
            pass
        else:
            logger.warning(
                "All notification channels failed for payout %s (decision=%s)",
                result.payout_id,
                result.decision.value,
            )
