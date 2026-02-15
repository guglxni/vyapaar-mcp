"""Audit logger — writes every governance decision to PostgreSQL.

If PostgreSQL is unreachable, falls back to local filesystem
(fail-safe per SPEC §14.1).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from vyapaar_mcp.db.postgres import PostgresClient
from vyapaar_mcp.models import GovernanceResult

logger = logging.getLogger(__name__)

# Make fallback path configurable via environment variable
FALLBACK_DIR = Path(os.environ.get("VYAPAAR_AUDIT_FALLBACK_DIR", "./audit_logs"))


async def log_decision(
    postgres: PostgresClient,
    result: GovernanceResult,
    vendor_name: str | None = None,
    vendor_url: str | None = None,
) -> None:
    """Log a governance decision to PostgreSQL with filesystem fallback.

    Args:
        postgres: PostgreSQL client instance.
        result: The governance decision result.
        vendor_name: Optional vendor name for audit trail.
        vendor_url: Optional vendor URL for audit trail.
    """
    try:
        await postgres.write_audit_log(
            result,
            vendor_name=vendor_name,
            vendor_url=vendor_url,
        )
    except Exception as e:
        logger.error("PostgreSQL audit write failed: %s — falling back to filesystem", e)
        _write_fallback(result, vendor_name, vendor_url)


def _write_fallback(
    result: GovernanceResult,
    vendor_name: str | None = None,
    vendor_url: str | None = None,
) -> None:
    """Emergency fallback: write audit to local JSON file."""
    FALLBACK_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S")
    filename = FALLBACK_DIR / f"{result.payout_id}_{timestamp}.json"

    entry = {
        "payout_id": result.payout_id,
        "agent_id": result.agent_id,
        "amount": result.amount,
        "decision": result.decision.value,
        "reason_code": result.reason_code.value,
        "reason_detail": result.reason_detail,
        "threat_types": result.threat_types,
        "processing_ms": result.processing_ms,
        "vendor_name": vendor_name,
        "vendor_url": vendor_url,
        "timestamp": timestamp,
    }

    filename.write_text(json.dumps(entry, indent=2))
    logger.warning("Audit fallback written to: %s", filename)
