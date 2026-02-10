"""PostgreSQL client for audit logs and agent policies.

Uses asyncpg for async, parameterized queries (SQL injection safe).
"""

from __future__ import annotations

import logging
from datetime import datetime

import asyncpg

from vyapaar_mcp.models import AgentPolicy, AuditLogEntry, Decision, GovernanceResult, ReasonCode

logger = logging.getLogger(__name__)


class PostgresClient:
    """Async PostgreSQL client for Vyapaar data layer."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None  # type: ignore[type-arg]

    async def connect(self) -> None:
        """Create connection pool."""
        self._pool = await asyncpg.create_pool(
            self._dsn,
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
        logger.info("PostgreSQL pool created: %s", self._dsn.split("@")[-1])

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("PostgreSQL pool closed")

    @property
    def pool(self) -> asyncpg.Pool:  # type: ignore[type-arg]
        """Get the connection pool."""
        if self._pool is None:
            raise RuntimeError("PostgreSQL not connected. Call connect() first.")
        return self._pool

    async def ping(self) -> bool:
        """Check if PostgreSQL is reachable."""
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception:
            return False

    # ================================================================
    # Schema Migration
    # ================================================================

    async def run_migrations(self) -> None:
        """Run database migrations to create tables."""
        async with self.pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS agent_policies (
                    agent_id        VARCHAR(128) PRIMARY KEY,
                    daily_limit     BIGINT       NOT NULL DEFAULT 500000,
                    per_txn_limit   BIGINT       DEFAULT NULL,
                    require_approval_above BIGINT DEFAULT NULL,
                    allowed_domains TEXT[]       DEFAULT '{}',
                    blocked_domains TEXT[]       DEFAULT '{}',
                    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
                    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
                );
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id              BIGSERIAL    PRIMARY KEY,
                    payout_id       VARCHAR(64)  NOT NULL UNIQUE,
                    agent_id        VARCHAR(128) NOT NULL,
                    amount          BIGINT       NOT NULL,
                    currency        VARCHAR(3)   NOT NULL DEFAULT 'INR',
                    vendor_name     TEXT,
                    vendor_url      TEXT,
                    decision        VARCHAR(20)  NOT NULL,
                    reason_code     VARCHAR(64)  NOT NULL,
                    reason_detail   TEXT,
                    threat_types    TEXT[]        DEFAULT '{}',
                    processing_ms   INTEGER,
                    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
                );
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_agent
                ON audit_logs(agent_id);
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_created
                ON audit_logs(created_at);
            """)
            logger.info("Database migrations completed")

    # ================================================================
    # Agent Policies
    # ================================================================

    async def get_agent_policy(self, agent_id: str) -> AgentPolicy | None:
        """Fetch spending policy for an agent."""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM agent_policies WHERE agent_id = $1",
                agent_id,
            )
            if row is None:
                return None
            return AgentPolicy(
                agent_id=row["agent_id"],
                daily_limit=row["daily_limit"],
                per_txn_limit=row["per_txn_limit"],
                require_approval_above=row["require_approval_above"],
                allowed_domains=list(row["allowed_domains"] or []),
                blocked_domains=list(row["blocked_domains"] or []),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    async def upsert_agent_policy(self, policy: AgentPolicy) -> AgentPolicy:
        """Create or update an agent policy."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_policies
                    (agent_id, daily_limit, per_txn_limit, require_approval_above,
                     allowed_domains, blocked_domains, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, NOW())
                ON CONFLICT (agent_id) DO UPDATE SET
                    daily_limit = EXCLUDED.daily_limit,
                    per_txn_limit = EXCLUDED.per_txn_limit,
                    require_approval_above = EXCLUDED.require_approval_above,
                    allowed_domains = EXCLUDED.allowed_domains,
                    blocked_domains = EXCLUDED.blocked_domains,
                    updated_at = NOW()
                """,
                policy.agent_id,
                policy.daily_limit,
                policy.per_txn_limit,
                policy.require_approval_above,
                policy.allowed_domains,
                policy.blocked_domains,
            )
        logger.info("Policy upserted for agent: %s", policy.agent_id)
        return policy

    # ================================================================
    # Audit Logs
    # ================================================================

    async def write_audit_log(self, result: GovernanceResult, **kwargs: str | None) -> None:
        """Write a governance decision to the audit log."""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO audit_logs
                    (payout_id, agent_id, amount, vendor_name, vendor_url,
                     decision, reason_code, reason_detail, threat_types, processing_ms)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (payout_id) DO NOTHING
                """,
                result.payout_id,
                result.agent_id,
                result.amount,
                kwargs.get("vendor_name"),
                kwargs.get("vendor_url"),
                result.decision.value,
                result.reason_code.value,
                result.reason_detail,
                result.threat_types,
                result.processing_ms,
            )
        logger.info(
            "Audit logged: payout=%s decision=%s reason=%s",
            result.payout_id, result.decision.value, result.reason_code.value,
        )

    async def get_audit_logs(
        self,
        agent_id: str | None = None,
        payout_id: str | None = None,
        limit: int = 50,
    ) -> list[AuditLogEntry]:
        """Retrieve audit log entries with optional filters."""
        conditions: list[str] = []
        params: list[str | int] = []
        param_idx = 1

        if agent_id:
            conditions.append(f"agent_id = ${param_idx}")
            params.append(agent_id)
            param_idx += 1

        if payout_id:
            conditions.append(f"payout_id = ${param_idx}")
            params.append(payout_id)
            param_idx += 1

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        params.append(limit)
        query = f"""
            SELECT * FROM audit_logs
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ${param_idx}
        """

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(query, *params)

        return [
            AuditLogEntry(
                payout_id=row["payout_id"],
                agent_id=row["agent_id"],
                amount=row["amount"],
                currency=row["currency"],
                vendor_name=row["vendor_name"],
                vendor_url=row["vendor_url"],
                decision=Decision(row["decision"]),
                reason_code=ReasonCode(row["reason_code"]),
                reason_detail=row["reason_detail"] or "",
                threat_types=list(row["threat_types"] or []),
                processing_ms=row["processing_ms"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
