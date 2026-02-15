"""Razorpay webhook handler — ingress point for Vyapaar MCP.

CRITICAL SECURITY:
- Every webhook MUST have its X-Razorpay-Signature verified via HMAC-SHA256.
- Replayed webhooks are detected via Redis SETNX idempotency.
- Invalid signatures return 401 immediately.
- All payloads are validated for size and format before processing.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from typing import Any

from vyapaar_mcp.models import RazorpayWebhookEvent

logger = logging.getLogger(__name__)

# Maximum webhook payload size: 1MB
MAX_PAYLOAD_SIZE = 1024 * 1024


class WebhookValidationError(Exception):
    """Raised when webhook payload fails validation."""

    def __init__(self, message: str, code: str = "VALIDATION_ERROR") -> None:
        self.code = code
        super().__init__(message)


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


def validate_webhook_payload(payload: str) -> bytes:
    """Validate and sanitize webhook payload before processing.
    
    Implements fail-fast input validation per API security best practices.
    
    Args:
        payload: Raw webhook payload string.
        
    Returns:
        Validated payload as bytes.
        
    Raises:
        WebhookValidationError: If payload fails validation.
    """
    # Check for empty payload
    if not payload:
        raise WebhookValidationError(
            "Empty webhook payload",
            code="EMPTY_PAYLOAD"
        )
    
    # Encode to bytes for size check
    payload_bytes = payload.encode("utf-8")
    
    # Check payload size (DoS protection)
    if len(payload_bytes) > MAX_PAYLOAD_SIZE:
        raise WebhookValidationError(
            f"Webhook payload exceeds maximum size of {MAX_PAYLOAD_SIZE} bytes",
            code="PAYLOAD_TOO_LARGE"
        )
    
    # Check for obviously malformed data (potential injection)
    if len(payload_bytes) < 10:  # Minimum reasonable size
        raise WebhookValidationError(
            "Webhook payload too short to be valid",
            code="PAYLOAD_TOO_SHORT"
        )
    
    return payload_bytes
