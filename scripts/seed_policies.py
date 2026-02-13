#!/usr/bin/env python3
"""Seed sample agent policies into PostgreSQL.

Usage:
    PYTHONPATH=src python scripts/seed_policies.py

Creates sample policies for demo agents per SPEC §9.1.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vyapaar_mcp.config import load_config
from vyapaar_mcp.db.postgres import PostgresClient
from vyapaar_mcp.models import AgentPolicy

SAMPLE_POLICIES = [
    AgentPolicy(
        agent_id="openclaw-agent-001",
        daily_limit=500000,        # ₹5,000
        per_txn_limit=100000,      # ₹1,000
        require_approval_above=50000,  # ₹500
        blocked_domains=["evil.com", "malware.org", "phishing.net"],
    ),
    AgentPolicy(
        agent_id="openclaw-agent-002",
        daily_limit=1000000,       # ₹10,000
        per_txn_limit=250000,      # ₹2,500
        require_approval_above=200000,  # ₹2,000
        allowed_domains=["trusted-vendor.com", "example-vendor.com"],
    ),
    AgentPolicy(
        agent_id="cursor-finance-bot",
        daily_limit=200000,        # ₹2,000
        per_txn_limit=50000,       # ₹500
        # No approval threshold — fully autonomous
    ),
    AgentPolicy(
        agent_id="demo-agent-restricted",
        daily_limit=10000,         # ₹100
        per_txn_limit=5000,        # ₹50
        require_approval_above=2500,  # ₹25
        blocked_domains=["*"],     # Block everything (demo)
    ),
]


async def seed() -> None:
    """Connect to PostgreSQL and seed policies."""
    config = load_config()
    pg = PostgresClient(dsn=config.postgres_dsn)

    try:
        await pg.connect()
        print("✅ Connected to PostgreSQL")
        print()

        for policy in SAMPLE_POLICIES:
            await pg.upsert_agent_policy(policy)
            print(
                f"  📋 {policy.agent_id:30s}  "
                f"daily=₹{policy.daily_limit / 100:,.0f}  "
                f"per-txn=₹{(policy.per_txn_limit or 0) / 100:,.0f}  "
                f"approval>₹{(policy.require_approval_above or 0) / 100:,.0f}"
            )

        print()
        print(f"✅ Seeded {len(SAMPLE_POLICIES)} agent policies")

    finally:
        await pg.disconnect()


if __name__ == "__main__":
    print("=" * 60)
    print("  Vyapaar MCP — Seed Agent Policies")
    print("=" * 60)
    print()
    asyncio.run(seed())
