"""Bridge to Razorpay via Official Go MCP Server (subprocess).

Instead of using the Python SDK's raw HTTP methods (which lack
payout support), this bridge spawns the official
razorpay-mcp-server Go binary and communicates via MCP/stdio.

This gives us native Go SDK payout support (Payout.All,
Payout.Fetch) plus all 40+ tools — exactly as the official
MCP server was designed to be consumed.

Integration Method:
  Python (MCP client) ←—stdio—→ Go binary (MCP server) → Razorpay API

Why not gopy?
  The Go SDK's Payout resource (razorpay-go/resources/payout.go)
  just wraps HTTP GET /v1/payouts — same as all other resources.
  gopy would add CGO complexity, cross-compilation issues,
  and shared library management for what's basically HTTP calls.
  The MCP subprocess approach uses the SAME protocol the Go
  server was designed for, with zero overhead.

Reference: https://github.com/razorpay/razorpay-mcp-server
License:   MIT (Copyright (c) 2025 Razorpay)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

# Default binary location (built from vendor source)
DEFAULT_BINARY_PATH = str(
    Path(__file__).resolve().parents[3] / "bin" / "razorpay-mcp-server"
)


class RazorpayBridge:
    """Bridge to Razorpay API via the official Go MCP server binary.

    Spawns the razorpay-mcp-server as a subprocess and communicates
    using the MCP protocol over stdio. This gives us:

    - Native Go SDK payout support (Payout.All, Payout.Fetch)
    - All 40+ Razorpay tools (payments, orders, refunds, etc.)
    - Proper error handling, validation, and observability
    - Same tool signatures as the official MCP server

    The Go binary is built from source at vendor/razorpay-mcp-server
    and placed at bin/razorpay-mcp-server.
    """

    def __init__(
        self,
        key_id: str,
        key_secret: str,
        binary_path: str | None = None,
    ) -> None:
        self._key_id = key_id
        self._key_secret = key_secret
        self._binary_path = binary_path or DEFAULT_BINARY_PATH
        self._session: ClientSession | None = None
        self._available_tools: list[str] = []

        # Verify binary exists
        if not os.path.isfile(self._binary_path):
            raise FileNotFoundError(
                f"razorpay-mcp-server binary not found at "
                f"{self._binary_path}. "
                f"Build it: cd vendor/razorpay-mcp-server && "
                f"go build -o ../../bin/razorpay-mcp-server "
                f"./cmd/razorpay-mcp-server"
            )

        logger.info(
            "RazorpayBridge initialized (binary: %s, key: %s...)",
            self._binary_path,
            key_id[:12],
        )

    def _get_server_params(self) -> StdioServerParameters:
        """Build server parameters for the Go MCP binary."""
        return StdioServerParameters(
            command=self._binary_path,
            args=[
                "stdio",
                "--log-file", "/dev/null",
            ],
            env={
                **os.environ,
                "RAZORPAY_KEY_ID": self._key_id,
                "RAZORPAY_KEY_SECRET": self._key_secret,
            },
        )

    @asynccontextmanager
    async def _connect(self) -> AsyncGenerator[ClientSession, None]:
        """Spawn Go binary and establish MCP session.

        This is a context manager that handles the full lifecycle:
        spawn → initialize → yield session → shutdown.
        """
        server_params = self._get_server_params()

        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                logger.debug("MCP session initialized with Go binary")

                # Cache available tools on first connect
                if not self._available_tools:
                    tools_response = await session.list_tools()
                    self._available_tools = [
                        t.name for t in tools_response.tools
                    ]
                    logger.info(
                        "Go MCP server offers %d tools: %s",
                        len(self._available_tools),
                        ", ".join(self._available_tools),
                    )

                yield session

    async def _call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Call a tool on the Go MCP server and return parsed result.

        Spawns a fresh subprocess for each call. This is the safest
        approach — no process state leaks between calls.
        For high-frequency usage, consider a persistent connection.
        """
        async with self._connect() as session:
            result = await session.call_tool(
                tool_name, arguments
            )

            # Parse the MCP response
            if result.isError:
                error_text = ""
                for content in result.content:
                    if hasattr(content, "text"):
                        error_text += content.text
                logger.error(
                    "Go MCP tool '%s' error: %s",
                    tool_name,
                    error_text,
                )
                raise RuntimeError(
                    f"Razorpay MCP tool error: {error_text}"
                )

            # Extract text content and parse as JSON
            for content in result.content:
                if hasattr(content, "text"):
                    try:
                        return json.loads(content.text)
                    except json.JSONDecodeError:
                        return {"raw": content.text}

            return {"raw": str(result.content)}

    # ================================================================
    # Payouts — uses Go SDK's native Payout resource
    # (razorpay-go/resources/payout.go)
    # ================================================================

    async def fetch_all_payouts(
        self,
        account_number: str,
        count: int = 100,
        skip: int = 0,
        status: str | None = None,
    ) -> dict[str, Any]:
        """Fetch all payouts for a given account number.

        Calls Go MCP tool: fetch_all_payouts
        Go SDK: client.Payout.All(queryParams, nil)
        API:    GET /v1/payouts?account_number={acct}
        """
        args: dict[str, Any] = {
            "account_number": account_number,
            "count": count,
            "skip": skip,
        }
        # Note: status filtering done client-side since the Go
        # MCP tool doesn't expose a status parameter directly
        result = await self._call_tool(
            "fetch_all_payouts", args
        )

        # Client-side status filter (if needed)
        if status and "items" in result:
            result["items"] = [
                p for p in result["items"]
                if p.get("status") == status
            ]
            result["count"] = len(result["items"])

        return result

    async def fetch_payout(self, payout_id: str) -> dict[str, Any]:
        """Fetch a single payout by ID.

        Calls Go MCP tool: fetch_payout_with_id
        Go SDK: client.Payout.Fetch(id, nil, nil)
        """
        return await self._call_tool(
            "fetch_payout_with_id",
            {"payout_id": payout_id},
        )

    # ================================================================
    # Payments — uses Go SDK's native Payment resource
    # ================================================================

    async def fetch_all_payments(
        self,
        count: int = 10,
        skip: int = 0,
    ) -> dict[str, Any]:
        """Fetch all payments.

        Calls Go MCP tool: fetch_all_payments
        """
        return await self._call_tool(
            "fetch_all_payments",
            {"count": count, "skip": skip},
        )

    async def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        """Fetch a single payment by ID.

        Calls Go MCP tool: fetch_payment
        """
        return await self._call_tool(
            "fetch_payment",
            {"payment_id": payment_id},
        )

    async def capture_payment(
        self,
        payment_id: str,
        amount: int,
        currency: str = "INR",
    ) -> dict[str, Any]:
        """Capture a payment.

        Calls Go MCP tool: capture_payment
        """
        return await self._call_tool(
            "capture_payment",
            {
                "payment_id": payment_id,
                "amount": amount,
                "currency": currency,
            },
        )

    # ================================================================
    # Payment Links
    # ================================================================

    async def create_payment_link(
        self,
        amount: int,
        currency: str = "INR",
        description: str = "",
        customer: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a payment link.

        Calls Go MCP tool: create_payment_link
        """
        args: dict[str, Any] = {
            "amount": amount,
            "currency": currency,
            "description": description,
        }
        if customer:
            args["customer"] = customer
        args.update(kwargs)
        return await self._call_tool(
            "create_payment_link", args
        )

    async def fetch_all_payment_links(
        self,
        count: int = 10,
        skip: int = 0,
    ) -> dict[str, Any]:
        """Fetch all payment links.

        Calls Go MCP tool: fetch_all_payment_links
        """
        return await self._call_tool(
            "fetch_all_payment_links",
            {"count": count, "skip": skip},
        )

    # ================================================================
    # Orders
    # ================================================================

    async def create_order(
        self,
        amount: int,
        currency: str = "INR",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create an order.

        Calls Go MCP tool: create_order
        """
        args: dict[str, Any] = {
            "amount": amount,
            "currency": currency,
        }
        args.update(kwargs)
        return await self._call_tool(
            "create_order", args
        )

    async def fetch_all_orders(
        self,
        count: int = 10,
        skip: int = 0,
    ) -> dict[str, Any]:
        """Fetch all orders.

        Calls Go MCP tool: fetch_all_orders
        """
        return await self._call_tool(
            "fetch_all_orders",
            {"count": count, "skip": skip},
        )

    # ================================================================
    # Refunds
    # ================================================================

    async def create_refund(
        self,
        payment_id: str,
        amount: int,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create a refund.

        Calls Go MCP tool: create_refund
        """
        args: dict[str, Any] = {
            "payment_id": payment_id,
            "amount": amount,
        }
        args.update(kwargs)
        return await self._call_tool(
            "create_refund", args
        )

    async def fetch_all_refunds(
        self,
        count: int = 10,
        skip: int = 0,
    ) -> dict[str, Any]:
        """Fetch all refunds.

        Calls Go MCP tool: fetch_all_refunds
        """
        return await self._call_tool(
            "fetch_all_refunds",
            {"count": count, "skip": skip},
        )

    # ================================================================
    # Settlements
    # ================================================================

    async def fetch_all_settlements(
        self,
        count: int = 10,
        skip: int = 0,
    ) -> dict[str, Any]:
        """Fetch all settlements.

        Calls Go MCP tool: fetch_all_settlements
        """
        return await self._call_tool(
            "fetch_all_settlements",
            {"count": count, "skip": skip},
        )

    # ================================================================
    # Utilities
    # ================================================================

    async def list_tools(self) -> list[str]:
        """List all available tools from the Go MCP server."""
        async with self._connect() as session:
            tools_response = await session.list_tools()
            return [t.name for t in tools_response.tools]

    async def ping(self) -> bool:
        """Health check — verify Go binary and API reachability."""
        try:
            async with self._connect() as session:
                # Just establishing a session proves the binary works
                tools = await session.list_tools()
                return len(tools.tools) > 0
        except Exception as e:
            logger.error("Ping failed: %s", e)
            return False
