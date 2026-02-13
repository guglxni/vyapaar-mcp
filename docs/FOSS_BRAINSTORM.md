# Vyapaar MCP — FOSS Integration Brainstorm

## Current State
- **9 MCP Tools**: handle_razorpay_webhook, poll_razorpay_payouts, check_vendor_reputation, get_agent_budget, get_audit_log, set_agent_policy, health_check, get_metrics, handle_slack_action
- **Stack**: Python 3.12 + FastMCP, Go sidecar (Razorpay), Redis, PostgreSQL, Slack
- **Tests**: 100/100 passing

---

## Part 1: FOSS Demo App to Showcase Vyapaar MCP

### Option A: Streamlit Dashboard (⭐ RECOMMENDED)
**Repo**: [streamlit/streamlit](https://github.com/streamlit/streamlit) — Apache 2.0, 40k+ stars, Python-native

A single-page visual dashboard that calls Vyapaar MCP tools and shows the full governance lifecycle:

| Tab | MCP Tools Used | What It Shows |
|-----|---------------|---------------|
| **Health** | `health_check`, `get_metrics` | System status, circuit breaker states, Redis/Postgres health |
| **Policies** | `set_agent_policy`, `get_agent_budget` | Create/edit agent policies, view budget utilization bars |
| **Vendor Check** | `check_vendor_reputation` | Enter a URL → show Google Safe Browsing score, reputation cache |
| **Payment Flow** | `handle_razorpay_webhook`, `poll_razorpay_payouts` | Simulate webhook → show governance decision → Slack notification |
| **Audit Trail** | `get_audit_log` | Searchable table of all governance decisions with timestamps |
| **Slack Actions** | `handle_slack_action` | Show approve/reject button workflow |

**Effort**: ~2 hours, single `demo_app.py` file
**Why it wins**: Visual, impressive for hackathon, zero JS needed, runs locally

### Option B: CLI Demo Script (Fastest)
A Python script that runs the full vendor payment lifecycle E2E:
```
1. set_agent_policy → Create "payments-agent" with ₹50k daily limit
2. check_vendor_reputation → Verify vendor URL is safe
3. handle_razorpay_webhook → Simulate incoming payment notification
4. get_agent_budget → Show remaining budget after transaction
5. get_audit_log → Show full audit trail
6. get_metrics → Show governance statistics
7. health_check → Confirm all systems operational
```

**Effort**: ~30 minutes
**Why**: Terminal demo, no dependencies, pure MCP tool calls

### Option C: FastAPI + HTMX Mini-App
A lightweight web app with:
- Vendor onboarding form (reputation check on submit)
- Payment approval queue (shows pending payouts)
- Budget dashboard per agent
- Audit log viewer

**Effort**: ~4 hours
**Why**: More "app-like", good for showing how MCP serverintegrates into a real product

---

## Part 2: FOSS Repos to Plug INTO Vyapaar MCP (Enhancements)

### 🏆 Tier 1: High-Impact, Easy Integration

#### 1. GLEIF LEI Lookup — Company Identity Verification
**Repo**: [olgasafonova/gleif-mcp-server](https://github.com/olgasafonova/gleif-mcp-server)
**What**: Access the Global Legal Entity Identifier (LEI) database — verify company registration, KYC
**Integration**: Add `verify_vendor_entity` MCP tool that:
- Takes company name or LEI code
- Returns legal name, jurisdiction, registration status
- Feeds into reputation score alongside Google Safe Browsing
**Impact**: Elevates vendor reputation from "URL safety" to "full KYC-lite verification"

#### 2. Anomaly Detection — Transaction Risk Scoring
**Repo**: [scikit-learn](https://github.com/scikit-learn/scikit-learn) (BSD-3, 61k+ stars)
**What**: Use IsolationForest for unsupervised anomaly detection on transaction patterns
**Integration**: Add `score_transaction_risk` MCP tool that:
- Analyzes amount, time, frequency patterns
- Returns risk score 0-100
- Auto-escalates to Slack for high-risk transactions
- Feeds into governance engine as additional policy dimension
**Impact**: ML-powered fraud detection, very demo-impressive

#### 3. hledger — Double-Entry Accounting Audit
**Repo**: [simonmichael/hledger](https://github.com/simonmichael/hledger) + [iiAtlas/hledger-mcp](https://github.com/iiAtlas/hledger-mcp)
**What**: Plain-text double-entry accounting
**Integration**: Add `record_ledger_entry` MCP tool that:
- Every approved payout creates a journal entry
- Balance sheet always reconciles
- Auditors can verify with standard accounting tools
**Impact**: Full financial audit trail, compliance-grade

#### 4. ntfy — Multi-Channel Notifications
**Repo**: [binwiederhier/ntfy](https://github.com/binwiederhier/ntfy) (Apache 2.0, 20k+ stars)
**What**: Self-hosted push notifications (phone, desktop, email)
**Integration**: Add as notification fallback when Slack is down (circuit breaker):
- High-risk transactions → ntfy push notification to phone
- Slack circuit open → automatic failover to ntfy
**Impact**: Multi-channel alerting, resilience improvement

### 🥈 Tier 2: Medium-Impact, Moderate Effort

#### 5. Apache Fineract (via Mifos MCP) — Core Banking
**Repo**: [openMF/mcp-mifosx](https://github.com/openMF/mcp-mifosx) + [apache/fineract](https://github.com/apache/fineract)
**What**: Open-source core banking platform with its own MCP server
**Integration**: Chain Vyapaar MCP as governance layer in front of Mifos:
- Mifos handles loans, savings, accounts
- Vyapaar governs every disbursement/transfer
- Create an MCP-to-MCP bridge
**Impact**: Enterprise banking governance use case

#### 6. Datapane/Plotly — Rich Analytics Reports
**Repo**: [plotly/plotly.py](https://github.com/plotly/plotly.py) (MIT, 16k+ stars)
**What**: Interactive charts and dashboards
**Integration**: Add `generate_report` MCP tool that:
- Creates visual PDF/HTML reports from audit data
- Budget utilization charts, trend analysis
- Auto-generates weekly governance summaries
**Impact**: Executive-ready reporting

#### 7. Open Policy Agent (OPA) — Policy-as-Code
**Repo**: [open-policy-agent/opa](https://github.com/open-policy-agent/opa) (Apache 2.0, 10k+ stars)
**What**: General-purpose policy engine, industry standard
**Integration**: Replace/augment current governance engine with Rego policies:
- `policy.rego` files for complex rules
- Multi-dimensional policies (time, amount, vendor, geography)
- Policy versioning and rollback
**Impact**: Enterprise-grade policy engine, industry-standard compliance

#### 8. Langfuse — LLM Observability
**Repo**: [langfuse/langfuse](https://github.com/langfuse/langfuse) (MIT, 8k+ stars)
**What**: Open-source LLM observability + prompt management
**Integration**: Trace every MCP tool call:
- Monitor latency, token usage, error rates
- Dashboard for governance decision analytics
- Cost tracking per agent
**Impact**: Full observability stack

### 🥉 Tier 3: Nice-to-Have, Higher Effort

#### 9. Supabase — Migrate from raw Postgres
**Repo**: [supabase/supabase](https://github.com/supabase/supabase)
**What**: Open-source Firebase alternative with real-time subscriptions
**Integration**: Real-time audit log streaming, row-level security, auto-generated APIs

#### 10. n8n — Workflow Automation
**Repo**: [n8n-io/n8n](https://github.com/n8n-io/n8n) (fair-code, 55k+ stars)
**What**: Visual workflow automation
**Integration**: Build visual payment approval workflows, connect to external systems

#### 11. MindsDB — AI/ML in SQL
**Repo**: [mindsdb/mindsdb](https://github.com/mindsdb/mindsdb)
**What**: AI tables in database
**Integration**: Predictive analytics on transaction patterns directly in SQL

#### 12. Grafana — Metrics Dashboard
**Repo**: [grafana/grafana](https://github.com/grafana/grafana) (AGPL-3.0, 67k+ stars)
**What**: Industry-standard observability dashboards
**Integration**: Export Vyapaar metrics to Prometheus → Grafana dashboards

---

## Part 3: Recommended Demo Strategy

### For Hackathon Demo (2-3 hours total implementation)

```
┌─────────────────────────────────────────────────┐
│              DEMO FLOW (5 minutes)               │
├─────────────────────────────────────────────────┤
│                                                  │
│  1. Show Health Dashboard (Streamlit)            │
│     └─ All systems green, 9 tools registered     │
│                                                  │
│  2. Set Agent Policy                             │
│     └─ "payments-bot" → ₹50,000/day, ₹10k/txn   │
│                                                  │
│  3. Vendor Reputation Check                      │
│     └─ Check google.com (safe) vs bad URL (flag) │
│                                                  │
│  4. Simulate Razorpay Webhook                    │
│     └─ Incoming ₹8,000 payment captured          │
│     └─ Governance: ✅ under budget, vendor safe   │
│     └─ Slack notification sent                   │
│                                                  │
│  5. Simulate Over-Budget Transaction             │
│     └─ ₹55,000 payout attempt                   │
│     └─ Governance: ❌ DENIED - exceeds daily limit│
│     └─ Slack alert with details                  │
│                                                  │
│  6. Show Slack Interactive Buttons               │
│     └─ Approve/Reject from Slack                 │
│     └─ Human-in-the-loop decision                │
│                                                  │
│  7. Show Audit Trail                             │
│     └─ Every decision logged with timestamps     │
│                                                  │
│  8. Show Metrics Dashboard                       │
│     └─ Requests, approvals, denials, latencies   │
│                                                  │
└─────────────────────────────────────────────────┘
```

### Implementation Plan

| # | Task | Time | Files |
|---|------|------|-------|
| 1 | Create `demo/app.py` (Streamlit dashboard) | 1.5h | 1 file |
| 2 | Create `demo/scenarios.py` (demo scenarios) | 30m | 1 file |
| 3 | Add `demo/requirements.txt` | 5m | 1 file |
| 4 | Create `scripts/run_demo.sh` | 5m | 1 file |

### New MCP Tool Ideas (for enhancement)

| Tool | Source FOSS | Effort |
|------|------------|--------|
| `verify_vendor_entity` | GLEIF API (free, no key) | 1h |
| `score_transaction_risk` | scikit-learn IsolationForest | 2h |
| `generate_governance_report` | plotly + jinja2 | 2h |

---

## Part 4: Architecture — How Everything Connects

```
                    ┌──────────────────┐
                    │   VS Code / IDE  │
                    │   (MCP Client)   │
                    └────────┬─────────┘
                             │ stdio
                    ┌────────▼─────────┐
                    │  VYAPAAR MCP     │
                    │  (9+ tools)      │
                    │  FastMCP Server  │
                    └───┬───┬───┬──────┘
                        │   │   │
          ┌─────────────┤   │   ├──────────────┐
          │             │   │   │              │
    ┌─────▼─────┐ ┌─────▼───▼───▼─────┐  ┌────▼─────┐
    │ Razorpay  │ │   Governance      │  │  Slack   │
    │ Go Sidecar│ │   Engine          │  │  Bot     │
    │ (Payments)│ │   (Policies+ML)   │  │ (Human)  │
    └─────┬─────┘ └───────┬───────────┘  └──────────┘
          │               │
    ┌─────▼─────┐   ┌─────▼─────┐
    │ Razorpay  │   │ PostgreSQL│◄── Audit Logs
    │ Sandbox   │   │ + Redis   │◄── Budget Tracking
    └───────────┘   └───────────┘

    ═══════════════════════════════════
    FOSS ENHANCEMENT LAYER (optional)
    ═══════════════════════════════════
    
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │  GLEIF   │  │ sklearn  │  │  ntfy    │
    │  (KYC)   │  │ (Fraud)  │  │ (Alerts) │
    └──────────┘  └──────────┘  └──────────┘
```

---

## Part 5: Quick Win — What to Build Now

**Recommended: Build the Streamlit demo app + CLI demo script.**

These two together give you:
1. **Visual appeal** (Streamlit) for live demo / screenshots
2. **Scriptable proof** (CLI) for automated testing / CI

Both use only the existing 9 MCP tools — no new code needed in the server itself.

For enhancement, **GLEIF vendor verification** is the highest-impact, lowest-effort addition:
- Free API, no key needed
- Adds real KYC capability
- ~50 lines of code
- Makes the "vendor reputation" story much stronger
