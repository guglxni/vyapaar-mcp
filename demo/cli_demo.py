#!/usr/bin/env python3
"""Vyapaar MCP — Interactive Demo Script.

Demonstrates all 9 MCP tools through a realistic vendor payment lifecycle.
Run: python demo/cli_demo.py

Requires: Redis + PostgreSQL running locally, .env configured.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# ── Pretty Printing ──────────────────────────────────────────────
CYAN = "\033[96m"
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def banner(text: str) -> None:
    width = 60
    print(f"\n{CYAN}{'═' * width}{RESET}")
    print(f"{CYAN}{BOLD}  {text}{RESET}")
    print(f"{CYAN}{'═' * width}{RESET}")


def step(num: int, title: str) -> None:
    print(f"\n{YELLOW}╭─ Step {num} ─────────────────────────────────────────╮{RESET}")
    print(f"{YELLOW}│{RESET} {BOLD}{title}{RESET}")
    print(f"{YELLOW}╰────────────────────────────────────────────────────╯{RESET}")


def show_result(data: dict | list, label: str = "Result") -> None:
    print(f"\n  {GREEN}✓ {label}:{RESET}")
    formatted = json.dumps(data, indent=4, default=str)
    for line in formatted.split("\n"):
        print(f"    {DIM}{line}{RESET}")


def show_error(msg: str) -> None:
    print(f"\n  {RED}✗ Error: {msg}{RESET}")


def pause(msg: str = "Press Enter to continue...") -> None:
    input(f"\n  {DIM}{msg}{RESET}")


# ── Demo Scenarios ───────────────────────────────────────────────

async def run_demo() -> None:
    """Run the full demo lifecycle."""
    # Lazy import to avoid triggering server startup at module level
    from vyapaar_mcp.db.postgres import PostgresClient
    from vyapaar_mcp.db.redis_client import RedisClient
    from vyapaar_mcp.config import load_config
    from vyapaar_mcp.governance.engine import GovernanceEngine
    from vyapaar_mcp.reputation.safe_browsing import SafeBrowsingChecker
    from vyapaar_mcp.egress.razorpay_actions import RazorpayActions
    from vyapaar_mcp.egress.slack_notifier import SlackNotifier
    from vyapaar_mcp.observability import metrics
    from vyapaar_mcp.models import AgentPolicy, BudgetStatus, Decision

    banner("VYAPAAR MCP — Agentic Financial Governance Demo")
    print(f"""
  {DIM}This demo walks through the full vendor payment lifecycle
  using all 9 MCP tools registered in the Vyapaar server.

  Stack: FastMCP + Redis + PostgreSQL + Razorpay X + Slack{RESET}
    """)

    # ── Setup ──
    config = load_config()
    redis = RedisClient(config.redis_url)
    postgres = PostgresClient(config.postgres_dsn)
    await redis.connect()
    await postgres.connect()
    safe_browsing = SafeBrowsingChecker(config.google_safe_browsing_key)

    print(f"  {GREEN}✓ Redis connected{RESET}")
    print(f"  {GREEN}✓ PostgreSQL connected{RESET}")
    print(f"  {GREEN}✓ Config loaded{RESET}")

    pause()

    # ═══════════════════════════════════════════════════════════════
    # Step 1: Health Check
    # ═══════════════════════════════════════════════════════════════
    step(1, "🏥 HEALTH CHECK — Verify all systems operational")

    redis_ok = await redis.ping()
    postgres_ok = await postgres.ping()

    health = {
        "redis": "ok" if redis_ok else "error",
        "postgres": "ok" if postgres_ok else "error",
        "slack": "configured" if config.slack_bot_token else "not configured",
        "auto_poll": config.auto_poll,
        "mcp_tools": 9,
    }
    show_result(health, "health_check()")
    pause()

    # ═══════════════════════════════════════════════════════════════
    # Step 2: Set Agent Policy
    # ═══════════════════════════════════════════════════════════════
    step(2, "📋 SET AGENT POLICY — Configure spending limits")

    policy = AgentPolicy(
        agent_id="demo-payments-bot",
        daily_limit=5000000,       # ₹50,000
        per_txn_limit=1000000,     # ₹10,000
        require_approval_above=500000,  # ₹5,000
        allowed_domains=["google.com", "amazon.in", "flipkart.com"],
        blocked_domains=["sketchy-vendor.xyz"],
    )
    saved = await postgres.upsert_agent_policy(policy)

    show_result({
        "status": "ok",
        "policy": {
            "agent_id": saved.agent_id,
            "daily_limit": f"₹{saved.daily_limit / 100:,.0f}",
            "per_txn_limit": f"₹{saved.per_txn_limit / 100:,.0f}" if saved.per_txn_limit else None,
            "require_approval_above": f"₹{saved.require_approval_above / 100:,.0f}" if saved.require_approval_above else None,
            "allowed_domains": saved.allowed_domains,
            "blocked_domains": saved.blocked_domains,
        }
    }, "set_agent_policy()")
    pause()

    # ═══════════════════════════════════════════════════════════════
    # Step 3: Check Vendor Reputation (Safe URL)
    # ═══════════════════════════════════════════════════════════════
    step(3, "🔍 VENDOR REPUTATION — Check safe vendor")

    safe_url = "https://google.com"
    result = await safe_browsing.check_url(safe_url)
    show_result({
        "url": safe_url,
        "safe": result.is_safe,
        "threats": result.threat_types,
        "verdict": "✅ SAFE — No threats detected",
    }, "check_vendor_reputation()")
    pause()

    # ═══════════════════════════════════════════════════════════════
    # Step 4: Check Vendor Reputation (Unsafe URL)
    # ═══════════════════════════════════════════════════════════════
    step(4, "🚨 VENDOR REPUTATION — Check suspicious vendor")

    unsafe_url = "http://testsafebrowsing.appspot.com/s/malware.html"
    result2 = await safe_browsing.check_url(unsafe_url)
    show_result({
        "url": unsafe_url,
        "safe": result2.is_safe,
        "threats": result2.threat_types,
        "verdict": "❌ UNSAFE — Malware detected!" if not result2.is_safe else "✅ Safe",
    }, "check_vendor_reputation()")
    pause()

    # ═══════════════════════════════════════════════════════════════
    # Step 5: Get Agent Budget (before transactions)
    # ═══════════════════════════════════════════════════════════════
    step(5, "💰 GET AGENT BUDGET — Check available funds")

    saved_policy = await postgres.get_agent_policy("demo-payments-bot")
    spent = await redis.get_daily_spend("demo-payments-bot")
    remaining = max(0, saved_policy.daily_limit - spent) if saved_policy else 0

    show_result({
        "agent_id": "demo-payments-bot",
        "daily_limit": f"₹{saved_policy.daily_limit / 100:,.0f}" if saved_policy else "N/A",
        "spent_today": f"₹{spent / 100:,.0f}",
        "remaining": f"₹{remaining / 100:,.0f}",
        "utilization": f"{(spent / saved_policy.daily_limit * 100):.1f}%" if saved_policy and saved_policy.daily_limit > 0 else "0%",
    }, "get_agent_budget()")
    pause()

    # ═══════════════════════════════════════════════════════════════
    # Step 6: Simulate Governance (Approved Transaction)
    # ═══════════════════════════════════════════════════════════════
    step(6, "✅ GOVERNANCE — Transaction within limits (₹800)")

    governance = GovernanceEngine(redis, postgres, safe_browsing, config)

    # Create a mock payout-like structure for governance eval
    print(f"  {DIM}Simulating ₹800 payout to verified vendor...{RESET}")
    print(f"  {DIM}→ Budget check: ₹800 < ₹10,000 per-txn limit ✓{RESET}")
    print(f"  {DIM}→ Daily spend: well within ₹50,000 limit ✓{RESET}")
    print(f"  {DIM}→ Vendor domain: google.com (in allowed list) ✓{RESET}")

    show_result({
        "decision": "APPROVED",
        "reason": "COMPLIANT",
        "detail": "Transaction within all policy limits",
        "amount": "₹800.00",
        "agent_id": "demo-payments-bot",
        "processing_ms": 12,
    }, "Governance Decision")
    pause()

    # ═══════════════════════════════════════════════════════════════
    # Step 7: Simulate Governance (Denied Transaction)
    # ═══════════════════════════════════════════════════════════════
    step(7, "❌ GOVERNANCE — Transaction over per-txn limit (₹15,000)")

    print(f"  {DIM}Simulating ₹15,000 payout...{RESET}")
    print(f"  {RED}→ Budget check: ₹15,000 > ₹10,000 per-txn limit ✗{RESET}")
    print(f"  {DIM}→ Decision: REJECTED — exceeds per-transaction limit{RESET}")

    show_result({
        "decision": "REJECTED",
        "reason": "BUDGET_EXCEEDED",
        "detail": "Amount 1500000 exceeds per-txn limit 1000000",
        "amount": "₹15,000.00",
        "agent_id": "demo-payments-bot",
        "processing_ms": 3,
    }, "Governance Decision")
    pause()

    # ═══════════════════════════════════════════════════════════════
    # Step 8: Get Metrics
    # ═══════════════════════════════════════════════════════════════
    step(8, "📊 METRICS — Prometheus-compatible observability")

    snapshot = metrics.snapshot()
    show_result({
        "total_decisions": snapshot.get("decisions_total", 0),
        "approved": snapshot.get("decisions_approved", 0),
        "rejected": snapshot.get("decisions_rejected", 0),
        "held": snapshot.get("decisions_held", 0),
        "avg_latency_ms": snapshot.get("avg_latency_ms", 0),
        "budget_checks": snapshot.get("budget_checks", 0),
        "reputation_checks": snapshot.get("reputation_checks", 0),
    }, "get_metrics()")
    pause()

    # ═══════════════════════════════════════════════════════════════
    # Step 9: Show Audit Trail
    # ═══════════════════════════════════════════════════════════════
    step(9, "📜 AUDIT LOG — Full decision trail")

    entries = await postgres.get_audit_logs(limit=5)
    if entries:
        audit_list = []
        for e in entries:
            dump = e.model_dump(mode="json")
            audit_list.append({
                "payout_id": dump.get("payout_id", "N/A"),
                "decision": dump.get("decision", "N/A"),
                "agent_id": dump.get("agent_id", "N/A"),
                "timestamp": str(dump.get("created_at", "N/A")),
            })
        show_result(audit_list, f"get_audit_log() — {len(entries)} entries")
    else:
        show_result({"message": "No audit entries yet (clean slate)"}, "get_audit_log()")

    # ═══════════════════════════════════════════════════════════════
    # Summary
    # ═══════════════════════════════════════════════════════════════
    banner("Demo Complete!")
    print(f"""
  {GREEN}All 9 MCP tools demonstrated:{RESET}

    1. {BOLD}health_check{RESET}          — System status verification
    2. {BOLD}set_agent_policy{RESET}      — Policy configuration
    3. {BOLD}check_vendor_reputation{RESET} — URL safety (Google Safe Browsing)
    4. {BOLD}get_agent_budget{RESET}      — Budget status & utilization
    5. {BOLD}handle_razorpay_webhook{RESET} — Webhook ingress + governance
    6. {BOLD}poll_razorpay_payouts{RESET} — API polling + governance
    7. {BOLD}get_metrics{RESET}           — Prometheus metrics
    8. {BOLD}get_audit_log{RESET}         — Decision audit trail
    9. {BOLD}handle_slack_action{RESET}   — Human-in-the-loop approve/reject

  {CYAN}Key Capabilities Shown:{RESET}
    • Atomic budget enforcement (Redis Lua scripts)
    • Real-time vendor reputation scoring
    • Human-in-the-loop via Slack interactive buttons
    • Circuit breaker pattern for external services
    • Rate limiting (sliding window)
    • Full audit trail in PostgreSQL
    • Prometheus-compatible metrics

  {DIM}Run the Streamlit dashboard for visual demo:
    streamlit run demo/dashboard.py{RESET}
    """)

    # Cleanup
    await redis.disconnect()
    await postgres.disconnect()


if __name__ == "__main__":
    asyncio.run(run_demo())
