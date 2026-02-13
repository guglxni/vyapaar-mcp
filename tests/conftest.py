"""Shared test fixtures for Vyapaar MCP test suite."""

from __future__ import annotations

import hashlib
import hmac
import json
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio

from vyapaar_mcp.config import VyapaarConfig
from vyapaar_mcp.db.redis_client import RedisClient
from vyapaar_mcp.models import AgentPolicy

# ================================================================
# Configuration Fixture
# ================================================================


@pytest.fixture
def config() -> VyapaarConfig:
    """Test configuration with dummy values."""
    return VyapaarConfig(
        razorpay_key_id="rzp_test_1234567890",
        razorpay_key_secret="test_secret_key_12345",
        razorpay_webhook_secret="test_webhook_secret",
        google_safe_browsing_key="test_gsb_key_12345",
        redis_url="redis://localhost:6379/0",
        postgres_dsn="postgresql://vyapaar:securepass@localhost:5432/vyapaar_test",
    )


# ================================================================
# Redis Fixture (using fakeredis)
# ================================================================


@pytest_asyncio.fixture
async def fake_redis() -> AsyncGenerator[RedisClient, None]:
    """Create a fakeredis-backed RedisClient for testing."""
    try:
        from fakeredis.aioredis import FakeRedis as FakeAioRedis
    except ImportError:
        pytest.skip("fakeredis not installed")

    client = RedisClient(url="redis://fake:6379/0")
    # Replace the real client with fakeredis
    client._client = FakeAioRedis(decode_responses=True)
    yield client


# ================================================================
# Mock PostgreSQL Fixture
# ================================================================


@pytest.fixture
def mock_postgres() -> MagicMock:
    """Mock PostgreSQL client."""
    mock = MagicMock()

    # Default policy for testing
    default_policy = AgentPolicy(
        agent_id="test-agent-001",
        daily_limit=500000,  # ₹5,000
        per_txn_limit=100000,  # ₹1,000
        require_approval_above=50000,  # ₹500
        blocked_domains=["evil.com", "malware.org"],
    )

    mock.get_agent_policy = AsyncMock(return_value=default_policy)
    mock.upsert_agent_policy = AsyncMock(return_value=default_policy)
    mock.write_audit_log = AsyncMock()
    mock.get_audit_logs = AsyncMock(return_value=[])
    mock.ping = AsyncMock(return_value=True)

    return mock


# ================================================================
# Webhook Helpers
# ================================================================


def make_webhook_payload(
    payout_id: str = "pout_test_123456",
    amount: int = 50000,
    agent_id: str = "test-agent-001",
    vendor_url: str = "https://safe-vendor.com",
    status: str = "queued",
) -> dict[str, Any]:
    """Create a realistic Razorpay webhook payload for testing."""
    return {
        "entity": "event",
        "account_id": "acc_test_12345",
        "event": "payout.queued",
        "contains": ["payout"],
        "payload": {
            "payout": {
                "entity": {
                    "id": payout_id,
                    "entity": "payout",
                    "fund_account_id": "fa_test_12345",
                    "amount": amount,
                    "currency": "INR",
                    "notes": {
                        "agent_id": agent_id,
                        "purpose": "vendor_payment",
                        "vendor_url": vendor_url,
                    },
                    "fees": 590,
                    "tax": 90,
                    "status": status,
                    "purpose": "payout",
                    "mode": "NEFT",
                    "reference_id": f"txn_test_{payout_id}",
                    "fund_account": {
                        "id": "fa_test_12345",
                        "entity": "fund_account",
                        "contact_id": "cont_test_12345",
                        "account_type": "bank_account",
                        "bank_account": {
                            "ifsc": "HDFC0000001",
                            "bank_name": "HDFC Bank",
                            "name": "Test Vendor Pvt Ltd",
                            "account_number": "1234567890123456",
                        },
                        "contact": {
                            "id": "cont_test_12345",
                            "entity": "contact",
                            "name": "Test Vendor Pvt Ltd",
                            "type": "vendor",
                            "email": "vendor@safe-vendor.com",
                        },
                    },
                    "created_at": 1707561564,
                }
            }
        },
        "created_at": 1707561564,
    }


def sign_payload(payload: dict[str, Any] | bytes, secret: str) -> str:
    """Generate HMAC-SHA256 signature for a webhook payload."""
    body = json.dumps(payload).encode("utf-8") if isinstance(payload, dict) else payload

    return hmac.new(
        key=secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()
