-- Vyapaar MCP: Initial Schema Migration
-- Version: 001
-- Date: 2026-02-10

-- Agent spending policies
CREATE TABLE IF NOT EXISTS agent_policies (
    agent_id        VARCHAR(128) PRIMARY KEY,
    daily_limit     BIGINT       NOT NULL DEFAULT 500000,   -- in paise (₹5,000)
    per_txn_limit   BIGINT       DEFAULT NULL,              -- per-transaction cap
    require_approval_above BIGINT DEFAULT NULL,             -- human approval threshold
    allowed_domains TEXT[]       DEFAULT '{}',              -- whitelist
    blocked_domains TEXT[]       DEFAULT '{}',              -- blacklist
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Audit trail for all governance decisions
CREATE TABLE IF NOT EXISTS audit_logs (
    id              BIGSERIAL    PRIMARY KEY,
    payout_id       VARCHAR(64)  NOT NULL UNIQUE,
    agent_id        VARCHAR(128) NOT NULL,
    amount          BIGINT       NOT NULL,                  -- in paise
    currency        VARCHAR(3)   NOT NULL DEFAULT 'INR',
    vendor_name     TEXT,
    vendor_url      TEXT,
    decision        VARCHAR(20)  NOT NULL,                  -- APPROVED / REJECTED / HELD
    reason_code     VARCHAR(64)  NOT NULL,                  -- POLICY_OK / RISK_HIGH / etc.
    reason_detail   TEXT,
    threat_types    TEXT[]        DEFAULT '{}',
    processing_ms   INTEGER,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_agent ON audit_logs(agent_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);

-- Seed a default agent policy for demo
INSERT INTO agent_policies (agent_id, daily_limit, per_txn_limit, require_approval_above)
VALUES ('openclaw-agent-001', 500000, 100000, 50000)
ON CONFLICT (agent_id) DO NOTHING;
