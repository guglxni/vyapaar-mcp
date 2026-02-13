#!/usr/bin/env python3
"""CLI Audit Dashboard — Real-time audit log viewer.

Usage:
    PYTHONPATH=src python scripts/audit_dashboard.py [--tail] [--agent AGENT_ID] [--limit N]

Displays a formatted table of governance decisions from the audit log.
Optionally runs in "tail" mode to poll for new entries continuously.

Per SPEC §19 Nice-to-Have: "CLI dashboard for real-time audit log viewer."
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, UTC
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vyapaar_mcp.config import load_config
from vyapaar_mcp.db.postgres import PostgresClient
from vyapaar_mcp.models import AuditLogEntry, Decision

# ================================================================
# ANSI Colors
# ================================================================

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
WHITE = "\033[97m"
BG_RED = "\033[41m"
BG_GREEN = "\033[42m"
BG_YELLOW = "\033[43m"


def decision_color(decision: Decision) -> str:
    """Get ANSI color for a decision."""
    return {
        Decision.APPROVED: GREEN,
        Decision.REJECTED: RED,
        Decision.HELD: YELLOW,
    }.get(decision, WHITE)


def decision_icon(decision: Decision) -> str:
    """Get icon for a decision."""
    return {
        Decision.APPROVED: "✅",
        Decision.REJECTED: "❌",
        Decision.HELD: "⏸ ",
    }.get(decision, "❓")


# ================================================================
# Display Functions
# ================================================================


def print_header() -> None:
    """Print dashboard header."""
    print()
    print(f"{BOLD}{CYAN}{'═' * 90}{RESET}")
    print(f"{BOLD}{CYAN}  ⚖️  VYAPAAR MCP — Audit Dashboard{RESET}")
    print(f"{BOLD}{CYAN}  The CFO for the Agentic Economy{RESET}")
    print(f"{BOLD}{CYAN}{'═' * 90}{RESET}")
    print()


def print_table_header() -> None:
    """Print table column headers."""
    print(
        f"  {BOLD}{DIM}"
        f"{'TIME':<20} "
        f"{'PAYOUT ID':<24} "
        f"{'DECISION':<12} "
        f"{'AMOUNT':>12} "
        f"{'AGENT':<20} "
        f"{'REASON':<20}"
        f"{RESET}"
    )
    print(f"  {DIM}{'─' * 88}{RESET}")


def print_entry(entry: AuditLogEntry) -> None:
    """Print a single audit log entry."""
    color = decision_color(entry.decision)
    icon = decision_icon(entry.decision)

    timestamp = ""
    if entry.created_at:
        timestamp = entry.created_at.strftime("%Y-%m-%d %H:%M:%S")
    else:
        timestamp = "N/A"

    amount_rupees = f"₹{entry.amount / 100:,.2f}"

    # Truncate long fields
    agent = entry.agent_id[:18] if len(entry.agent_id) > 18 else entry.agent_id
    reason = entry.reason_code.value[:18] if len(entry.reason_code.value) > 18 else entry.reason_code.value

    print(
        f"  {DIM}{timestamp:<20}{RESET} "
        f"{entry.payout_id:<24} "
        f"{color}{icon} {entry.decision.value:<9}{RESET} "
        f"{BOLD}{amount_rupees:>12}{RESET} "
        f"{CYAN}{agent:<20}{RESET} "
        f"{reason:<20}"
    )


def print_summary(entries: list[AuditLogEntry]) -> None:
    """Print summary statistics."""
    if not entries:
        print(f"\n  {DIM}No audit entries found.{RESET}\n")
        return

    approved = sum(1 for e in entries if e.decision == Decision.APPROVED)
    rejected = sum(1 for e in entries if e.decision == Decision.REJECTED)
    held = sum(1 for e in entries if e.decision == Decision.HELD)
    total_amount = sum(e.amount for e in entries)
    approved_amount = sum(e.amount for e in entries if e.decision == Decision.APPROVED)

    print()
    print(f"  {DIM}{'─' * 88}{RESET}")
    print(
        f"  {BOLD}Summary:{RESET}  "
        f"{GREEN}✅ {approved} approved{RESET}  "
        f"{RED}❌ {rejected} rejected{RESET}  "
        f"{YELLOW}⏸  {held} held{RESET}  |  "
        f"Total: {BOLD}₹{total_amount / 100:,.2f}{RESET}  "
        f"Approved: {GREEN}₹{approved_amount / 100:,.2f}{RESET}"
    )
    print()


def print_detail(entry: AuditLogEntry) -> None:
    """Print detailed view of an audit entry."""
    color = decision_color(entry.decision)
    icon = decision_icon(entry.decision)

    print(f"\n  {BOLD}┌─ {entry.payout_id}{RESET}")
    print(f"  │  {BOLD}Decision:{RESET}   {color}{icon} {entry.decision.value}{RESET}")
    print(f"  │  {BOLD}Amount:{RESET}     ₹{entry.amount / 100:,.2f} ({entry.amount} paise)")
    print(f"  │  {BOLD}Agent:{RESET}      {CYAN}{entry.agent_id}{RESET}")
    print(f"  │  {BOLD}Reason:{RESET}     {entry.reason_code.value}")
    print(f"  │  {BOLD}Detail:{RESET}     {entry.reason_detail}")
    if entry.vendor_name:
        print(f"  │  {BOLD}Vendor:{RESET}     {entry.vendor_name}")
    if entry.vendor_url:
        print(f"  │  {BOLD}URL:{RESET}        {entry.vendor_url}")
    if entry.threat_types:
        print(f"  │  {BOLD}Threats:{RESET}    {RED}{', '.join(entry.threat_types)}{RESET}")
    if entry.processing_ms is not None:
        print(f"  │  {BOLD}Latency:{RESET}    {entry.processing_ms}ms")
    if entry.created_at:
        print(f"  │  {BOLD}Time:{RESET}       {entry.created_at.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    print(f"  └{'─' * 50}")


# ================================================================
# Main
# ================================================================


async def fetch_and_display(
    pg: PostgresClient,
    agent_id: str | None,
    payout_id: str | None,
    limit: int,
    detail: bool,
) -> list[AuditLogEntry]:
    """Fetch audit logs and display them."""
    entries = await pg.get_audit_logs(
        agent_id=agent_id,
        payout_id=payout_id,
        limit=limit,
    )

    if detail:
        for entry in entries:
            print_detail(entry)
    else:
        print_table_header()
        for entry in entries:
            print_entry(entry)
        print_summary(entries)

    return entries


async def tail_mode(
    pg: PostgresClient,
    agent_id: str | None,
    interval: int,
) -> None:
    """Continuously poll for new audit entries."""
    seen_ids: set[str] = set()

    print(f"  {BOLD}🔄 Tail mode — polling every {interval}s (Ctrl+C to stop){RESET}")
    print()
    print_table_header()

    while True:
        entries = await pg.get_audit_logs(
            agent_id=agent_id,
            limit=20,
        )

        for entry in reversed(entries):  # Show oldest first
            if entry.payout_id not in seen_ids:
                seen_ids.add(entry.payout_id)
                print_entry(entry)

        await asyncio.sleep(interval)


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Vyapaar MCP — Audit Dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Show latest 20 entries\n"
            "  PYTHONPATH=src python scripts/audit_dashboard.py\n"
            "\n"
            "  # Filter by agent\n"
            "  PYTHONPATH=src python scripts/audit_dashboard.py --agent openclaw-agent-001\n"
            "\n"
            "  # Detailed view of specific payout\n"
            "  PYTHONPATH=src python scripts/audit_dashboard.py --payout pout_123 --detail\n"
            "\n"
            "  # Live tail mode\n"
            "  PYTHONPATH=src python scripts/audit_dashboard.py --tail\n"
        ),
    )
    parser.add_argument("--agent", help="Filter by agent ID")
    parser.add_argument("--payout", help="Filter by payout ID")
    parser.add_argument("--limit", type=int, default=20, help="Max entries to show (default: 20)")
    parser.add_argument("--detail", action="store_true", help="Show detailed view")
    parser.add_argument("--tail", action="store_true", help="Live tail mode (polls continuously)")
    parser.add_argument("--interval", type=int, default=5, help="Tail poll interval in seconds (default: 5)")
    args = parser.parse_args()

    config = load_config()
    pg = PostgresClient(dsn=config.postgres_dsn)

    try:
        await pg.connect()
        print_header()

        if args.tail:
            await tail_mode(pg, args.agent, args.interval)
        else:
            await fetch_and_display(
                pg,
                agent_id=args.agent,
                payout_id=args.payout,
                limit=args.limit,
                detail=args.detail,
            )

    except KeyboardInterrupt:
        print(f"\n\n  {DIM}Dashboard stopped.{RESET}\n")
    finally:
        await pg.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
