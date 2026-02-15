"""Slack integration for human-in-the-loop approval workflows.

When the governance engine returns a HELD decision (amount exceeds
approval threshold), this module sends an approval request to a
configured Slack channel.

SPEC §3.3: "The Messenger — Human-in-the-loop approvals via Slack MCP"
SPEC §8 row 8: Amount > Approval Threshold → HOLD → Slack approval request
SPEC §16.2: @modelcontextprotocol/server-slack integration

Architecture:
  GovernanceEngine → HELD decision → SlackNotifier.request_approval()
                                       ↓
                                   Slack Channel (Block Kit message)
                                       ↓
                                   Human reviews + approves/rejects

Environment Variables:
  SLACK_BOT_TOKEN  — xoxb- bot token with chat:write scope
  SLACK_CHANNEL_ID — Channel ID for approval messages
  SLACK_SIGNING_SECRET — For verifying interactive callback signatures
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any

import httpx

from vyapaar_mcp.models import Decision, GovernanceResult, ReasonCode
from vyapaar_mcp.observability import metrics
from vyapaar_mcp.security import mask_secrets

logger = logging.getLogger(__name__)

SLACK_API_BASE = "https://slack.com/api"

# Slack signature verification
SLACK_SIGNATURE_VERSION = "v0"


def verify_slack_signature(
    payload: str,
    timestamp: str,
    signature: str,
    signing_secret: str,
) -> bool:
    """Verify Slack request signature to prevent callback spoofing.
    
    Per Slack security best practices:
    https://api.slack.com/authentication/verifying-requests-from-slack
    
    Args:
        payload: Raw request body
        timestamp: X-Slack-Request-Timestamp header
        signature: X-Slack-Signature header
        signing_secret: Slack app signing secret
        
    Returns:
        True if signature is valid, False otherwise
    """
    # Reject requests older than 5 minutes (replay attack protection)
    try:
        request_time = int(timestamp)
        current_time = int(time.time())
        if abs(current_time - request_time) > 300:
            logger.warning("Slack signature verification failed: request too old")
            return False
    except ValueError:
        logger.warning("Slack signature verification failed: invalid timestamp")
        return False
    
    # Build the base string
    base_string = f"{SLACK_SIGNATURE_VERSION}:{timestamp}:{payload}"
    
    # Compute signature
    expected_signature = hmac.new(
        key=signing_secret.encode("utf-8"),
        msg=base_string.encode("utf-8"),
        digestmod=hashlib.sha256,
    ).hexdigest()
    
    # Compare signatures (timing-safe)
    is_valid = hmac.compare_digest(f"{SLACK_SIGNATURE_VERSION}={expected_signature}", signature)
    
    if not is_valid:
        logger.warning("Slack signature verification FAILED")
    else:
        logger.debug("Slack signature verified OK")
    
    return is_valid


class SlackNotifier:
    """Sends governance notifications and approval requests to Slack."""

    def __init__(
        self,
        bot_token: str,
        channel_id: str,
    ) -> None:
        self._bot_token = bot_token
        self._channel_id = channel_id
        self._http = httpx.AsyncClient(
            base_url=SLACK_API_BASE,
            headers={
                "Authorization": f"Bearer {bot_token}",
                "Content-Type": "application/json; charset=utf-8",
            },
            timeout=10.0,
        )
        logger.info(
            "SlackNotifier initialized (channel=%s)",
            channel_id,
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._http.aclose()

    # ================================================================
    # Approval Requests (HELD payouts)
    # ================================================================

    async def request_approval(
        self,
        result: GovernanceResult,
        vendor_name: str | None = None,
        vendor_url: str | None = None,
    ) -> bool:
        """Send an approval request to Slack for a HELD payout.

        Returns True if the message was sent successfully.
        """
        amount_rupees = result.amount / 100
        blocks = self._build_approval_blocks(
            result, amount_rupees, vendor_name, vendor_url
        )

        return await self._post_message(
            text=f"🔔 Approval Required: ₹{amount_rupees:,.2f} payout by {result.agent_id}",
            blocks=blocks,
        )

    # ================================================================
    # Alert Notifications (REJECTED payouts)
    # ================================================================

    async def send_rejection_alert(
        self,
        result: GovernanceResult,
        vendor_name: str | None = None,
        vendor_url: str | None = None,
    ) -> bool:
        """Send a rejection alert to Slack.

        Alerts are sent for security-relevant rejections:
        - RISK_HIGH (Safe Browsing flagged)
        - DOMAIN_BLOCKED
        - LIMIT_EXCEEDED
        - NO_POLICY
        """
        amount_rupees = result.amount / 100
        blocks = self._build_rejection_blocks(
            result, amount_rupees, vendor_name, vendor_url
        )

        return await self._post_message(
            text=f"🚨 Payout Rejected: ₹{amount_rupees:,.2f} — {result.reason_code.value}",
            blocks=blocks,
        )

    # ================================================================
    # Slack API
    # ================================================================

    async def _post_message(
        self,
        text: str,
        blocks: list[dict[str, Any]] | None = None,
    ) -> bool:
        """Post a message to the configured Slack channel."""
        payload: dict[str, Any] = {
            "channel": self._channel_id,
            "text": text,  # Fallback for notifications
        }
        if blocks:
            payload["blocks"] = blocks

        try:
            response = await self._http.post(
                "/chat.postMessage",
                json=payload,
            )
            data = response.json()

            if data.get("ok"):
                logger.info(
                    "Slack message sent: ts=%s channel=%s",
                    data.get("ts"),
                    self._channel_id,
                )
                return True
            else:
                logger.error(
                    "Slack API error: %s",
                    data.get("error", "unknown"),
                )
                return False

        except httpx.TimeoutException:
            logger.error("Slack API timeout")
            return False
        except Exception as e:
            logger.error("Slack notification failed: %s", e)
            return False

    async def ping(self) -> bool:
        """Check if Slack API is reachable with valid token."""
        try:
            response = await self._http.post("/auth.test")
            data = response.json()
            return bool(data.get("ok"))
        except Exception:
            return False

    async def update_approval_message(
        self,
        channel: str,
        message_ts: str,
        payout_id: str,
        action: str,
        user_name: str,
    ) -> bool:
        """Update an approval message to show the decision.

        Replaces the interactive buttons with a confirmation banner.
        """
        emoji = "✅" if action == "approve" else "❌"
        verb = "APPROVED" if action == "approve" else "REJECTED"

        blocks: list[dict[str, Any]] = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"{emoji} *Payout `{payout_id}` {verb}*\n"
                        f"Decision by <@{user_name}>"
                    ),
                },
            },
        ]

        payload: dict[str, Any] = {
            "channel": channel,
            "ts": message_ts,
            "blocks": blocks,
            "text": f"Payout {payout_id} {verb} by {user_name}",
        }

        try:
            response = await self._http.post(
                "/chat.update",
                json=payload,
            )
            data = response.json()
            return bool(data.get("ok"))
        except Exception as e:
            logger.error("Failed to update Slack message: %s", e)
            return False

    # ================================================================
    # Block Kit Message Builders
    # ================================================================

    @staticmethod
    def _build_approval_blocks(
        result: GovernanceResult,
        amount_rupees: float,
        vendor_name: str | None,
        vendor_url: str | None,
    ) -> list[dict[str, Any]]:
        """Build Slack Block Kit blocks for an approval request."""
        vendor_display = vendor_name or vendor_url or "Unknown Vendor"

        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔔 Payout Approval Required",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Payout ID:*\n`{result.payout_id}`",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Amount:*\n₹{amount_rupees:,.2f} ({result.amount} paise)",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Agent:*\n`{result.agent_id}`",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Vendor:*\n{vendor_display}",
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Reason:* {result.reason_detail}",
                },
            },
            {
                "type": "actions",
                "block_id": f"approval_{result.payout_id}",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✅ Approve",
                            "emoji": True,
                        },
                        "style": "primary",
                        "action_id": "approve_payout",
                        "value": result.payout_id,
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "❌ Reject",
                            "emoji": True,
                        },
                        "style": "danger",
                        "action_id": "reject_payout",
                        "value": result.payout_id,
                    },
                ],
            },
            {
                "type": "divider",
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            "⚖️ *Vyapaar MCP* — Agentic Financial Governance | "
                            f"Processing: {result.processing_ms}ms"
                        ),
                    },
                ],
            },
        ]
        return blocks

    @staticmethod
    def _build_rejection_blocks(
        result: GovernanceResult,
        amount_rupees: float,
        vendor_name: str | None,
        vendor_url: str | None,
    ) -> list[dict[str, Any]]:
        """Build Slack Block Kit blocks for a rejection alert."""
        vendor_display = vendor_name or vendor_url or "Unknown Vendor"

        # Emoji based on reason
        reason_emoji = {
            ReasonCode.RISK_HIGH: "🦠",
            ReasonCode.DOMAIN_BLOCKED: "🚫",
            ReasonCode.LIMIT_EXCEEDED: "💰",
            ReasonCode.TXN_LIMIT_EXCEEDED: "💸",
            ReasonCode.NO_POLICY: "📋",
        }
        emoji = reason_emoji.get(result.reason_code, "❌")

        threat_text = ""
        if result.threat_types:
            threat_text = f"\n*Threats Detected:* {', '.join(result.threat_types)}"

        blocks: list[dict[str, Any]] = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} Payout Rejected — {result.reason_code.value}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Payout ID:*\n`{result.payout_id}`",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Amount:*\n₹{amount_rupees:,.2f}",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Agent:*\n`{result.agent_id}`",
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Vendor:*\n{vendor_display}",
                    },
                ],
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Detail:* {result.reason_detail}{threat_text}",
                },
            },
            {
                "type": "divider",
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            "⚖️ *Vyapaar MCP* — Agentic Financial Governance | "
                            f"Processing: {result.processing_ms}ms"
                        ),
                    },
                ],
            },
        ]
        return blocks


# ================================================================
# Notification Decision Logic
# ================================================================


async def notify_slack(
    notifier: SlackNotifier | None,
    result: GovernanceResult,
    vendor_name: str | None = None,
    vendor_url: str | None = None,
) -> None:
    """Send Slack notification based on governance decision.

    Per SPEC §8 Decision Matrix:
    - HELD → Slack approval request
    - REJECTED (security reasons) → Slack alert
    - APPROVED → No notification (logged silently)
    """
    if notifier is None:
        return

    try:
        if result.decision == Decision.HELD:
            success = await notifier.request_approval(
                result,
                vendor_name=vendor_name,
                vendor_url=vendor_url,
            )
            metrics.record_slack_notification(success=success)
        elif result.decision == Decision.REJECTED:
            # Only alert on security-relevant rejections
            alert_reasons = {
                ReasonCode.RISK_HIGH,
                ReasonCode.DOMAIN_BLOCKED,
                ReasonCode.LIMIT_EXCEEDED,
                ReasonCode.NO_POLICY,
            }
            if result.reason_code in alert_reasons:
                success = await notifier.send_rejection_alert(
                    result,
                    vendor_name=vendor_name,
                    vendor_url=vendor_url,
                )
                metrics.record_slack_notification(success=success)
    except Exception as e:
        # Slack failures should never block the governance pipeline
        metrics.record_slack_notification(success=False)
        logger.error("Slack notification error (non-fatal): %s", e)
