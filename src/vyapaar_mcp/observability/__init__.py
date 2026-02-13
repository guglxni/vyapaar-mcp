"""Prometheus-compatible metrics for Vyapaar MCP.

Exposes governance metrics in Prometheus text format at /metrics.
Designed for Archestra observability integration.

Per SPEC §19 Nice-to-Have: "Prometheus-compatible /metrics endpoint."

Metrics exposed:
  vyapaar_decisions_total{decision,reason_code} — Counter of governance decisions
  vyapaar_payout_amount_paise_total{decision} — Total payout amounts processed
  vyapaar_decision_latency_ms — Histogram of decision processing time
  vyapaar_budget_checks_total{result} — Counter of budget check results
  vyapaar_reputation_checks_total{result} — Counter of reputation checks
  vyapaar_uptime_seconds — Server uptime gauge
"""

from __future__ import annotations

import time
import threading
from typing import Any

from vyapaar_mcp.models import Decision, GovernanceResult, ReasonCode


class MetricsCollector:
    """Thread-safe Prometheus metrics collector.

    Uses simple counters and gauges — no external dependency needed.
    Output format: Prometheus text exposition format (v0.0.4).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._start_time = time.time()

        # Counters
        self._decisions: dict[str, int] = {}
        self._amounts: dict[str, int] = {}
        self._budget_checks: dict[str, int] = {"ok": 0, "exceeded": 0}
        self._reputation_checks: dict[str, int] = {"safe": 0, "unsafe": 0, "error": 0}
        self._slack_notifications: dict[str, int] = {"sent": 0, "failed": 0}
        self._rate_limit_checks: dict[str, int] = {"allowed": 0, "blocked": 0}

        # Histogram (simplified — just track sum and count per bucket)
        self._latency_sum: float = 0.0
        self._latency_count: int = 0
        self._latency_buckets: dict[str, int] = {
            "5": 0, "10": 0, "25": 0, "50": 0, "100": 0,
            "250": 0, "500": 0, "1000": 0, "+Inf": 0,
        }

        # Webhook / polling counters
        self._webhooks_received: int = 0
        self._webhooks_invalid_sig: int = 0
        self._webhooks_idempotent_skip: int = 0
        self._polls_executed: int = 0
        self._polls_payouts_found: int = 0

        # FOSS integration counters
        self._gleif_checks: dict[str, int] = {"verified": 0, "unverified": 0, "error": 0}
        self._anomaly_checks: dict[str, int] = {"normal": 0, "anomalous": 0, "insufficient_data": 0}
        self._ntfy_notifications: dict[str, int] = {"sent": 0, "failed": 0}

    # ================================================================
    # Record Methods
    # ================================================================

    def record_decision(self, result: GovernanceResult) -> None:
        """Record a governance decision."""
        with self._lock:
            key = f"{result.decision.value}|{result.reason_code.value}"
            self._decisions[key] = self._decisions.get(key, 0) + 1

            amount_key = result.decision.value
            self._amounts[amount_key] = self._amounts.get(amount_key, 0) + result.amount

            if result.processing_ms is not None:
                self._latency_sum += result.processing_ms
                self._latency_count += 1
                ms = result.processing_ms
                for bucket in ["5", "10", "25", "50", "100", "250", "500", "1000"]:
                    if ms <= int(bucket):
                        self._latency_buckets[bucket] += 1
                        break  # only increment smallest matching bucket
                self._latency_buckets["+Inf"] += 1

    def record_budget_check(self, ok: bool) -> None:
        """Record a budget check result."""
        with self._lock:
            key = "ok" if ok else "exceeded"
            self._budget_checks[key] += 1

    def record_reputation_check(self, safe: bool, error: bool = False) -> None:
        """Record a reputation check result."""
        with self._lock:
            if error:
                self._reputation_checks["error"] += 1
            elif safe:
                self._reputation_checks["safe"] += 1
            else:
                self._reputation_checks["unsafe"] += 1

    def record_slack_notification(self, success: bool) -> None:
        """Record a Slack notification attempt."""
        with self._lock:
            key = "sent" if success else "failed"
            self._slack_notifications[key] += 1

    def record_rate_limit_check(self, allowed: bool) -> None:
        """Record a rate limit check result."""
        with self._lock:
            key = "allowed" if allowed else "blocked"
            self._rate_limit_checks[key] += 1

    def record_webhook(self, valid_sig: bool = True, idempotent_skip: bool = False) -> None:
        """Record a webhook event."""
        with self._lock:
            self._webhooks_received += 1
            if not valid_sig:
                self._webhooks_invalid_sig += 1
            if idempotent_skip:
                self._webhooks_idempotent_skip += 1

    def record_poll(self, payouts_found: int = 0) -> None:
        """Record a poll execution."""
        with self._lock:
            self._polls_executed += 1
            self._polls_payouts_found += payouts_found

    def record_gleif_check(self, verified: bool, error: bool = False) -> None:
        """Record a GLEIF vendor verification check."""
        with self._lock:
            if error:
                self._gleif_checks["error"] += 1
            elif verified:
                self._gleif_checks["verified"] += 1
            else:
                self._gleif_checks["unverified"] += 1

    def record_anomaly_check(self, anomalous: bool, model_trained: bool = True) -> None:
        """Record a transaction anomaly scoring check."""
        with self._lock:
            if not model_trained:
                self._anomaly_checks["insufficient_data"] += 1
            elif anomalous:
                self._anomaly_checks["anomalous"] += 1
            else:
                self._anomaly_checks["normal"] += 1

    def record_ntfy_notification(self, success: bool) -> None:
        """Record an ntfy notification attempt."""
        with self._lock:
            key = "sent" if success else "failed"
            self._ntfy_notifications[key] += 1

    # ================================================================
    # Prometheus Text Format Output
    # ================================================================

    def render(self) -> str:
        """Render all metrics in Prometheus text exposition format."""
        with self._lock:
            lines: list[str] = []

            # --- Decisions ---
            lines.append("# HELP vyapaar_decisions_total Total governance decisions")
            lines.append("# TYPE vyapaar_decisions_total counter")
            for key, count in sorted(self._decisions.items()):
                decision, reason = key.split("|", 1)
                lines.append(
                    f'vyapaar_decisions_total{{decision="{decision}",reason_code="{reason}"}} {count}'
                )

            # --- Amounts ---
            lines.append("# HELP vyapaar_payout_amount_paise_total Total payout amounts in paise")
            lines.append("# TYPE vyapaar_payout_amount_paise_total counter")
            for decision, total in sorted(self._amounts.items()):
                lines.append(
                    f'vyapaar_payout_amount_paise_total{{decision="{decision}"}} {total}'
                )

            # --- Latency ---
            lines.append("# HELP vyapaar_decision_latency_ms Decision processing latency in ms")
            lines.append("# TYPE vyapaar_decision_latency_ms histogram")
            cumulative = 0
            for bucket, count in sorted(
                self._latency_buckets.items(),
                key=lambda x: float("inf") if x[0] == "+Inf" else float(x[0]),
            ):
                cumulative += count if bucket != "+Inf" else 0
                le = bucket if bucket == "+Inf" else bucket
                lines.append(f'vyapaar_decision_latency_ms_bucket{{le="{le}"}} {cumulative if bucket != "+Inf" else self._latency_count}')
            lines.append(f"vyapaar_decision_latency_ms_sum {self._latency_sum}")
            lines.append(f"vyapaar_decision_latency_ms_count {self._latency_count}")

            # --- Budget checks ---
            lines.append("# HELP vyapaar_budget_checks_total Budget check results")
            lines.append("# TYPE vyapaar_budget_checks_total counter")
            for result, count in sorted(self._budget_checks.items()):
                lines.append(f'vyapaar_budget_checks_total{{result="{result}"}} {count}')

            # --- Reputation checks ---
            lines.append("# HELP vyapaar_reputation_checks_total Reputation check results")
            lines.append("# TYPE vyapaar_reputation_checks_total counter")
            for result, count in sorted(self._reputation_checks.items()):
                lines.append(f'vyapaar_reputation_checks_total{{result="{result}"}} {count}')

            # --- Slack ---
            lines.append("# HELP vyapaar_slack_notifications_total Slack notification outcomes")
            lines.append("# TYPE vyapaar_slack_notifications_total counter")
            for result, count in sorted(self._slack_notifications.items()):
                lines.append(f'vyapaar_slack_notifications_total{{result="{result}"}} {count}')

            # --- Rate limiting ---
            lines.append("# HELP vyapaar_rate_limit_checks_total Rate limit check results")
            lines.append("# TYPE vyapaar_rate_limit_checks_total counter")
            for result, count in sorted(self._rate_limit_checks.items()):
                lines.append(f'vyapaar_rate_limit_checks_total{{result="{result}"}} {count}')

            # --- Webhooks ---
            lines.append("# HELP vyapaar_webhooks_received_total Total webhooks received")
            lines.append("# TYPE vyapaar_webhooks_received_total counter")
            lines.append(f"vyapaar_webhooks_received_total {self._webhooks_received}")

            lines.append("# HELP vyapaar_webhooks_invalid_sig_total Webhooks with invalid signature")
            lines.append("# TYPE vyapaar_webhooks_invalid_sig_total counter")
            lines.append(f"vyapaar_webhooks_invalid_sig_total {self._webhooks_invalid_sig}")

            lines.append("# HELP vyapaar_webhooks_idempotent_skip_total Webhooks skipped (idempotent)")
            lines.append("# TYPE vyapaar_webhooks_idempotent_skip_total counter")
            lines.append(f"vyapaar_webhooks_idempotent_skip_total {self._webhooks_idempotent_skip}")

            # --- Polling ---
            lines.append("# HELP vyapaar_polls_executed_total Total poll cycles executed")
            lines.append("# TYPE vyapaar_polls_executed_total counter")
            lines.append(f"vyapaar_polls_executed_total {self._polls_executed}")

            lines.append("# HELP vyapaar_polls_payouts_found_total Total payouts found via polling")
            lines.append("# TYPE vyapaar_polls_payouts_found_total counter")
            lines.append(f"vyapaar_polls_payouts_found_total {self._polls_payouts_found}")

            # --- GLEIF checks ---
            lines.append("# HELP vyapaar_gleif_checks_total GLEIF vendor verification results")
            lines.append("# TYPE vyapaar_gleif_checks_total counter")
            for result, count in sorted(self._gleif_checks.items()):
                lines.append(f'vyapaar_gleif_checks_total{{result="{result}"}} {count}')

            # --- Anomaly checks ---
            lines.append("# HELP vyapaar_anomaly_checks_total Transaction anomaly scoring results")
            lines.append("# TYPE vyapaar_anomaly_checks_total counter")
            for result, count in sorted(self._anomaly_checks.items()):
                lines.append(f'vyapaar_anomaly_checks_total{{result="{result}"}} {count}')

            # --- ntfy ---
            lines.append("# HELP vyapaar_ntfy_notifications_total ntfy notification outcomes")
            lines.append("# TYPE vyapaar_ntfy_notifications_total counter")
            for result, count in sorted(self._ntfy_notifications.items()):
                lines.append(f'vyapaar_ntfy_notifications_total{{result="{result}"}} {count}')

            # --- Uptime ---
            lines.append("# HELP vyapaar_uptime_seconds Server uptime in seconds")
            lines.append("# TYPE vyapaar_uptime_seconds gauge")
            lines.append(f"vyapaar_uptime_seconds {int(time.time() - self._start_time)}")

            return "\n".join(lines) + "\n"

    def snapshot(self) -> dict[str, Any]:
        """Return metrics as a dict (for JSON API)."""
        with self._lock:
            return {
                "decisions": dict(self._decisions),
                "amounts_paise": dict(self._amounts),
                "latency": {
                    "sum_ms": self._latency_sum,
                    "count": self._latency_count,
                    "avg_ms": round(self._latency_sum / self._latency_count, 1) if self._latency_count else 0,
                },
                "budget_checks": dict(self._budget_checks),
                "reputation_checks": dict(self._reputation_checks),
                "slack_notifications": dict(self._slack_notifications),
                "rate_limit_checks": dict(self._rate_limit_checks),
                "webhooks": {
                    "received": self._webhooks_received,
                    "invalid_sig": self._webhooks_invalid_sig,
                    "idempotent_skip": self._webhooks_idempotent_skip,
                },
                "polling": {
                    "executed": self._polls_executed,
                    "payouts_found": self._polls_payouts_found,
                },
                "gleif_checks": dict(self._gleif_checks),
                "anomaly_checks": dict(self._anomaly_checks),
                "ntfy_notifications": dict(self._ntfy_notifications),
                "uptime_seconds": int(time.time() - self._start_time),
            }


# Global singleton
metrics = MetricsCollector()
