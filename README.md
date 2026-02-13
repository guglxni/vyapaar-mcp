# Vyapaar MCP

> **The CFO for the Agentic Economy**

Vyapaar MCP is a governance layer that sits between AI agents and the [Razorpay X](https://razorpay.com/x/) banking platform. It intercepts, validates, and audits every payout request — enforcing budgets, checking vendor reputation, and keeping humans in the loop.

Built on the [Model Context Protocol](https://modelcontextprotocol.io/) (MCP), it exposes 12 governance tools that any MCP-compatible client (Claude Desktop, Cursor, VS Code Copilot) can call.

## Features

| Category | Capability |
|---|---|
| **Governance** | Per-agent budgets (daily + per-txn), domain allow/block lists, multi-step approval |
| **Reputation** | Google Safe Browsing v4, GLEIF legal entity verification, ML anomaly detection |
| **Human-in-the-Loop** | Slack interactive buttons for HELD payouts, ntfy push fallback |
| **Observability** | Prometheus metrics, structured audit logs, circuit breaker dashboards |
| **Resilience** | Circuit breakers, sliding-window rate limiting, atomic Redis budget ops |
| **Ingress** | Razorpay webhooks (HMAC-SHA256) + API polling via Go sidecar bridge |

## Quick Start

### Prerequisites

- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- Go 1.25+ (sidecar build)
- Docker (Redis & PostgreSQL)
- Razorpay X Sandbox credentials

### Setup

```bash
# Install dependencies
uv sync

# Build the Go sidecar bridge
cd vendor/razorpay-mcp-server
go build -o ../../bin/razorpay-mcp-server ./cmd/razorpay-mcp-server
cd ../..

# Start infrastructure
docker compose up -d redis postgres

# Configure environment
cp .env.example .env
# → Edit .env with your Razorpay, Google Safe Browsing, and Slack keys

# Seed demo policies
uv run scripts/seed_policies.py

# Run the server
uv run vyapaar-mcp
```

## Architecture

Vyapaar uses a **Hybrid Architecture** — polling for local development, webhooks for production:

```
┌─────────────┐     ┌────────────────────┐     ┌──────────────┐
│  MCP Client │────▶│   Vyapaar MCP       │────▶│  Razorpay X  │
│  (Claude,   │     │   (Python/FastMCP)  │     │  (Banking)   │
│   Cursor)   │     │                     │     └──────────────┘
└─────────────┘     │  ┌───────────────┐  │
                    │  │ Governance    │  │     ┌──────────────┐
                    │  │ Engine        │  │────▶│  PostgreSQL   │
                    │  └───────────────┘  │     │  (Audit Logs) │
                    │  ┌───────────────┐  │     └──────────────┘
                    │  │ Go Sidecar    │  │
                    │  │ (RazorpayMCP) │  │     ┌──────────────┐
                    │  └───────────────┘  │────▶│  Redis        │
                    └────────────────────┘     │  (Budgets)    │
                                               └──────────────┘
```

See [SPEC.md](SPEC.md) for the full architecture specification.

## Project Structure

```
vyapaar-mcp/
├── src/vyapaar_mcp/        # Core application
│   ├── server.py           # FastMCP server & 12 tool definitions
│   ├── config.py           # Pydantic settings (env-driven)
│   ├── models.py           # Domain models
│   ├── governance/         # Policy evaluation engine
│   ├── db/                 # Redis (budgets) & PostgreSQL (audit)
│   ├── ingress/            # Webhook handler & polling bridge
│   ├── egress/             # Razorpay actions, Slack, ntfy
│   ├── reputation/         # Safe Browsing, GLEIF, anomaly ML
│   ├── observability/      # Prometheus metrics
│   ├── resilience/         # Circuit breaker & rate limiter
│   └── audit/              # Structured audit logging
├── tests/                  # 146 tests (pytest + pytest-asyncio)
├── scripts/                # Operational utilities
├── demo/                   # CLI demo & Streamlit dashboard
├── docs/                   # Documentation
├── deploy/                 # Deployment configs (Archestra, ngrok)
└── vendor/                 # Razorpay MCP Go server (gitignored)
```

## Testing

```bash
# Full test suite
uv run pytest tests/ -v

# With coverage
uv run pytest tests/ --cov=vyapaar_mcp --cov-report=term-missing
```

## MCP Tools

| # | Tool | Description |
|---|------|-------------|
| 1 | `handle_razorpay_webhook` | Process Razorpay webhook with full governance |
| 2 | `poll_razorpay_payouts` | Poll API for queued payouts (no webhook needed) |
| 3 | `check_vendor_reputation` | Google Safe Browsing URL check |
| 4 | `verify_vendor_entity` | GLEIF legal entity verification |
| 5 | `score_transaction_risk` | ML anomaly detection (IsolationForest) |
| 6 | `get_agent_risk_profile` | Agent transaction pattern analysis |
| 7 | `get_agent_budget` | Current daily spend & remaining budget |
| 8 | `set_agent_policy` | Create/update agent spending policies |
| 9 | `get_audit_log` | Retrieve filtered audit trail |
| 10 | `handle_slack_action` | Process Slack approve/reject callbacks |
| 11 | `health_check` | Service health & circuit breaker status |
| 12 | `get_metrics` | Prometheus-compatible metrics |

## Configuration

All configuration is via environment variables with the `VYAPAAR_` prefix. See [.env.example](.env.example) for the full list.

Key variables:

| Variable | Required | Description |
|---|---|---|
| `VYAPAAR_RAZORPAY_KEY_ID` | Yes | Razorpay API Key ID |
| `VYAPAAR_RAZORPAY_KEY_SECRET` | Yes | Razorpay API Key Secret |
| `VYAPAAR_GOOGLE_SAFE_BROWSING_KEY` | Yes | Google Safe Browsing API key |
| `VYAPAAR_POSTGRES_DSN` | Yes | PostgreSQL connection string |
| `VYAPAAR_REDIS_URL` | No | Redis URL (default: `redis://localhost:6379/0`) |
| `VYAPAAR_SLACK_BOT_TOKEN` | No | Slack bot token for approval notifications |
| `VYAPAAR_NTFY_TOPIC` | No | ntfy topic for push notification fallback |

## Documentation

- [SPEC.md](SPEC.md) — Full architecture & governance specification
- [docs/SLACK_SETUP.md](docs/SLACK_SETUP.md) — Slack bot configuration
- [docs/TUNNEL_SETUP.md](docs/TUNNEL_SETUP.md) — Webhook tunnel setup
- [docs/FOSS_BRAINSTORM.md](docs/FOSS_BRAINSTORM.md) — FOSS integration notes
- [CONTRIBUTING.md](CONTRIBUTING.md) — Contributor guidelines

## License

[AGPL-3.0](LICENSE) — see [LICENSE](LICENSE) for details.
