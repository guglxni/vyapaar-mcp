---
name: archestra
description: Comprehensive guidance for the Archestra AI platform. Use when deploying agents, configuring the MCP Gateway, managing secrets via Vault, setting up observability with OpenTelemetry, or implementing security guardrails like Dynamic Tools and Dual LLM.
---

# Archestra: Enterprise MCP Orchestrator

Archestra is an open-source platform for deploying, governing, and observing AI agents and MCP servers. It provides a "financial firewall" and security layer for the agentic economy.

## Core Workflows

### 1. Platform Deployment
Choose between local development or production-scale Kubernetes.
- **Local (Docker)**: Use the one-liner in [deployment.md](references/deployment.md).
- **Production (Helm)**: Follow infrastructure requirements in [deployment.md](references/deployment.md).

### 2. Securing Agents
Mitigate the "Lethal Trifecta" (Private Data + Untrusted Content + External Comms).
- **Dynamic Tools**: Restrict capabilities when untrusted data enters context. See [security.md](references/security.md).
- **Dual LLM**: Add an independent security validation layer. See [security.md](references/security.md).

### 3. MCP Connectivity & Secrets
Centralize your agent infrastructure.
- **Gateway Setup**: Connect Claude or other clients to managed agents. See [mcp-gateway.md](references/mcp-gateway.md).
- **Vault Integration**: Securely store and rotate API keys. See [secrets.md](references/secrets.md).

### 4. Observability
Monitor costs, tokens, and security events.
- **Traces & Metrics**: Track LLM spans and token consumption. See [observability.md](references/observability.md).

## Quick Reference

| Task | Key Resource |
| :--- | :--- |
| **Run Local** | `docker run ... archestra/platform` |
| **Default Ports** | 3000 (UI), 9000 (Gateway) |
| **Security Pattern** | Dual LLM & Dynamic Tools |
| **Metrics** | Prometheus & OpenTelemetry |
| **Auth** | Bearer Tokens / Headers |

## API & Manifests
For detailed API references and `archestra.yaml` configuration, see [deployment.md](references/deployment.md).