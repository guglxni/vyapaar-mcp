# Vyapaar MCP — Hackathon Submission

> **2 Fast 2 MCP Hackathon** | **$10,000+ Prizes** | **Archestra Platform**

---

## 🏁 Project Overview

**Vyapaar MCP** is a production-grade governance layer for AI agents that enforces financial controls, vendor vetting, and audit trails — all via the Model Context Protocol (MCP).

In the race to deploy AI agents, Vyapaar ensures they don't crash the company's finances. Think of it as your AI's **CFO** — always watching, always enforcing budgets, and never letting a suspicious vendor slip through.

---

## 🏆 Hackathon Alignment

| Judging Criteria | How We Score |
|------------------|--------------|
| **Potential Impact** | Solves real problem: AI agents spending company money without oversight |
| **Creativity & Originality** | First MCP-based financial governance server with 6-layer security |
| **Learning & Growth** | Built from scratch with FOSS integrations (GLEIF, IsolationForest) |
| **Technical Implementation** | Clean architecture with Redis atomic ops, circuit breakers, async-first |
| **Aesthetics & UX** | Streamlit dashboard with real-time metrics, beautiful dark theme |
| **Best Use of Archestra** | Full Archestra integration with SSE transport, Foundry LLM |

---

## 🚀 Key Features

### 🔒 Security (6 Layers)

1. **Google Safe Browsing v4** — Blocks malware vendor sites
2. **GLEIF Verification** — Confirms vendors are real legal entities
3. **Budget Enforcement** — Atomic Redis limits, no overspending
4. **Human Approval Gate** — Slack integration for high-value txns
5. **ML Anomaly Detection** — IsolationForest catches unusual patterns
6. **Policy Engine** — Real-time domain blocking

### ⚡ Speed

- Sub-millisecond budget checks via Redis Lua scripts
- Circuit breakers prevent cascade failures
- Async-first Python architecture

### 🛠️ Architecture

```
┌─────────────┐      ┌─────────────────┐      ┌──────────────┐
│ MCP Client │─────▶│  Vyapaar MCP    │─────▶│ Razorpay X   │
│ (Claude,   │       │  (FastMCP)     │      │  (Banking)   │
│  Cursor)   │       │                 │      └──────────────┘
└─────────────┘      │ ┌─────────────┐ │
                     │ │ Governance  │ │      ┌──────────────┐
                     │ │ Engine       │ │─────▶│ PostgreSQL   │
                     │ └─────────────┘ │      │ (Audit Logs) │
                     │ ┌─────────────┐ │      └──────────────┘
                     │ │ Reputation   │ │
                     │ │ (SB, GLEIF) │ │      ┌──────────────┐
                     │ └─────────────┘ │─────▶│ Redis        │
                     │ ┌─────────────┐ │      │ (Budgets)    │
                     │ │ ML Anomaly  │ │      └──────────────┘
                     │ │ (IsolationF) │ │
                     │ └─────────────┘ │      ┌──────────────┐
                     └─────────────────┘─────▶│ Slack        │
                                             │ (Human Loop)  │
                                             └──────────────┘
```

---

## 📊 Demo Flow (3 Minutes)

### Scenario 1: Legitimate Payment ✅
- Agent: `marketing-bot`
- Vendor: Google LLC
- Amount: ₹2,500
- **Result:** APPROVED in 247ms

### Scenario 2: Malware Site ❌
- Agent: `marketing-bot`
- Vendor: `sketchy-vendor.xyz`
- **Result:** BLOCKED by Safe Browsing API

### Scenario 3: Budget Exceeded 💰
- Agent spent: ₹45,000 / ₹50,000 limit
- New request: ₹8,000
- **Result:** REJECTED — would exceed limit

### Scenario 4: Human Approval 👤
- Amount: ₹8,000 (above ₹5,000 threshold)
- **Result:** HELD → Slack notification sent

