# Vyapaar MCP

> **The CFO for the Agentic Economy** | **2 Fast 2 MCP Hackathon** | **$10,000+ Prizes**

---

## Overview

Vyapaar MCP is a **production-grade governance layer** that sits between AI agents and the financial infrastructure. It intercepts, validates, and audits every payout request — enforcing budgets, checking vendor reputation, and keeping humans in the loop.

Built on the [Model Context Protocol](https://modelcontextprotocol.io/) (MCP), it exposes **12 governance tools** that any MCP-compatible client (Claude Desktop, Cursor, VS Code Copilot) can call.

In the race to deploy AI agents, Vyapaar ensures they don't crash the company's finances. Think of it as your AI's **CFO** — always watching, always enforcing budgets.

---

## Hackathon Alignment

| Judging Criteria | How We Score |
|-----------------|--------------|
| **Potential Impact** | Solves real problem: AI agents spending company money without oversight |
| **Creativity & Originality** | First MCP-based financial governance server with 6-layer security |
| **Learning & Growth** | Built from scratch with FOSS integrations (GLEIF, IsolationForest) |
| **Technical Implementation** | Clean architecture with Redis atomic ops, circuit breakers, async-first |
| **Aesthetics & UX** | Streamlit dashboard with real-time metrics, beautiful dark theme |
| **Best Use of Archestra** | Full Archestra integration with SSE transport, Foundry LLM |

---

## Key Features

### Security (6 Layers)

| Layer | Technology | Purpose |
|-------|------------|---------|
| 1 | Google Safe Browsing v4 | Blocks malware vendor sites |
| 2 | GLEIF Verification | Confirms vendors are real legal entities |
| 3 | Budget Enforcement | Atomic Redis limits, no overspending |
| 4 | Human Approval Gate | Slack integration for high-value txns |
| 5 | ML Anomaly Detection | IsolationForest catches unusual patterns |
| 6 | Policy Engine | Real-time domain blocking |

### Speed & Reliability

- Sub-millisecond budget checks via Redis Lua scripts
- Circuit breakers prevent cascade failures
- Async-first Python architecture
- Prometheus metrics built-in

---

## Architecture

```
MCP Client          Vyapaar MCP              Razorpay X
(Claude,       -->  (FastMCP)         -->   (Banking)
 Cursor)            |
                     | Governance Engine    PostgreSQL
                     |                      (Audit Logs)
                     |
                     | Reputation           Redis
                     | (SB, GLEIF)          (Budgets)
                     |
                     | ML Anomaly           Slack
                     | (IsolationForest)    (Human Loop)
```

---

## Demo Flow (3 Minutes)

| Scenario | Agent | Vendor | Amount | Result |
|----------|-------|--------|--------|--------|
| 1: Legitimate | marketing-bot | Google LLC | ₹2,500 | APPROVED |
| 2: Malware | marketing-bot | sketchy-vendor.xyz | ₹15,000 | BLOCKED |
| 3: Budget | marketing-bot | any | ₹8,000 | REJECTED |
| 4: Human | marketing-bot | AWS | ₹8,000 | HELD → Slack |
| 5: ML Anomaly | night-bot | unknown.io | ₹25,000 | FLAGGED |
| 6: Policy | any | .xyz domain | any | BLOCKED |

---

## MCP Tools (12 Total)

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

## Quick Start

```bash
# Clone and setup
git clone https://github.com/guglxni/vyapaar-mcp.git
cd vyapaar-mcp

# Start infrastructure
docker compose up -d redis postgres

# Configure
cp .env.example .env
# Add your Razorpay, Google Safe Browsing, Slack keys

# Run dashboard
streamlit run demo/dashboard.py
```

---

## Archestra Integration

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

## Project Structure

```
vyapaar-mcp/
├── src/vyapaar_mcp/      # Core application
│   ├── server.py           # FastMCP + 12 tools
│   ├── governance/         # Policy engine
│   ├── reputation/        # Safe Browsing, GLEIF, ML
│   ├── db/                # Redis, PostgreSQL
│   └── egress/            # Slack, Razorpay
├── demo/
│   └── dashboard.py       # Streamlit dashboard
├── docs/
│   ├── HACKATHON_README.md
│   └── HACKATHON_DEMO_FLOW.md
├── deploy/
│   └── archestra.yaml
└── tests/                 # 146 tests
```

---

## Why Vyapaar Wins

1. **Real Problem** — Every company deploying AI agents needs financial governance
2. **Clean Architecture** — Async-first, microservices-ready
3. **Production-Grade** — Circuit breakers, audit logs, Prometheus
4. **FOSS Stack** — No expensive dependencies
5. **Demo-Ready** — Beautiful dashboard shows all features in 3 minutes
6. **Archestra-Ready** — Full integration with SSE transport

---

## Features

| Category | Capability |
|----------|------------|
| **Governance** | Per-agent budgets (daily + per-txn), domain allow/block lists, multi-step approval |
| **Reputation** | Google Safe Browsing v4, GLEIF legal entity verification, ML anomaly detection |
| **Human-in-the-Loop** | Slack interactive buttons for HELD payouts, ntfy push fallback |
| **Observability** | Prometheus metrics, structured audit logs, circuit breaker dashboards |
| **Resilience** | Circuit breakers, sliding-window rate limiting, atomic Redis budget ops |
| **Ingress** | Razorpay webhooks (HMAC-SHA256) + API polling via Go sidecar bridge |

---

## Testing

```bash
# Full test suite
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ --cov=vyapaar_mcp --cov-report=term-missing
```

---

## Configuration

All configuration is via environment variables with the `VYAPAAR_` prefix. See [.env.example](.env.example) for the full list.

| Variable | Required | Description |
|----------|----------|-------------|
| `VYAPAAR_RAZORPAY_KEY_ID` | Yes | Razorpay API Key ID |
| `VYAPAAR_RAZORPAY_KEY_SECRET` | Yes | Razorpay API Key Secret |
| `VYAPAAR_GOOGLE_SAFE_BROWSING_KEY` | Yes | Google Safe Browsing API key |
| `VYAPAAR_POSTGRES_DSN` | Yes | PostgreSQL connection string |
| `VYAPAAR_REDIS_URL` | No | Redis URL (default: `redis://localhost:6379/0`) |
| `VYAPAAR_SLACK_BOT_TOKEN` | No | Slack bot token for approval notifications |
| `VYAPAAR_NTFY_TOPIC` | No | ntfy topic for push notification fallback |

---

## Documentation

- [SPEC.md](SPEC.md) — Full architecture & governance specification
- [docs/SLACK_SETUP.md](docs/SLACK_SETUP.md) — Slack bot configuration
- [docs/TUNNEL_SETUP.md](docs/TUNNEL_SETUP.md) — Webhook tunnel setup
- [docs/FOSS_BRAINSTORM.md](docs/FOSS_BRAINSTORM.md) — FOSS integration notes
- [docs/HACKATHON_README.md](docs/HACKATHON_README.md) — Hackathon submission
- [CONTRIBUTING.md](CONTRIBUTING.md) — Contributor guidelines

---

## License

[AGPL-3.0](LICENSE) — see [LICENSE](LICENSE) for details.

---

## Links

- **GitHub:** https://github.com/guglxni/vyapaar-mcp
- **Dashboard:** http://localhost:8501
- **Archestra:** https://archestra.ai
- **MCP Protocol:** https://modelcontextprotocol.io

---

*Built for the 2 Fast 2 MCP Hackathon — "It's not about how fast you code, it's about control, security, and architecture."*
