"""Tests for Prometheus metrics collector.

Tests metric recording and Prometheus text format output.
"""

from __future__ import annotations

from vyapaar_mcp.models import Decision, GovernanceResult, ReasonCode
from vyapaar_mcp.observability import MetricsCollector


def make_result(
    decision: Decision = Decision.APPROVED,
    reason_code: ReasonCode = ReasonCode.POLICY_OK,
    amount: int = 50000,
    processing_ms: int = 25,
) -> GovernanceResult:
    return GovernanceResult(
        decision=decision,
        reason_code=reason_code,
        reason_detail="test",
        payout_id="pout_test_001",
        agent_id="test-agent",
        amount=amount,
        processing_ms=processing_ms,
    )


class TestMetricsCollector:
    def test_record_decision_counter(self) -> None:
        m = MetricsCollector()
        m.record_decision(make_result())
        snapshot = m.snapshot()
        assert "APPROVED|POLICY_OK" in snapshot["decisions"]
        assert snapshot["decisions"]["APPROVED|POLICY_OK"] == 1

    def test_record_multiple_decisions(self) -> None:
        m = MetricsCollector()
        m.record_decision(make_result(Decision.APPROVED))
        m.record_decision(make_result(Decision.APPROVED))
        m.record_decision(make_result(Decision.REJECTED, ReasonCode.RISK_HIGH))
        snapshot = m.snapshot()
        assert snapshot["decisions"]["APPROVED|POLICY_OK"] == 2
        assert snapshot["decisions"]["REJECTED|RISK_HIGH"] == 1

    def test_record_amounts(self) -> None:
        m = MetricsCollector()
        m.record_decision(make_result(amount=50000))
        m.record_decision(make_result(amount=30000))
        snapshot = m.snapshot()
        assert snapshot["amounts_paise"]["APPROVED"] == 80000

    def test_record_latency(self) -> None:
        m = MetricsCollector()
        m.record_decision(make_result(processing_ms=10))
        m.record_decision(make_result(processing_ms=20))
        snapshot = m.snapshot()
        assert snapshot["latency"]["count"] == 2
        assert snapshot["latency"]["sum_ms"] == 30.0
        assert snapshot["latency"]["avg_ms"] == 15.0

    def test_budget_check_recording(self) -> None:
        m = MetricsCollector()
        m.record_budget_check(ok=True)
        m.record_budget_check(ok=True)
        m.record_budget_check(ok=False)
        snapshot = m.snapshot()
        assert snapshot["budget_checks"]["ok"] == 2
        assert snapshot["budget_checks"]["exceeded"] == 1

    def test_reputation_check_recording(self) -> None:
        m = MetricsCollector()
        m.record_reputation_check(safe=True)
        m.record_reputation_check(safe=False)
        m.record_reputation_check(safe=False, error=True)
        snapshot = m.snapshot()
        assert snapshot["reputation_checks"]["safe"] == 1
        assert snapshot["reputation_checks"]["unsafe"] == 1
        assert snapshot["reputation_checks"]["error"] == 1

    def test_slack_notification_recording(self) -> None:
        m = MetricsCollector()
        m.record_slack_notification(success=True)
        m.record_slack_notification(success=False)
        snapshot = m.snapshot()
        assert snapshot["slack_notifications"]["sent"] == 1
        assert snapshot["slack_notifications"]["failed"] == 1

    def test_webhook_recording(self) -> None:
        m = MetricsCollector()
        m.record_webhook(valid_sig=True)
        m.record_webhook(valid_sig=False)
        m.record_webhook(valid_sig=True, idempotent_skip=True)
        snapshot = m.snapshot()
        assert snapshot["webhooks"]["received"] == 3
        assert snapshot["webhooks"]["invalid_sig"] == 1
        assert snapshot["webhooks"]["idempotent_skip"] == 1

    def test_poll_recording(self) -> None:
        m = MetricsCollector()
        m.record_poll(payouts_found=5)
        m.record_poll(payouts_found=0)
        snapshot = m.snapshot()
        assert snapshot["polling"]["executed"] == 2
        assert snapshot["polling"]["payouts_found"] == 5


class TestPrometheusFormat:
    def test_render_returns_string(self) -> None:
        m = MetricsCollector()
        m.record_decision(make_result())
        text = m.render()
        assert isinstance(text, str)
        assert "vyapaar_decisions_total" in text

    def test_render_format_valid(self) -> None:
        m = MetricsCollector()
        m.record_decision(make_result())
        m.record_budget_check(ok=True)
        text = m.render()
        # Check standard Prometheus format markers
        assert "# HELP" in text
        assert "# TYPE" in text
        assert "counter" in text
        assert "gauge" in text

    def test_render_includes_uptime(self) -> None:
        m = MetricsCollector()
        text = m.render()
        assert "vyapaar_uptime_seconds" in text

    def test_render_includes_labels(self) -> None:
        m = MetricsCollector()
        m.record_decision(make_result(Decision.REJECTED, ReasonCode.RISK_HIGH))
        text = m.render()
        assert 'decision="REJECTED"' in text
        assert 'reason_code="RISK_HIGH"' in text

    def test_empty_metrics_renders(self) -> None:
        m = MetricsCollector()
        text = m.render()
        # Should render without errors even with no data
        assert "vyapaar_uptime_seconds" in text
        assert len(text) > 100


class TestSnapshot:
    def test_snapshot_returns_dict(self) -> None:
        m = MetricsCollector()
        snapshot = m.snapshot()
        assert isinstance(snapshot, dict)
        assert "decisions" in snapshot
        assert "latency" in snapshot
        assert "uptime_seconds" in snapshot

    def test_snapshot_latency_zero_division(self) -> None:
        m = MetricsCollector()
        snapshot = m.snapshot()
        assert snapshot["latency"]["avg_ms"] == 0
