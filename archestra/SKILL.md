---
name: archestra
description: Comprehensive guidance for the Archestra AI platform. Use when deploying agents, configuring the MCP Gateway, managing secrets, setting up observability, or implementing security guardrails like Dynamic Tools, Dual LLM, and RBAC. Includes support for Vercel AI, Pydantic AI, LangChain, and more.
---

# Archestra: Enterprise MCP Orchestrator

Archestra is an open-source platform for deploying, governing, and observing AI agents and MCP servers.

## Core Navigation

### 1. Platform & Deployment
- [**Deployment Reference**](references/deployment.md): Local Quickstart (Docker), Production (Helm), and `archestra.yaml`.
- [**Platform Access Control**](references/access-control.md): Managing RBAC, roles (Admin, Editor, Member), and custom permissions.
- [**Secrets Management**](references/secrets.md): Vault integration, rotation, and secure injection.

### 2. Security & Guardrails
- [**Advanced Security**](references/security-advanced.md): Mitigation of the **Lethal Trifecta**, **Dual LLM** patterns, and **Dynamic Tools**.
- [**Core Security**](references/security.md): Taint tracking and trusted data policies.

### 3. Agent Connectivity
- [**MCP Gateway**](references/mcp-gateway.md): Connecting agents (Claude, etc.) and managed registries.
- [**Framework Integrations**](references/frameworks.md): Securing agents built with **Vercel AI SDK**, **Pydantic AI**, **LangChain**, **N8N**, and **OpenWebUI**.

### 4. Observability
- [**Monitoring & Metrics**](references/observability.md): Prometheus/OpenTelemetry for tracking costs, tokens, and security events.

## Quick Start Commands

| Action | Command |
| :--- | :--- |
| **Start Local** | `docker run -p 3000:3000 -p 9000:9000 ... archestra/platform` |
| **Add Agent** | `claude mcp add archestra "http://localhost:9000/v1/mcp/{id}"` |
| **Enable Vault** | `export ARCHESTRA_SECRETS_MANAGER=VAULT` |

## Key Concepts
- **The Lethal Trifecta**: Data Access + Untrusted Content + Communication.
- **Dynamic Tools**: Tools that change availability based on trust.
- **Dual LLM**: An independent validator LLM for tool calls.
