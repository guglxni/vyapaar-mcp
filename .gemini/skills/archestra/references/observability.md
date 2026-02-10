# Archestra Observability & Monitoring

## Tech Stack
- **Metrics**: Prometheus
- **Tracing**: OpenTelemetry (OTLP)

## Monitoring System Health
Archestra exposes metrics on system performance, HTTP request counts, and error rates.

## LLM Performance Tracking
Detailed spans are generated for every LLM request, including:
- **Provider & Model**: (e.g., Anthropic Claude 3.5 Sonnet)
- **Token Usage**: Input/Output counts.
- **Latency**: Time to first token and total duration.
- **Cost**: Estimated cost based on model pricing.
- **Spans**: Recursive spans for tool calls triggered by the LLM.

## Security Observability
Metrics and traces capture:
- **Blocked Tool Calls**: When Dynamic Tools or Dual LLM blocks an action.
- **Policy Violations**: When untrusted data triggers a security restriction.
- **Taint Tracking**: Visualizing how untrusted data flows through an agent's context.
