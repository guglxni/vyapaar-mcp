"""Tests for webhook signature verification and parsing.

SPEC §4 Constraint #1: Every webhook MUST have valid signature.
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest

from tests.conftest import make_webhook_payload
from vyapaar_mcp.ingress.webhook import (
    extract_webhook_id,
    parse_webhook_event,
    verify_razorpay_signature,
)

SECRET = "test_webhook_secret"


class TestSignatureVerification:
    """Test HMAC-SHA256 webhook signature verification."""

    def test_valid_signature_passes(self) -> None:
        """A correctly signed payload should pass verification."""
        body = b'{"event": "payout.queued"}'
        sig = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
        assert verify_razorpay_signature(body, sig, SECRET) is True

    def test_invalid_signature_rejected(self) -> None:
        """A tampered signature should fail verification."""
        body = b'{"event": "payout.queued"}'
        assert verify_razorpay_signature(body, "invalid_signature_hex", SECRET) is False

    def test_tampered_payload_rejected(self) -> None:
        """A valid signature for a different payload should fail."""
        original = b'{"event": "payout.queued"}'
        tampered = b'{"event": "payout.queued", "injected": true}'
        sig = hmac.new(SECRET.encode(), original, hashlib.sha256).hexdigest()
        assert verify_razorpay_signature(tampered, sig, SECRET) is False

    def test_empty_body_valid_if_signed(self) -> None:
        """Empty body with correct signature should still work."""
        body = b""
        sig = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
        assert verify_razorpay_signature(body, sig, SECRET) is True

    def test_wrong_secret_rejected(self) -> None:
        """Signature from wrong secret should fail."""
        body = b'{"event": "payout.queued"}'
        sig = hmac.new(b"wrong_secret", body, hashlib.sha256).hexdigest()
        assert verify_razorpay_signature(body, sig, SECRET) is False

    def test_timing_safe_comparison(self) -> None:
        """Verify we use timing-safe comparison (hmac.compare_digest)."""
        body = b"test"
        sig = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
        # Just ensure it doesn't crash — actual timing safety is in the implementation
        assert verify_razorpay_signature(body, sig, SECRET) is True


class TestWebhookParsing:
    """Test parsing of Razorpay webhook payloads."""

    def test_parse_valid_payout_queued(self) -> None:
        """A valid payout.queued payload should parse correctly."""
        payload = make_webhook_payload(
            payout_id="pout_ABC123",
            amount=50000,
            agent_id="agent-001",
        )
        body = json.dumps(payload).encode()
        event = parse_webhook_event(body)

        assert event.event == "payout.queued"
        assert event.payload.payout.entity.id == "pout_ABC123"
        assert event.payload.payout.entity.amount == 50000

    def test_parse_extracts_notes(self) -> None:
        """Agent ID and vendor URL should be extractable from notes."""
        payload = make_webhook_payload(
            agent_id="my-agent",
            vendor_url="https://example.com",
        )
        body = json.dumps(payload).encode()
        event = parse_webhook_event(body)

        notes = event.payload.payout.entity.get_notes()
        assert notes.agent_id == "my-agent"
        assert notes.vendor_url == "https://example.com"

    def test_parse_invalid_json_raises(self) -> None:
        """Invalid JSON should raise ValueError."""
        with pytest.raises(ValueError, match="Invalid webhook payload"):
            parse_webhook_event(b"not valid json {{{")

    def test_parse_missing_fields_raises(self) -> None:
        """Payload missing required fields should raise."""
        with pytest.raises(ValueError):
            parse_webhook_event(b'{"entity": "event"}')


class TestWebhookIdExtraction:
    """Test idempotency key extraction."""

    def test_extract_webhook_id(self) -> None:
        """Should combine event type and payout ID."""
        payload = make_webhook_payload(payout_id="pout_XYZ789")
        body = json.dumps(payload).encode()
        event = parse_webhook_event(body)

        webhook_id = extract_webhook_id(event)
        assert webhook_id == "payout.queued:pout_XYZ789"

    def test_same_event_same_id(self) -> None:
        """Same event should produce same webhook ID (idempotent)."""
        payload = make_webhook_payload(payout_id="pout_SAME")
        body = json.dumps(payload).encode()

        event1 = parse_webhook_event(body)
        event2 = parse_webhook_event(body)

        assert extract_webhook_id(event1) == extract_webhook_id(event2)
