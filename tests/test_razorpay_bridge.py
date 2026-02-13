"""Tests for the RazorpayBridge (Go MCP subprocess integration).

Tests the bridge's ability to:
1. Initialize and locate the Go binary
2. Spawn the Go MCP server subprocess
3. Communicate via MCP/stdio protocol
4. Call tools (list_tools, fetch_all_payouts, ping)

These tests require:
- Go binary built at bin/razorpay-mcp-server
- Valid Razorpay API credentials in .env
"""

from __future__ import annotations

import os
import pytest

from vyapaar_mcp.ingress.razorpay_bridge import RazorpayBridge, DEFAULT_BINARY_PATH

# Skip all tests if Go binary not built
GO_BINARY_EXISTS = os.path.isfile(DEFAULT_BINARY_PATH)
pytestmark = pytest.mark.skipif(
    not GO_BINARY_EXISTS,
    reason=f"Go binary not found at {DEFAULT_BINARY_PATH}. "
           f"Build: cd vendor/razorpay-mcp-server && "
           f"go build -o ../../bin/razorpay-mcp-server ./cmd/razorpay-mcp-server",
)


# ================================================================
# Unit Tests (no network needed)
# ================================================================


class TestBridgeInit:
    """Test bridge initialization."""

    def test_init_with_valid_binary(self) -> None:
        """Bridge initializes when binary exists."""
        bridge = RazorpayBridge(
            key_id="rzp_test_1234",
            key_secret="test_secret",
        )
        assert bridge._binary_path == DEFAULT_BINARY_PATH
        assert bridge._key_id == "rzp_test_1234"

    def test_init_with_missing_binary(self) -> None:
        """Bridge raises FileNotFoundError for missing binary."""
        with pytest.raises(FileNotFoundError, match="razorpay-mcp-server"):
            RazorpayBridge(
                key_id="rzp_test_1234",
                key_secret="test_secret",
                binary_path="/nonexistent/binary",
            )

    def test_init_with_custom_binary_path(self) -> None:
        """Bridge accepts custom binary path."""
        bridge = RazorpayBridge(
            key_id="rzp_test_1234",
            key_secret="test_secret",
            binary_path=DEFAULT_BINARY_PATH,
        )
        assert bridge._binary_path == DEFAULT_BINARY_PATH


# ================================================================
# Integration Tests (require API credentials)
# ================================================================


@pytest.fixture
def bridge() -> RazorpayBridge:
    """Create a bridge with credentials from .env."""
    from vyapaar_mcp.config import load_config
    config = load_config()
    return RazorpayBridge(
        key_id=config.razorpay_key_id,
        key_secret=config.razorpay_key_secret,
    )


@pytest.fixture
def account_number() -> str:
    """Get account number from config."""
    from vyapaar_mcp.config import load_config
    return load_config().razorpay_account_number


class TestBridgeConnectivity:
    """Test MCP subprocess communication with Go binary."""

    async def test_ping(self, bridge: RazorpayBridge) -> None:
        """Go binary spawns and responds to health check."""
        result = await bridge.ping()
        assert result is True

    async def test_list_tools(self, bridge: RazorpayBridge) -> None:
        """Go binary exposes 40+ Razorpay tools."""
        tools = await bridge.list_tools()
        assert len(tools) >= 40
        # Key tools must be present
        assert "fetch_all_payouts" in tools
        assert "fetch_payout_with_id" in tools
        assert "fetch_all_payments" in tools
        assert "fetch_payment" in tools
        assert "create_order" in tools
        assert "create_refund" in tools

    async def test_fetch_all_payouts(
        self,
        bridge: RazorpayBridge,
        account_number: str,
    ) -> None:
        """Fetch payouts via Go SDK's native Payout.All()."""
        result = await bridge.fetch_all_payouts(
            account_number=account_number,
            count=5,
        )
        # Response should have standard Razorpay structure
        assert "items" in result
        assert "count" in result
        assert isinstance(result["items"], list)

    async def test_fetch_all_payouts_with_status_filter(
        self,
        bridge: RazorpayBridge,
        account_number: str,
    ) -> None:
        """Status filter works (client-side filtering)."""
        result = await bridge.fetch_all_payouts(
            account_number=account_number,
            count=5,
            status="queued",
        )
        assert "items" in result
        # All items should be queued (if any exist)
        for item in result["items"]:
            assert item["status"] == "queued"

    async def test_fetch_all_payments(
        self,
        bridge: RazorpayBridge,
    ) -> None:
        """Fetch payments via Go SDK."""
        result = await bridge.fetch_all_payments(count=3)
        assert "items" in result
        assert isinstance(result["items"], list)
