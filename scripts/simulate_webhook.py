#!/usr/bin/env python3
"""Simulate payout events for demo and testing.

Usage:
    PYTHONPATH=src python scripts/simulate_webhook.py

Demonstrates the APPROVE → REJECT → HOLD decision flow
using the poll_razorpay_payouts MCP tool and the
RazorpayBridge's Go MCP subprocess.

Per SPEC §11 Phase 7 & §19 Nice-to-Have.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vyapaar_mcp.config import load_config
from vyapaar_mcp.ingress.razorpay_bridge import RazorpayBridge
from vyapaar_mcp.ingress.webhook import verify_razorpay_signature
from vyapaar_mcp.models import PayoutEntity


# ================================================================
# Mock Payout Data (simulates what Razorpay API would return)
# ================================================================

MOCK_PAYOUTS = [
    {
        "id": "pout_demo_approved_001",
        "entity": "payout",
        "fund_account_id": "fa_demo_001",
        "amount": 25000,  # ₹250 — should be APPROVED
        "currency": "INR",
        "notes": {
            "agent_id": "openclaw-agent-001",
            "purpose": "vendor_payment",
            "vendor_url": "https://safe-vendor.com",
        },
        "status": "queued",
        "mode": "NEFT",
        "created_at": 1707561564,
    },
    {
        "id": "pout_demo_rejected_002",
        "entity": "payout",
        "fund_account_id": "fa_demo_002",
        "amount": 200000,  # ₹2,000 — exceeds per-txn limit (₹1,000)
        "currency": "INR",
        "notes": {
            "agent_id": "openclaw-agent-001",
            "purpose": "vendor_payment",
            "vendor_url": "https://example.com",
        },
        "status": "queued",
        "mode": "IMPS",
        "created_at": 1707561565,
    },
    {
        "id": "pout_demo_held_003",
        "entity": "payout",
        "fund_account_id": "fa_demo_003",
        "amount": 75000,  # ₹750 — above approval threshold (₹500)
        "currency": "INR",
        "notes": {
            "agent_id": "openclaw-agent-001",
            "purpose": "vendor_payment",
            "vendor_url": "https://trusted-vendor.com",
        },
        "status": "queued",
        "mode": "NEFT",
        "created_at": 1707561566,
    },
    {
        "id": "pout_demo_blocked_004",
        "entity": "payout",
        "fund_account_id": "fa_demo_004",
        "amount": 10000,  # ₹100 — but vendor domain is blocked
        "currency": "INR",
        "notes": {
            "agent_id": "openclaw-agent-001",
            "purpose": "vendor_payment",
            "vendor_url": "https://evil.com/pay",
        },
        "status": "queued",
        "mode": "NEFT",
        "created_at": 1707561567,
    },
]


def print_header() -> None:
    """Print demo header."""
    print()
    print("=" * 70)
    print("  🔥 Vyapaar MCP — Governance Decision Demo")
    print("  The CFO for the Agentic Economy")
    print("=" * 70)
    print()
    print("  This simulates 4 payout scenarios:")
    print("  1. ✅ APPROVE — ₹250 to safe vendor")
    print("  2. ❌ REJECT  — ₹2,000 exceeds per-txn limit")
    print("  3. ⏸  HOLD    — ₹750 above approval threshold")
    print("  4. 🚫 REJECT  — ₹100 to blocked domain")
    print()


def print_payout(idx: int, payout: dict) -> None:
    """Print a payout scenario."""
    notes = payout.get("notes", {})
    amount_rupees = payout["amount"] / 100
    print(f"  ┌─ Payout #{idx + 1}: {payout['id']}")
    print(f"  │  Amount:  ₹{amount_rupees:,.2f} ({payout['amount']} paise)")
    print(f"  │  Agent:   {notes.get('agent_id', 'unknown')}")
    print(f"  │  Vendor:  {notes.get('vendor_url', 'none')}")
    print(f"  │  Mode:    {payout.get('mode', 'NEFT')}")


def print_decision(decision: str, reason: str, detail: str) -> None:
    """Print governance decision."""
    icons = {"APPROVED": "✅", "REJECTED": "❌", "HELD": "⏸ "}
    icon = icons.get(decision, "❓")
    print(f"  │  Decision: {icon} {decision}")
    print(f"  │  Reason:   {reason}")
    print(f"  │  Detail:   {detail}")
    print(f"  └{'─' * 50}")
    print()


async def demo_webhook_signature() -> None:
    """Demo: Signature verification."""
    print("─" * 70)
    print("  📝 Demo: Webhook Signature Verification")
    print("─" * 70)
    print()

    secret = "test_webhook_secret"
    body = json.dumps(MOCK_PAYOUTS[0]).encode("utf-8")

    # Valid signature
    import hashlib
    import hmac as hmac_mod
    valid_sig = hmac_mod.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    result = verify_razorpay_signature(body, valid_sig, secret)
    print(f"  Valid signature:   {'✅ PASS' if result else '❌ FAIL'}")

    # Tampered payload
    tampered = body + b"INJECTED"
    result = verify_razorpay_signature(tampered, valid_sig, secret)
    print(f"  Tampered payload:  {'❌ FAIL (correct!)' if not result else '✅ PASS (wrong!)'}")

    # Wrong secret
    result = verify_razorpay_signature(body, valid_sig, "wrong_secret")
    print(f"  Wrong secret:      {'❌ FAIL (correct!)' if not result else '✅ PASS (wrong!)'}")
    print()


async def demo_go_bridge() -> None:
    """Demo: Go MCP bridge connectivity."""
    print("─" * 70)
    print("  🔗 Demo: Go MCP Bridge Connection")
    print("─" * 70)
    print()

    try:
        config = load_config()
        bridge = RazorpayBridge(
            key_id=config.razorpay_key_id,
            key_secret=config.razorpay_key_secret,
        )

        ok = await bridge.ping()
        print(f"  Go binary health:  {'✅ healthy' if ok else '❌ unreachable'}")

        tools = await bridge.list_tools()
        print(f"  Available tools:   {len(tools)}")

        result = await bridge.fetch_all_payouts(
            account_number=config.razorpay_account_number,
            count=1,
        )
        count = result.get("count", 0)
        print(f"  Live payouts:      {count}")
        print()

    except Exception as e:
        print(f"  ⚠️  Bridge not available: {e}")
        print(f"     (Build: cd vendor/razorpay-mcp-server && go build ...)")
        print()


async def demo_model_parsing() -> None:
    """Demo: Pydantic model parsing."""
    print("─" * 70)
    print("  📦 Demo: Payout Model Parsing")
    print("─" * 70)
    print()

    for i, raw in enumerate(MOCK_PAYOUTS):
        payout = PayoutEntity(**raw)
        agent_id = payout.notes.agent_id if payout.notes else "N/A"
        print(f"  Payout {i + 1}: {payout.id}")
        print(f"    Amount: {payout.amount} paise (₹{payout.amount / 100:,.2f})")
        print(f"    Agent:  {agent_id}")
        print(f"    Status: {payout.status}")
        print()


async def main() -> None:
    """Run the full demo."""
    print_header()

    # Demo 1: Signature verification
    await demo_webhook_signature()

    # Demo 2: Model parsing
    await demo_model_parsing()

    # Demo 3: Go MCP bridge
    await demo_go_bridge()

    # Demo 4: Show mock governance scenarios
    print("─" * 70)
    print("  ⚖️  Demo: Governance Decision Scenarios (Mock)")
    print("─" * 70)
    print()

    scenarios = [
        ("APPROVED", "POLICY_OK", "All governance checks passed"),
        ("REJECTED", "TXN_LIMIT_EXCEEDED", "Amount 200000 paise exceeds per-txn limit of 100000 paise"),
        ("HELD", "APPROVAL_REQUIRED", "Amount 75000 paise exceeds approval threshold of 50000 paise"),
        ("REJECTED", "DOMAIN_BLOCKED", "Vendor domain 'evil.com' is on the blocklist"),
    ]

    for i, (payout, (decision, reason, detail)) in enumerate(zip(MOCK_PAYOUTS, scenarios)):
        print_payout(i, payout)
        print_decision(decision, reason, detail)

    print("=" * 70)
    print("  ✅ Demo complete!")
    print()
    print("  To run with live governance (requires Redis + PostgreSQL):")
    print("    docker compose up -d redis postgres")
    print("    PYTHONPATH=src python scripts/seed_policies.py")
    print("    PYTHONPATH=src python -m vyapaar_mcp.server")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