### Scenario 5: ML Anomaly 🤖
- Unusual hour (3:47 AM)
- First transaction with unknown vendor
- **Result:** FLAGGED (87% anomaly score)

### Scenario 6: Policy Change ⚙️
- Add rule: Block `.xyz` domains
- **Result:** Immediately effective, no redeploy

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Server** | FastMCP | 12 MCP tools exposed |
| **Database** | PostgreSQL | Audit trail storage |
| **Cache** | Redis | Atomic budget counters |
| **Banking** | Razorpay X | Payout execution |
| **LLM** | Azure AI Foundry | Governance copilot |
| **Human Loop** | Slack | Approval workflow |
| **ML** | scikit-learn | Anomaly detection |
| **Deployment** | Archestra | SSE transport, production |

---

## 📈 MCP Tools (12 Total)

| # | Tool | Function |
|---|------|----------|
| 1 | `handle_razorpay_webhook` | Process webhook → governance → action |
| 2 | `poll_razorpay_payouts` | Poll API instead of webhooks |
| 3 | `check_vendor_reputation` | Google Safe Browsing check |
| 4 | `verify_vendor_entity` | GLEIF legal entity lookup |
| 5 | `score_transaction_risk` | ML anomaly scoring |
| 6 | `get_agent_risk_profile` | Agent spending patterns |
| 7 | `get_agent_budget` | Current spend & limits |
| 8 | `set_agent_policy` | Create/update policies |
| 9 | `get_audit_log` | Query audit trail |
| 10 | `handle_slack_action` | Process approve/reject |
| 11 | `health_check` | Service status |
| 12 | `get_metrics` | Prometheus metrics |

---

## 🏃 Quick Start

```bash
# Clone and setup
git clone https://github.com/guglxni/vyapaar-mcp.git
cd vyapaar-mcp

# Start infrastructure
docker compose up -d redis postgres

# Configure
cp .env.example .env
# Add your Razorpay, Google, Slack keys

# Run dashboard
streamlit run demo/dashboard.py
```

---

## 🔗 Archestra Integration

Vyapaar is built for **Archestra** deployment:

- **SSE Transport** — Stream events to Archestra
- **Foundry LLM** — Azure AI Foundry for governance copilot
- **Vault Secrets** — Environment-driven configuration
- **Prometheus** — Built-in observability

```yaml
# deploy/archestra.yaml
apiVersion: v1
kind: Service
metadata:
  name: vyapaar-mcp
spec:
  ports:
    - port: 8000
      targetPort: 8000
  selector:
    app: vyapaar-mcp
```

---

## 📁 Project Structure

```
vyapaar-mcp/
├── src/vyapaar_mcp/      # Core application
│   ├── server.py          # FastMCP + 12 tools
│   ├── governance/        # Policy engine
│   ├── reputation/        # Safe Browsing, GLEIF, ML
│   ├── db/                # Redis, PostgreSQL
│   └── egress/            # Slack, Razorpay
├── demo/
│   └── dashboard.py      # Streamlit demo
├── docs/
│   └── HACKATHON_DEMO_FLOW.md
├── deploy/
│   └── archestra.yaml
└── tests/                 # 146 tests
```

---

## 🏅 Why Vyapaar Wins

1. **Real Problem** — Every company deploying AI agents needs financial governance
2. **Clean Architecture** — Async-first, microservices-ready
3. **Production-Grade** — Circuit breakers, audit logs, Prometheus
4. **FOSS Stack** — No expensive dependencies
5. **Demo-Ready** — Beautiful dashboard shows all features in 3 minutes

---

## 📄 License

AGPL-3.0 — See [LICENSE](LICENSE)

---

## 🔗 Links

- **GitHub:** https://github.com/guglxni/vyapaar-mcp
- **Dashboard:** http://localhost:8501
- **Archestra:** https://archestra.ai

---

*Built for the 2 Fast 2 MCP Hackathon — "It's not about how fast you code, it's about control, security, and architecture."*
