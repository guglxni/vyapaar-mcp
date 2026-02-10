"""Razorpay webhook handler — ingress point for Vyapaar MCP.

CRITICAL SECURITY:
- Every webhook MUST have its X-Razorpay-Signature verified via HMAC-SHA256.
- Replayed webhooks are detected via Redis SETNX idempotency.
- Invalid signatures return 401 immediately.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from vyapaar_mcp.models import RazorpayWebhookEvent

logger = logging.getLogger(__name__)


def verify_razorpay_signature(
    payload_body: bytes,
    signature: str,
    secret: str,
) -> bool:
    """Verify Razorpay webhook signature using HMAC-SHA256.

    Uses hmac.compare_digest for timing-attack-safe comparison.

    Args:
        payload_body: Raw request body bytes.
        signature: Value of X-Razorpay-Signature header.
        secret: Razorpay webhook signing secret.

    Returns:
        True if signature is valid, False otherwise.
    """
    expected = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    is_valid = hmac.compare_digest(expected, signature)

    if not is_valid:
        logger.warning("Webhook signature verification FAILED")
    else:
        logger.debug("Webhook signature verified OK")

    return is_valid


def parse_webhook_event(payload_body: bytes) -> RazorpayWebhookEvent:
    """Parse raw webhook body into a typed Pydantic model.

    Args:
        payload_body: Raw JSON bytes from the webhook request.

    Returns:
        Parsed RazorpayWebhookEvent model.

    Raises:
        ValueError: If the payload cannot be parsed.
    """
    try:
        data: dict[str, Any] = json.loads(payload_body)
        event = RazorpayWebhookEvent(**data)
        logger.info(
            "Parsed webhook: event=%s payout_id=%s amount=%d",
            event.event,
            event.payload.payout.entity.id,
            event.payload.payout.entity.amount,
        )
        return event
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error("Failed to parse webhook payload: %s", e)
        raise ValueError(f"Invalid webhook payload: {e}") from e


def extract_webhook_id(event: RazorpayWebhookEvent) -> str:
    """Extract a unique webhook ID for idempotency checking.

    Uses the payout ID + event type as the dedup key.
    """
    payout_id = event.payload.payout.entity.id
    event_type = event.event
    return f"{event_type}:{payout_id}"
