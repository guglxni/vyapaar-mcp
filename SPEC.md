# Vyapaar MCP — Agentic Financial Governance Server

> **Version:** 3.0.0  
> **Codename:** "The CFO for the Agentic Economy"  
> **Stack:** Python 3.12, UV, FastMCP, Razorpay X (Sandbox), Redis, Google Safe Browsing v4  
> **Architecture:** Async Event-Driven (Webhook + SSE Transport)  
> **Hackathon:** [2 Fast 2 MCP](https://www.wemakedevs.org/hackathons/2fast2mcp) — Archestra Track  
> **Platform:** [Archestra](https://archestra.ai) — Enterprise MCP Orchestrator  

---

## 1. Executive Summary

**Vyapaar MCP** is a *Governance-as-a-Service* MCP Server that acts as an autonomous financial firewall between AI Agents and the **Razorpay X** payments platform. It intercepts, validates, and audits every payout an agent attempts to make — enforcing budgets, checking vendor reputation, and keeping humans in the loop for high-value decisions.

### Why This Matters

We're entering the era of autonomous AI agents executing real-world financial tasks. The gap isn't intelligence — it's **trust**. Giving an AI agent a credit card is like giving a new hire the company chequebook on Day 1 with no spending policy.

| Without Vyapaar | With Vyapaar |
|:---|:---|
| Agent hallucinates → drains corporate wallet | Atomic budget limits block overspend |
| Agent pays fraudulent vendor | Google Safe Browsing flags malware domains |
| No audit trail for AI spending | Every rupee logged with decision rationale |
| All-or-nothing access | Granular per-agent policy engine |

### Hackathon Judging Alignment

| Judging Criterion | How Vyapaar Addresses It |
|:---|:---|
| **Potential Impact** | Solves a critical trust gap — financial governance for the $B AI agent economy |
| **Creativity & Originality** | Novel "CFO-as-MCP" pattern; agents governed by policy, not just prompts |
| **Technical Implementation** | Atomic Redis locking, webhook signature verification, async approval workflows |
| **Aesthetics & UX** | CLI dashboard for real-time audit logs; Slack-native human-in-the-loop UX |
| **Best Use of Archestra** | Deployed as a governed MCP server with secrets management, observability, and auto-scaling |
| **Learning & Growth** | First-of-its-kind fintech governance layer built on the MCP protocol |

---

## 2. Problem Statement — "The Rogue Agent Risk"

### The Threat Model

```
┌──────────────────────────────────────────────────────────────┐
│                    WITHOUT VYAPAAR                           │
│                                                              │
│  AI Agent ──── "Pay vendor X ₹50,000" ──── Razorpay X ────► │
│     │                                         │              │
│     │  (No validation, no limits,              │              │
│     │   no reputation check)                   │              │
│     │                                          ▼              │
│     └──── Hallucination? ──── Money Gone. ──── 💸            │
└──────────────────────────────────────────────────────────────┘
```

### Failure Scenarios We Prevent

1. **Budget Drain:** Agent enters a loop, making repeated payouts until the account is empty.
2. **Fraudulent Vendor:** Agent pays a domain flagged for malware/phishing (social engineering).
3. **Prompt Injection:** Malicious prompt tricks agent into paying an attacker's account.
4. **Shadow Spending:** Multiple agents spend from the same budget without coordination (race condition).
5. **Missing Audit Trail:** Compliance can't trace *why* an AI spent money.

---

## 3. Solution Architecture

### 3.1 The Four Pillars

```
┌─────────────────────────────────────────────────────────────────┐
│                        VYAPAAR MCP                              │
│                                                                 │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────┐  ┌─────────┐  │
│  │ INGRESS  │  │  GOVERNANCE  │  │  REPUTATION  │  │ EGRESS  │  │
│  │          │→ │   ENGINE     │→ │    CHECK     │→ │         │  │
│  │ Webhook  │  │ Budget/Policy│  │ Safe Browsing│  │ Approve │  │
│  │ Listener │  │ (Redis)      │  │ (Google API) │  │ /Reject │  │
│  └──────────┘  └──────────────┘  └─────────────┘  └─────────┘  │
│       ▲                                                  │      │
│       │              ┌──────────┐                        │      │
│       │              │  AUDIT   │◄───────────────────────┘      │
│       │              │   LOG    │                               │
│       │              │(Postgres)│                               │
│       │              └──────────┘                               │
│       │                                                         │
└───────┼─────────────────────────────────────────────────────────┘
        │
   Razorpay X
   (Webhook: payout.queued)
```

### 3.2 The Governance Loop (Sequence)

```
 Agent (OpenClaw)          Razorpay X              Vyapaar MCP             Google Safe Browsing
       │                       │                        │                          │
       │  1. Create Payout     │                        │                          │
       │  (status: queued)     │                        │                          │
       │──────────────────────►│                        │                          │
       │                       │  2. Webhook:           │                          │
       │                       │  payout.queued         │                          │
       │                       │───────────────────────►│                          │
       │                       │                        │  3a. Verify Signature    │
       │                       │                        │      (HMAC-SHA256)       │
       │                       │                        │                          │
       │                       │                        │  3b. Check Idempotency   │
       │                       │                        │      (Redis SETNX)       │
       │                       │                        │                          │
       │                       │                        │  3c. Check Budget        │
       │                       │                        │      (Redis INCRBY)      │
       │                       │                        │                          │
       │                       │                        │  3d. Check Reputation    │
       │                       │                        │──────────────────────────►│
       │                       │                        │◄─────────────────────────│
       │                       │                        │                          │
       │                       │                        │  3e. Log Decision        │
       │                       │                        │      (PostgreSQL)        │
       │                       │                        │                          │
       │                       │  4. Approve/Reject     │                          │
       │                       │◄───────────────────────│                          │
       │                       │                        │                          │
       │  5. Payout Processed/ │                        │                          │
       │     Rejected          │                        │                          │
       │◄──────────────────────│                        │                          │
```

### 3.3 Component Roles

| Component | Role | Technology |
|:---|:---|:---|
| **The Brain** | AI Agent initiating payouts | OpenClaw / Custom Agent |
| **The Bank** | Payment execution & webhooks | Razorpay X (Sandbox) |
| **The Guard** | Policy enforcement & governance | **Vyapaar MCP** (this project) |
| **The Platform** | MCP orchestration, secrets, observability | Archestra |
| **The Memory** | Atomic budget counters, idempotency keys | Redis |
| **The Ledger** | Audit logs, agent policies | PostgreSQL |
| **The Lookout** | Vendor URL reputation checking | Google Safe Browsing v4 |
| **The Messenger** | Human-in-the-loop approvals | Slack MCP |

---

## 4. Agentic IDE Context (Meta-Instructions)

> *Instructions for the AI Coding Assistant (Cursor / Antigravity / Copilot)*

**Role:** You are a Senior Fintech Engineer building a financial governance MCP server.  
**Tone:** Defensive, Secure, Type-Safe. Every line of code handles money.

### Critical Constraints (DO NOT VIOLATE)

| # | Constraint | Rationale |
|:---|:---|:---|
| 1 | **Verify `X-Razorpay-Signature`** on ALL incoming webhooks using HMAC-SHA256. Drop invalid requests with `401`. | Prevents webhook spoofing attacks. |
| 2 | **Use Redis Atomic Operations** (`INCRBY`, `SETNX`) for budget tracking. **NEVER** use Read-Modify-Write. | Prevents race conditions when multiple agents spend concurrently. |
| 3 | **Check `webhook_id` idempotency** via Redis `SETNX` before processing. | Razorpay retries failed webhooks; processing twice = double-spending. |
| 4 | **No Mocking in Prod.** Mocks belong strictly in `tests/`. Production code hits real Razorpay Sandbox APIs. | A mock in production = silent payment failures. |
| 5 | **All code passes `mypy --strict`.** Use Pydantic V2 `model_config = ConfigDict(strict=True)`. | Type safety is non-negotiable in fintech. |
| 6 | **Dedicated API keys per service.** `GOOGLE_SAFE_BROWSING_KEY` ≠ Generative AI key. | Principle of Least Privilege. |
| 7 | **All amounts in paise (integer).** ₹500 = `50000` paise. Never use floats for money. | Floating point arithmetic causes rounding errors. |
| 8 | **Log every decision** with reason codes to PostgreSQL `audit_logs`. | Compliance requires full audit trail. |

---

## 5. Tech Stack & Dependencies

### 5.1 Core Dependencies

| Category | Tool | Package / Command | Purpose |
|:---|:---|:---|:---|
| **Runtime** | Python 3.12+ | `uv` | Fast package manager & virtualenv |
| **MCP Framework** | FastMCP | `mcp[cli]` | MCP server with SSE transport |
| **Payments SDK** | Razorpay | `razorpay` | Payout approve/reject API calls |
| **Reputation** | Google Safe Browsing v4 | `httpx` | Async URL threat checking |
| **State & Locking** | Redis | `redis[hiredis]` | Atomic budget counters + idempotency |
| **Database** | PostgreSQL 15+ | `asyncpg` | Audit logs + agent policies |
| **Validation** | Pydantic V2 | `pydantic>=2.0` | Strict type-safe data models |
| **HTTP** | HTTPX | `httpx` | Async HTTP client for external APIs |
| **Config** | Pydantic Settings | `pydantic-settings` | Env-based configuration loading |

### 5.2 Dev / Test Dependencies

| Category | Tool | Package |
|:---|:---|:---|
| **Type Checking** | mypy | `mypy --strict` |
| **Testing** | pytest | `pytest`, `pytest-asyncio` |
| **Mocking** | fakeredis | `fakeredis[lua]` |
| **Linting** | Ruff | `ruff` |
| **Formatting** | Ruff | `ruff format` |

### 5.3 Infrastructure

| Component | How to Run |
|:---|:---|
| **Redis** | `docker run -d --name vyapaar-redis -p 6379:6379 redis:7-alpine` |
| **PostgreSQL** | `docker run -d --name vyapaar-pg -p 5432:5432 -e POSTGRES_DB=vyapaar_db -e POSTGRES_USER=vyapaar -e POSTGRES_PASSWORD=securepass postgres:15-alpine` |
| **MCP Server** | `uv run mcp run src/server.py` |

---

## 6. MCP Server Tool Definitions

> These are the tools Vyapaar exposes via the MCP protocol. Agents and Archestra interact with these.

### 6.1 `handle_razorpay_webhook`
**Type:** Tool (Ingress)  
**Description:** Receives and processes incoming Razorpay X webhook events.  
**Input Schema:**
```json
{
  "payload": "string (raw JSON body)",
  "signature": "string (X-Razorpay-Signature header)"
}
```
**Output:** `{ "decision": "APPROVED|REJECTED|HELD", "reason": "string", "payout_id": "string" }`  
**Side Effects:** Updates Redis budget counter, writes to audit_logs, calls Razorpay approve/reject API.

### 6.2 `check_vendor_reputation`
**Type:** Tool (Reputation)  
**Description:** Checks a URL/domain against Google Safe Browsing v4 threat lists.  
**Input Schema:**
```json
{
  "url": "string (vendor URL or domain to check)"
}
```
**Output:** `{ "safe": true|false, "threats": ["MALWARE", "SOCIAL_ENGINEERING", ...], "cache_duration": "string" }`

### 6.3 `get_agent_budget`
**Type:** Tool (Read)  
**Description:** Returns the current daily spend and remaining budget for a specific agent.  
**Input Schema:**
```json
{
  "agent_id": "string"
}
```
**Output:** `{ "agent_id": "string", "daily_limit": 500000, "spent_today": 125000, "remaining": 375000, "currency": "INR" }`

### 6.4 `get_audit_log`
**Type:** Tool (Read)  
**Description:** Retrieves the spending audit trail for a specific agent or payout.  
**Input Schema:**
```json
{
  "agent_id": "string (optional)",
  "payout_id": "string (optional)",
  "limit": "integer (default: 50)"
}
```
**Output:** `[{ "payout_id": "string", "agent_id": "string", "amount": 50000, "decision": "APPROVED", "reason": "POLICY_OK", "timestamp": "ISO8601" }]`

### 6.5 `set_agent_policy`
**Type:** Tool (Admin)  
**Description:** Creates or updates spending policies for a specific agent.  
**Input Schema:**
```json
{
  "agent_id": "string",
  "daily_limit": "integer (paise)",
  "per_txn_limit": "integer (paise, optional)",
  "require_approval_above": "integer (paise, optional)",
  "allowed_domains": ["string (optional whitelist)"],
  "blocked_domains": ["string (optional blacklist)"]
}
```
**Output:** `{ "status": "ok", "policy": { ... } }`

### 6.6 `health_check`
**Type:** Tool (Ops)  
**Description:** Returns the health status of all dependent services (Redis, PostgreSQL, Razorpay).  
**Output:** `{ "redis": "ok|error", "postgres": "ok|error", "razorpay": "ok|error", "uptime_seconds": 3600 }`

---

## 7. API Contracts (External Services)

### 7.1 Razorpay X — Incoming Webhook: `payout.queued`

> *Source: [Razorpay Webhook Docs](https://razorpay.com/docs/webhooks/setup-edit-payouts/)*

**Delivery:** `POST` to Vyapaar's webhook endpoint.  
**Header:** `X-Razorpay-Signature: <HMAC-SHA256 of body using webhook secret>`

```json
{
  "entity": "event",
  "account_id": "acc_BFQ7uQEaa7j2zS",
  "event": "payout.queued",
  "contains": ["payout"],
  "payload": {
    "payout": {
      "entity": {
        "id": "pout_EhYCPJnMVMpk21",
        "entity": "payout",
        "fund_account_id": "fa_100000000000fa",
        "amount": 500000,
        "currency": "INR",
        "notes": {
          "agent_id": "openclaw-agent-001",
          "purpose": "vendor_payment",
          "vendor_url": "https://example-vendor.com"
        },
        "fees": 590,
        "tax": 90,
        "status": "queued",
        "purpose": "payout",
        "mode": "NEFT",
        "reference_id": "txn_vyapaar_20260210_001",
        "fund_account": {
          "id": "fa_100000000000fa",
          "entity": "fund_account",
          "contact_id": "cont_AhYCJnMVMpk22",
          "account_type": "bank_account",
          "bank_account": {
            "ifsc": "HDFC0000001",
            "bank_name": "HDFC Bank",
            "name": "Vendor Pvt Ltd",
            "account_number": "1234567890123456"
          },
          "contact": {
            "id": "cont_AhYCJnMVMpk22",
            "entity": "contact",
            "name": "Suspicious Vendor Pvt Ltd",
            "type": "vendor",
            "email": "vendor@example.com"
          }
        },
        "created_at": 1707561564
      }
    }
  },
  "created_at": 1707561564
}
```

**Signature Verification (Python):**
```python
import hmac
import hashlib

def verify_razorpay_signature(payload_body: bytes, signature: str, secret: str) -> bool:
    """Verify Razorpay webhook signature using HMAC-SHA256."""
    expected = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

### 7.2 Razorpay X — Outgoing: Approve / Reject Payout

**Approve:**
```http
POST https://api.razorpay.com/v1/payouts/{payout_id}/approve
Authorization: Basic <base64(key_id:key_secret)>
Content-Type: application/json
```

**Cancel (Reject a queued payout):**
```http
PATCH https://api.razorpay.com/v1/payouts/{payout_id}/cancel
Authorization: Basic <base64(key_id:key_secret)>
Content-Type: application/json

{
  "remarks": "REJECTED by Vyapaar MCP: RISK_HIGH — Google Safe Browsing flagged MALWARE"
}
```

### 7.3 Google Safe Browsing v4 — Lookup API

> *Source: [Google Safe Browsing Lookup API](https://developers.google.com/safe-browsing/v4/lookup-api)*

**Request:**
```http
POST https://safebrowsing.googleapis.com/v4/threatMatches:find?key={API_KEY}
Content-Type: application/json
```
```json
{
  "client": {
    "clientId": "vyapaar-mcp",
    "clientVersion": "3.0.0"
  },
  "threatInfo": {
    "threatTypes": [
      "MALWARE",
      "SOCIAL_ENGINEERING",
      "UNWANTED_SOFTWARE",
      "POTENTIALLY_HARMFUL_APPLICATION"
    ],
    "platformTypes": ["ANY_PLATFORM"],
    "threatEntryTypes": ["URL"],
    "threatEntries": [
      { "url": "https://example-vendor.com" }
    ]
  }
}
```

**Response (Match Found — UNSAFE):**
```json
{
  "matches": [
    {
      "threatType": "MALWARE",
      "platformType": "ANY_PLATFORM",
      "threatEntryType": "URL",
      "threat": { "url": "https://example-vendor.com" },
      "cacheDuration": "300.000s"
    }
  ]
}
```

**Response (No Match — SAFE):**
```json
{}
```

> ⚠️ **Important:** An empty response body `{}` means the URL is clean. The presence of a `matches` array means threats were found.

---

## 8. Decision Matrix

| # | Condition | Action | Reason Code | Notification |
|:---|:---|:---|:---|:---|
| 1 | Signature invalid | **DROP** (401) | `INVALID_SIGNATURE` | Alert to ops channel |
| 2 | Webhook already processed | **SKIP** (200) | `IDEMPOTENT_SKIP` | None |
| 3 | Agent has no policy | **REJECT** | `NO_POLICY` | Slack alert |
| 4 | Amount > Daily Limit | **REJECT** | `LIMIT_EXCEEDED` | Slack alert |
| 5 | Amount > Per-Transaction Limit | **REJECT** | `TXN_LIMIT_EXCEEDED` | Slack alert |
| 6 | Google Safe Browsing = Unsafe | **REJECT** | `RISK_HIGH` | Slack alert + log threat type |
| 7 | Domain in `blocked_domains` | **REJECT** | `DOMAIN_BLOCKED` | Slack alert |
| 8 | Amount > Approval Threshold | **HOLD** | `APPROVAL_REQUIRED` | Slack approval request |
| 9 | All checks pass | **APPROVE** | `POLICY_OK` | None (logged silently) |

---

## 9. Database Schema

### 9.1 PostgreSQL Tables

**Table: `agent_policies`**
```sql
CREATE TABLE agent_policies (
    agent_id        VARCHAR(128) PRIMARY KEY,
    daily_limit     BIGINT       NOT NULL DEFAULT 500000,   -- in paise (₹5,000)
    per_txn_limit   BIGINT       DEFAULT NULL,              -- optional per-txn cap
    require_approval_above BIGINT DEFAULT NULL,             -- trigger human approval
    allowed_domains TEXT[]       DEFAULT '{}',              -- whitelist (empty = allow all)
    blocked_domains TEXT[]       DEFAULT '{}',              -- blacklist
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
```

**Table: `audit_logs`**
```sql
CREATE TABLE audit_logs (
    id              BIGSERIAL    PRIMARY KEY,
    payout_id       VARCHAR(64)  NOT NULL UNIQUE,           -- Razorpay pout_xxx
    agent_id        VARCHAR(128) NOT NULL,
    amount          BIGINT       NOT NULL,                  -- in paise
    currency        VARCHAR(3)   NOT NULL DEFAULT 'INR',
    vendor_name     TEXT,
    vendor_url      TEXT,
    decision        VARCHAR(20)  NOT NULL,                  -- APPROVED / REJECTED / HELD
    reason_code     VARCHAR(64)  NOT NULL,                  -- POLICY_OK / RISK_HIGH / etc.
    reason_detail   TEXT,                                   -- human-readable explanation
    threat_types    TEXT[],                                 -- ['MALWARE'] from Safe Browsing
    processing_ms   INTEGER,                               -- latency tracking
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_agent ON audit_logs(agent_id);
CREATE INDEX idx_audit_created ON audit_logs(created_at);
```

### 9.2 Redis Keys

| Key Pattern | Type | TTL | Purpose |
|:---|:---|:---|:---|
| `vyapaar:budget:{agent_id}:{YYYYMMDD}` | Integer | 25h | Daily spend counter (atomic `INCRBY`) |
| `vyapaar:idempotent:{webhook_id}` | String | 48h | Webhook dedup (`SETNX`) |
| `vyapaar:reputation:{url_hash}` | JSON | 5min | Safe Browsing result cache |
| `vyapaar:health:last_check` | String | 60s | Last health check timestamp |

---

## 10. Project Structure

```
vyapaar-mcp/
├── SPEC.md                       # This file — project specification
├── README.md                     # Project overview + setup guide
├── pyproject.toml                # UV/pip project config + dependencies
├── Dockerfile                    # Multi-stage production build
├── docker-compose.yml            # Local dev: Redis + PostgreSQL + Vyapaar
├── archestra.yaml                # Archestra deployment manifest
├── .env.example                  # Environment variable template
├── .env                          # Local secrets (NEVER commit)
│
├── src/
│   ├── __init__.py
│   ├── server.py                 # FastMCP server entrypoint (SSE transport)
│   ├── config.py                 # Pydantic Settings: env loading + validation
│   ├── models.py                 # Pydantic V2 data models (webhook payloads, policies)
│   │
│   ├── ingress/
│   │   ├── __init__.py
│   │   └── webhook.py            # Razorpay webhook handler + signature verification
│   │
│   ├── governance/
│   │   ├── __init__.py
│   │   ├── engine.py             # Core decision engine (orchestrates all checks)
│   │   ├── budget.py             # Atomic Redis budget checking (INCRBY)
│   │   └── policy.py             # Agent policy CRUD from PostgreSQL
│   │
│   ├── reputation/
│   │   ├── __init__.py
│   │   └── safe_browsing.py      # Google Safe Browsing v4 integration
│   │
│   ├── egress/
│   │   ├── __init__.py
│   │   └── razorpay_actions.py   # Approve/reject payout via Razorpay SDK
│   │
│   ├── audit/
│   │   ├── __init__.py
│   │   └── logger.py             # PostgreSQL audit log writer
│   │
│   └── db/
│       ├── __init__.py
│       ├── postgres.py           # asyncpg connection pool
│       ├── redis_client.py       # Redis connection (aioredis)
│       └── migrations/
│           └── 001_init.sql      # Initial schema migration
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # Shared fixtures (fakeredis, mock DB)
│   ├── test_webhook.py           # Signature verification tests
│   ├── test_budget.py            # Atomic budget + race condition tests
│   ├── test_safe_browsing.py     # Google API response handling
│   ├── test_governance.py        # End-to-end decision engine tests
│   └── test_models.py            # Pydantic model validation tests
│
└── scripts/
    ├── seed_policies.py          # Seed sample agent policies
    └── simulate_webhook.py       # Send test webhooks to local server
```

---

## 11. Implementation Plan (Phased)

### Phase 1: Scaffolding & Configuration (Day 1)
- [ ] Initialize project: `uv init vyapaar-mcp && cd vyapaar-mcp`
- [ ] Create `pyproject.toml` with all dependencies (see §5)
- [ ] Create `src/config.py` using `pydantic-settings`:
  ```python
  from pydantic_settings import BaseSettings
  from pydantic import ConfigDict

  class VyapaarConfig(BaseSettings):
      model_config = ConfigDict(env_prefix="VYAPAAR_")
      razorpay_key_id: str
      razorpay_key_secret: str
      razorpay_webhook_secret: str
      google_safe_browsing_key: str
      redis_url: str = "redis://localhost:6379"
      postgres_dsn: str = "postgresql://vyapaar:securepass@localhost:5432/vyapaar_db"
  ```
- [ ] Create `src/models.py` with Pydantic V2 models for all API payloads (see §7)
- [ ] Create `docker-compose.yml` for Redis + PostgreSQL
- [ ] Create `.env.example` template
- [ ] Create `src/db/migrations/001_init.sql` with schema from §9
- [ ] Verify: `mypy --strict src/` passes with zero errors

### Phase 2: Webhook Ingress (Day 1–2)
- [ ] Create `src/ingress/webhook.py`
- [ ] Implement `verify_razorpay_signature()` — HMAC-SHA256 (see §7.1)
- [ ] Implement idempotency check: `Redis SETNX vyapaar:idempotent:{webhook_id}`
- [ ] Parse `payout.queued` webhook payload into Pydantic model
- [ ] Extract `agent_id` from `payload.payout.entity.notes.agent_id`
- [ ] Extract `vendor_url` from `payload.payout.entity.notes.vendor_url`
- [ ] Write tests: `tests/test_webhook.py` (valid sig, invalid sig, replay attack)
- [ ] Verify: Invalid signatures return 401, replayed webhooks are skipped

### Phase 3: Governance Engine (Day 2–3)
- [ ] Create `src/governance/budget.py` — Atomic budget check:
  ```python
  async def check_budget_atomic(redis: Redis, agent_id: str, amount: int, daily_limit: int) -> bool:
      key = f"vyapaar:budget:{agent_id}:{date.today().strftime('%Y%m%d')}"
      new_total = await redis.incrby(key, amount)
      if new_total > daily_limit:
          await redis.decrby(key, amount)  # Rollback
          return False
      await redis.expire(key, 90000)  # 25 hours TTL
      return True
  ```
- [ ] Create `src/governance/policy.py` — Fetch agent policy from PostgreSQL
- [ ] Create `src/governance/engine.py` — Orchestrator implementing Decision Matrix (§8)
- [ ] Implement per-transaction limit check
- [ ] Implement domain whitelist/blacklist check
- [ ] Implement approval threshold → HOLD decision
- [ ] Write tests: `tests/test_budget.py` (concurrent spending, limit enforcement)
- [ ] Write tests: `tests/test_governance.py` (full decision matrix coverage)

### Phase 4: Reputation Check (Day 3)
- [ ] Create `src/reputation/safe_browsing.py`
- [ ] Implement `check_url_safety(url: str)` using httpx (async)
- [ ] Handle all 4 threat types: MALWARE, SOCIAL_ENGINEERING, UNWANTED_SOFTWARE, PHA
- [ ] Implement Redis caching for results (`vyapaar:reputation:{hash}`, 5min TTL)
- [ ] Handle API errors gracefully (timeout → default to HOLD, not APPROVE)
- [ ] Write tests: `tests/test_safe_browsing.py` (safe URL, unsafe URL, API timeout)

### Phase 5: Razorpay Egress (Day 3–4)
- [ ] Create `src/egress/razorpay_actions.py`
- [ ] Implement `approve_payout(payout_id)` using `razorpay.payout.approve()`
- [ ] Implement `reject_payout(payout_id, reason)` using payout cancel API
- [ ] Handle Razorpay API errors (retry with exponential backoff for 5xx)
- [ ] Write audit log entry for every decision (§9.1 `audit_logs`)

### Phase 6: MCP Server & Tools (Day 4–5)
- [ ] Create `src/server.py` — FastMCP server with SSE transport
- [ ] Register all 6 MCP tools (see §6)
- [ ] Wire `handle_razorpay_webhook` tool → Ingress → Governance → Egress pipeline
- [ ] Implement `check_vendor_reputation` as standalone tool
- [ ] Implement `get_agent_budget` (reads Redis counter + PostgreSQL policy)
- [ ] Implement `get_audit_log` (reads PostgreSQL with filters)
- [ ] Implement `set_agent_policy` (writes to PostgreSQL)
- [ ] Implement `health_check` (pings Redis, PostgreSQL, Razorpay)
- [ ] Verify: Server starts with `uv run mcp run src/server.py`

### Phase 7: Integration & Deployment (Day 5–6)
- [ ] Create `Dockerfile` (multi-stage: builder → slim runtime)
- [ ] Create `archestra.yaml` deployment manifest
- [ ] End-to-end test: webhook → governance → approve/reject
- [ ] Setup Slack MCP server integration for human-in-the-loop
- [ ] Create `scripts/simulate_webhook.py` for demo
- [ ] Create `scripts/seed_policies.py` for sample data
- [ ] Verify: All Definition of Done criteria pass (§17)

---

## 12. Security Model

### 12.1 Authentication & Authorization

| Layer | Mechanism | Details |
|:---|:---|:---|
| **Webhook Ingress** | HMAC-SHA256 | Verify `X-Razorpay-Signature` using `RAZORPAY_WEBHOOK_SECRET` |
| **Razorpay API** | HTTP Basic Auth | `RAZORPAY_KEY_ID:RAZORPAY_KEY_SECRET` Base64 encoded |
| **Google API** | API Key | `GOOGLE_SAFE_BROWSING_KEY` as query parameter |
| **MCP Transport** | SSE (Server-Sent Events) | Archestra handles auth at the platform level |

### 12.2 Secrets Management

- **Local Dev:** `.env` file (listed in `.gitignore`)
- **Production:** Archestra Secrets Manager (backed by HashiCorp Vault or K8s Secrets)
- **CI/CD:** GitHub Actions secrets → injected as env vars

### 12.3 Data Security

| Data | Classification | Handling |
|:---|:---|:---|
| API Keys | **Secret** | Never logged, never in git, rotated quarterly |
| Payout Amounts | **Confidential** | Logged in audit_logs, encrypted at rest in PostgreSQL |
| Vendor URLs | **Internal** | Logged for audit, hashed for Redis cache keys |
| Webhook Payloads | **Confidential** | Validated, parsed, not stored raw |

### 12.4 Threat Mitigations

| Threat | Mitigation |
|:---|:---|
| Webhook spoofing | HMAC-SHA256 signature verification |
| Replay attacks | Redis-based idempotency (`SETNX` with 48h TTL) |
| Race conditions | Atomic Redis `INCRBY` with rollback |
| SQL injection | Parameterized queries via `asyncpg` |
| Budget drain | Per-agent daily limits + per-txn limits |
| Malicious vendors | Google Safe Browsing + domain blacklists |
| API key leakage | Pydantic Settings from env, `.gitignore` enforcement |

---

## 13. Environment Configuration

### `.env.example`
```bash
# ============================================
# Vyapaar MCP — Environment Configuration
# ============================================

# --- Razorpay X (Sandbox) ---
VYAPAAR_RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx
VYAPAAR_RAZORPAY_KEY_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
VYAPAAR_RAZORPAY_WEBHOOK_SECRET=whsec_xxxxxxxxxxxx

# --- Google Safe Browsing v4 ---
# Get key from: https://console.cloud.google.com/apis/credentials
# Enable: Safe Browsing API
VYAPAAR_GOOGLE_SAFE_BROWSING_KEY=AIzaSyXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX

# --- Redis ---
VYAPAAR_REDIS_URL=redis://localhost:6379/0

# --- PostgreSQL ---
VYAPAAR_POSTGRES_DSN=postgresql://vyapaar:securepass@localhost:5432/vyapaar_db

# --- Slack (Human-in-the-Loop, optional) ---
SLACK_BOT_TOKEN=xoxb-xxxxxxxxxxxx-xxxxxxxxxxxx
SLACK_TEAM_ID=TXXXXXXXXXX
SLACK_CHANNEL_ID=CXXXXXXXXXX

# --- Server ---
VYAPAAR_HOST=0.0.0.0
VYAPAAR_PORT=8000
VYAPAAR_LOG_LEVEL=INFO
```

---

## 14. Error Handling & Resilience

### 14.1 Failure Modes

| Failure | Impact | Response |
|:---|:---|:---|
| Redis down | Cannot check budget or idempotency | **REJECT** all payouts (fail-closed) + alert ops |
| PostgreSQL down | Cannot fetch policy or write audit | **REJECT** + write to local filesystem fallback |
| Google Safe Browsing timeout | Cannot check reputation | **HOLD** payout for manual review |
| Google Safe Browsing 4xx | Bad API key or quota exceeded | **HOLD** + alert ops to fix key |
| Razorpay API 5xx | Cannot approve/reject payout | Retry with exponential backoff (max 3 attempts) |
| Razorpay API 4xx | Bad request / payout already processed | Log error, do not retry |

### 14.2 Design Principle: Fail-Closed

> **If in doubt, REJECT.** It is always safer to block a legitimate payment (which can be manually approved) than to approve a fraudulent one (which cannot be reversed).

### 14.3 Retry Strategy

```python
RETRY_CONFIG = {
    "max_attempts": 3,
    "base_delay_seconds": 1,
    "max_delay_seconds": 30,
    "backoff_multiplier": 2,
    "retryable_status_codes": [500, 502, 503, 504],
}
```

---

## 15. Testing Strategy

### 15.1 Test Pyramid

| Layer | Tool | What It Tests | Count Target |
|:---|:---|:---|:---|
| **Unit** | pytest | Individual functions (signature verify, budget math, model validation) | ~30 tests |
| **Integration** | pytest + fakeredis + testcontainers | Redis atomic operations, PostgreSQL queries | ~15 tests |
| **E2E** | pytest + httpx | Full webhook → decision → action pipeline | ~10 tests |

### 15.2 Critical Test Cases

```python
# tests/test_budget.py — Race Condition Prevention
import asyncio
from fakeredis.aioredis import FakeRedis

async def test_concurrent_budget_enforcement():
    """Two agents spending simultaneously should not exceed limit."""
    redis = FakeRedis()
    daily_limit = 100000  # ₹1,000

    # Simulate 20 concurrent ₹100 (10000 paise) requests
    results = await asyncio.gather(*[
        check_budget_atomic(redis, "agent-001", 10000, daily_limit)
        for _ in range(20)
    ])

    approved = sum(1 for r in results if r is True)
    assert approved == 10  # Exactly 10 × ₹100 = ₹1,000 limit
    assert results.count(False) == 10  # Remaining 10 rejected
```

```python
# tests/test_webhook.py — Signature Verification
def test_valid_signature_passes():
    body = b'{"event": "payout.queued"}'
    secret = "test_webhook_secret"
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_razorpay_signature(body, sig, secret) is True

def test_tampered_payload_rejected():
    body = b'{"event": "payout.queued"}'
    tampered = b'{"event": "payout.queued", "injected": true}'
    secret = "test_webhook_secret"
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_razorpay_signature(tampered, sig, secret) is False
```

### 15.3 Running Tests
```bash
# Full suite
uv run pytest tests/ -v --tb=short

# With coverage
uv run pytest tests/ --cov=src --cov-report=term-missing

# Type checking
uv run mypy --strict src/
```

---

## 16. FOSS Agent Skills (NPX Configuration)

> *External MCP servers loaded via `npx` to extend agent capabilities.*

### 16.1 Database Skill (PostgreSQL)

* **Skill Identity:** `@modelcontextprotocol/server-postgres`
* **Purpose:** SQL query tools for fetching Agent Policies and Audit Logs.
* **Agent Config:**
```json
"postgres": {
  "command": "npx",
  "args": [
    "-y",
    "@modelcontextprotocol/server-postgres",
    "postgresql://vyapaar:securepass@localhost:5432/vyapaar_db"
  ]
}
```

### 16.2 Communication Skill (Slack — Human-in-the-Loop)

* **Skill Identity:** `@modelcontextprotocol/server-slack`
* **Purpose:** Send approval requests for high-value or flagged transactions to a Slack channel.
* **Agent Config:**
```json
"slack": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-slack"],
  "env": {
    "SLACK_BOT_TOKEN": "${SLACK_BOT_TOKEN}",
    "SLACK_TEAM_ID": "${SLACK_TEAM_ID}"
  }
}
```

### 16.3 File System Skill (Failsafe Audit Logging)

* **Skill Identity:** `@modelcontextprotocol/server-filesystem`
* **Purpose:** Emergency local logging if PostgreSQL is unreachable (fail-safe).
* **Agent Config:**
```json
"filesystem": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-filesystem", "./audit_logs"]
}
```

---

## 17. Development Environment — Agent Skills

> *Meta-Instructions: Before writing any code, the Agentic IDE SHOULD install these context skills for best-practice patterns.*

### 17.1 Redis Context (Atomic Locking)
> **Goal:** Prevent race conditions in financial logic.  
> **Command:** `npx skills add redis/agent-skills`  
> **Constraint:** Use patterns from `redis/agent-skills/SKILL.md` for the `check_budget_atomic` function.

### 17.2 Pydantic Context (Type Safety)
> **Goal:** Ensure strictly typed webhook payloads using Pydantic V2.  
> **Command:** `npx skills add microsoft/agent-skills --skill pydantic-models-py`  
> **Constraint:** All API data classes must use `pydantic.BaseModel` with V2 `ConfigDict(strict=True)`.

### 17.3 Testing Context (Pytest)
> **Goal:** Write non-flaky, deterministic integration tests.  
> **Command:** `npx skills add vercel-labs/agent-skills --skill python-testing`  
> **Constraint:** Use `pytest` fixtures for the Redis mock via `fakeredis`.

---

## 18. Archestra Deployment

### 18.1 Deployment Manifest

**File: `archestra.yaml`**
```yaml
version: "1.0"
server:
  name: "vyapaar-mcp"
  description: "Financial Governance MCP Server — Razorpay X + Google Safe Browsing"
  transport:
    type: "sse"
    url: "http://localhost:8000/sse"
  health_check:
    endpoint: "/health"
    interval: "30s"
  
tools:
  - name: "handle_razorpay_webhook"
    description: "Ingest and process Razorpay X webhook events (payout.queued)"
  - name: "check_vendor_reputation"
    description: "Check a URL against Google Safe Browsing v4 threat lists"
  - name: "get_agent_budget"
    description: "Get current daily spend and remaining budget for an agent"
  - name: "get_audit_log"
    description: "Retrieve spending audit trail with filtering"
  - name: "set_agent_policy"
    description: "Create or update agent spending policies"
  - name: "health_check"
    description: "Check health of all dependent services"

secrets:
  - name: "VYAPAAR_RAZORPAY_KEY_ID"
    source: "vault"
  - name: "VYAPAAR_RAZORPAY_KEY_SECRET"
    source: "vault"
  - name: "VYAPAAR_RAZORPAY_WEBHOOK_SECRET"
    source: "vault"
  - name: "VYAPAAR_GOOGLE_SAFE_BROWSING_KEY"
    source: "vault"

resources:
  redis:
    image: "redis:7-alpine"
    port: 6379
  postgres:
    image: "postgres:15-alpine"
    port: 5432
    env:
      POSTGRES_DB: "vyapaar_db"
      POSTGRES_USER: "vyapaar"
      POSTGRES_PASSWORD: "${POSTGRES_PASSWORD}"
```

### 18.2 Dockerfile (Multi-Stage)
```dockerfile
# Stage 1: Build
FROM python:3.12-slim AS builder
WORKDIR /app
RUN pip install uv
COPY pyproject.toml .
RUN uv sync --frozen --no-dev

# Stage 2: Runtime
FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY src/ src/
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["python", "-m", "mcp", "run", "src/server.py"]
```

### 18.3 Docker Compose (Local Dev)
```yaml
version: "3.8"
services:
  vyapaar:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      - redis
      - postgres

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  postgres:
    image: postgres:15-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: vyapaar_db
      POSTGRES_USER: vyapaar
      POSTGRES_PASSWORD: securepass
    volumes:
      - pg_data:/var/lib/postgresql/data
      - ./src/db/migrations:/docker-entrypoint-initdb.d

volumes:
  redis_data:
  pg_data:
```

---

## 19. Definition of Done

### Must-Have (MVP)
- [ ] **Server boots:** `uv run mcp run src/server.py` starts without errors
- [ ] **Signature check:** Webhook with invalid `X-Razorpay-Signature` returns 401
- [ ] **Idempotency:** Replayed webhook is silently skipped (not double-processed)
- [ ] **Budget enforcement:** Transaction exceeding daily limit is REJECTED on Razorpay
- [ ] **Reputation check:** URL flagged by Google Safe Browsing triggers REJECT
- [ ] **Atomic concurrency:** 50 parallel requests correctly enforce a budget limit (no overspend)
- [ ] **Audit trail:** Every decision is logged to PostgreSQL with reason code
- [ ] **Type safe:** `mypy --strict src/` exits with 0 errors
- [ ] **Tests pass:** `pytest tests/ -v` all green

### Should-Have (Polish)
- [ ] **Slack integration:** High-value payouts trigger approval request in Slack
- [ ] **Domain blacklist:** Admin can block specific vendor domains via `set_agent_policy`
- [ ] **Health check:** `health_check` tool returns status of Redis, PostgreSQL, Razorpay
- [ ] **Docker:** `docker compose up` brings up full stack in one command
- [ ] **Archestra deploy:** `archestra.yaml` passes platform validation

### Nice-to-Have (Demo Impact)
- [ ] **CLI dashboard:** Real-time audit log viewer in the terminal
- [ ] **Metrics:** Prometheus-compatible `/metrics` endpoint for Archestra observability
- [ ] **Demo script:** `scripts/simulate_webhook.py` shows APPROVE → REJECT → HOLD flow live

---

## 20. Essential Resources

| Resource | URL |
|:---|:---|
| **Hackathon** | [2 Fast 2 MCP](https://www.wemakedevs.org/hackathons/2fast2mcp) |
| **Archestra Platform** | [archestra.ai](https://archestra.ai) |
| **Archestra GitHub** | [github.com/archestra-ai/archestra](https://github.com/archestra-ai/archestra) |
| **Archestra Docs** | [archestra.ai/docs](https://archestra.ai/docs/platform-quickstart) |
| **Razorpay X Payouts API** | [razorpay.com/docs/api/x/payouts](https://razorpay.com/docs/api/x/payouts/) |
| **Razorpay Webhook Setup** | [razorpay.com/docs/webhooks](https://razorpay.com/docs/webhooks/setup-edit-payouts/) |
| **Google Safe Browsing v4** | [developers.google.com/safe-browsing](https://developers.google.com/safe-browsing/v4/lookup-api) |
| **FastMCP Docs** | [modelcontextprotocol.io](https://modelcontextprotocol.io) |
| **Agent Skills Registry** | [skills.sh](https://skills.sh) |
| **Pydantic V2 Docs** | [docs.pydantic.dev](https://docs.pydantic.dev/latest/) |
| **Redis Commands** | [redis.io/commands](https://redis.io/commands/) |

