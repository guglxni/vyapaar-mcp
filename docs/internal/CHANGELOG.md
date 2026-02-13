# Changelog (Internal Prototype Record)

> This is an internal development log. Vyapaar MCP has not been publicly
> released or versioned. These entries track prototype development milestones.

---

## 2026-02-14 — Code Review Fixes & Repo Reorganization

- Removed all public version strings from codebase
- Applied 12 fixes from comprehensive code review (security, correctness, performance)
- Reorganized repository into enterprise-grade structure
- Added LICENSE, CONTRIBUTING.md
- Moved checkpoint/review docs to `docs/internal/`

## 2026-02-13 — FOSS Code Review

- Installed 5 FOSS review skills (code-review-excellence, security-auditor, etc.)
- Produced comprehensive code review with 29 findings (4 Critical, 11 High, 10 Medium, 4 Low)
- 146/146 tests passing

## 2026-02-12 — FOSS Integrations

- GLEIF vendor entity verification (free API, no key required)
- Transaction anomaly detection (scikit-learn IsolationForest)
- ntfy push notification fallback for Slack
- 38 new tests added → 146/146 total

## 2026-02-11 — Slack, Polling, Metrics, Demo

- Slack human-in-the-loop approval with interactive buttons
- Auto-polling background task with configurable interval
- Prometheus-compatible metrics (decisions, latency, budget, reputation)
- CLI demo script and Streamlit dashboard
- Circuit breaker and rate limiting
- 100/100 tests passing

## 2026-02-11 — Hybrid Architecture

- Go sidecar bridge for Razorpay MCP binary
- API polling mode (no ngrok required for local dev)
- Webhook mode for production
- 52/52 tests passing

## 2026-02-10 — Initial Prototype

- FastMCP server with governance engine
- Redis atomic budget tracking (Lua scripts)
- PostgreSQL audit logging with asyncpg
- Google Safe Browsing v4 vendor reputation
- Razorpay X sandbox integration (approve/reject payouts)
- Pydantic V2 models, async throughout
