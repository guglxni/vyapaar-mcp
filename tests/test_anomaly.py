"""Tests for transaction anomaly scoring with IsolationForest."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from vyapaar_mcp.reputation.anomaly import (
    AnomalyScore,
    TransactionAnomalyScorer,
    _MIN_TRAINING_SAMPLES,
)


# ================================================================
# AnomalyScore Tests
# ================================================================


class TestAnomalyScore:
    """Test AnomalyScore data class."""

    def test_to_dict(self) -> None:
        score = AnomalyScore(
            risk_score=0.85,
            raw_score=-0.35,
            is_anomalous=True,
            features={"amount_log": 5.0, "hour_of_day": 3.0, "day_of_week": 1.0, "amount_zscore": 3.2},
            model_trained=True,
            training_samples=50,
            detail="Anomaly detected: unusual amount (z=3.2)",
        )
        d = score.to_dict()
        assert d["risk_score"] == 0.85
        assert d["is_anomalous"] is True
        assert d["model_trained"] is True
        assert d["training_samples"] == 50
        assert "unusual amount" in d["detail"]

    def test_to_dict_untrained(self) -> None:
        score = AnomalyScore(
            risk_score=0.5,
            raw_score=0.0,
            is_anomalous=False,
            features={"amount_log": 4.0},
            model_trained=False,
            training_samples=3,
            detail="Insufficient data (3/10 samples). Using neutral score.",
        )
        d = score.to_dict()
        assert d["model_trained"] is False
        assert d["risk_score"] == 0.5


# ================================================================
# TransactionAnomalyScorer Tests
# ================================================================


@pytest.mark.asyncio
class TestTransactionAnomalyScorer:
    """Test the anomaly scoring engine."""

    async def test_insufficient_data_returns_neutral(self) -> None:
        """With < 10 samples, should return neutral score 0.5."""
        scorer = TransactionAnomalyScorer(redis=None)
        score = await scorer.score_transaction(
            amount=50000,
            agent_id="test-agent",
        )
        assert score.risk_score == 0.5
        assert score.is_anomalous is False
        assert score.model_trained is False
        assert "Insufficient data" in score.detail

    async def test_feature_extraction(self) -> None:
        """Test that features are correctly extracted."""
        ts = datetime(2025, 6, 15, 14, 30, 0, tzinfo=timezone.utc)  # Sunday 14:30
        features = TransactionAnomalyScorer._extract_features(50000, ts)

        assert features["amount_log"] == pytest.approx(np.log10(50000), rel=1e-3)
        assert features["hour_of_day"] == 14.0
        assert features["day_of_week"] == 6.0  # Sunday
        assert features["amount_zscore"] == 0.0  # Default before history

    async def test_feature_extraction_minimum_amount(self) -> None:
        """Test log10 doesn't fail on zero/negative amounts."""
        features = TransactionAnomalyScorer._extract_features(0, datetime.now(timezone.utc))
        assert features["amount_log"] == 0.0  # log10(1) = 0

    async def test_scoring_with_redis_history(self, fake_redis) -> None:
        """Test scoring with enough historical data in Redis."""
        scorer = TransactionAnomalyScorer(redis=fake_redis, risk_threshold=0.75)

        # Seed history with 15 "normal" transactions (₹100-₹500 range)
        # All at normal business hours
        for i in range(15):
            amount = 10000 + (i * 2000)  # 10000 to 38000 paise
            ts = datetime(2025, 6, 10 + (i % 5), 10 + (i % 8), 0, 0, tzinfo=timezone.utc)
            features = TransactionAnomalyScorer._extract_features(amount, ts)
            entry = json.dumps({
                **features,
                "amount_paise": amount,
                "timestamp": ts.isoformat(),
            })
            await fake_redis._client.lpush(f"anomaly:history:test-agent", entry)

        # Score a normal transaction
        normal_score = await scorer.score_transaction(
            amount=20000,  # ₹200 — well within normal range
            agent_id="test-agent",
            timestamp=datetime(2025, 6, 16, 12, 0, 0, tzinfo=timezone.utc),
        )
        assert normal_score.model_trained is True
        assert normal_score.training_samples >= _MIN_TRAINING_SAMPLES

    async def test_anomalous_transaction_scores_high(self, fake_redis) -> None:
        """Test that a very unusual transaction gets a higher risk score."""
        scorer = TransactionAnomalyScorer(redis=fake_redis, risk_threshold=0.75)

        # Seed with 20 consistent small transactions at business hours
        for i in range(20):
            amount = 10000 + (i * 1000)  # 10000 to 29000 paise (₹100-₹290)
            ts = datetime(2025, 6, 10 + (i % 5), 10 + (i % 4), 0, 0, tzinfo=timezone.utc)
            features = TransactionAnomalyScorer._extract_features(amount, ts)
            entry = json.dumps({
                **features,
                "amount_paise": amount,
                "timestamp": ts.isoformat(),
            })
            await fake_redis._client.lpush("anomaly:history:consistent-agent", entry)

        # Score the normal pattern
        normal = await scorer.score_transaction(
            amount=15000,
            agent_id="consistent-agent",
            timestamp=datetime(2025, 6, 16, 11, 0, 0, tzinfo=timezone.utc),
        )

        # Score a wildly different transaction (₹500,000 at 3am on Sunday)
        outlier = await scorer.score_transaction(
            amount=50000000,  # ₹500,000 — 1000x normal
            agent_id="consistent-agent",
            timestamp=datetime(2025, 6, 15, 3, 0, 0, tzinfo=timezone.utc),  # Sunday 3am
        )

        # The outlier should score higher risk than the normal one
        assert outlier.risk_score > normal.risk_score

    async def test_get_agent_profile_no_data(self) -> None:
        """Profile with no data returns empty profile."""
        scorer = TransactionAnomalyScorer(redis=None)
        profile = await scorer.get_agent_profile("unknown-agent")
        assert profile["total_transactions"] == 0
        assert profile["profile"] == "no_data"

    async def test_get_agent_profile_with_data(self, fake_redis) -> None:
        """Profile correctly summarises transaction history."""
        scorer = TransactionAnomalyScorer(redis=fake_redis)

        # Seed 5 transactions
        for i in range(5):
            amount = 10000 * (i + 1)
            ts = datetime(2025, 6, 10, 10 + i, 0, 0, tzinfo=timezone.utc)
            features = TransactionAnomalyScorer._extract_features(amount, ts)
            entry = json.dumps({
                **features,
                "amount_paise": amount,
                "timestamp": ts.isoformat(),
            })
            await fake_redis._client.lpush("anomaly:history:profile-agent", entry)

        profile = await scorer.get_agent_profile("profile-agent")
        assert profile["total_transactions"] == 5
        assert "amount_stats" in profile
        assert "time_stats" in profile
        assert profile["amount_stats"]["min_paise"] > 0

    async def test_build_feature_matrix(self) -> None:
        """Test feature matrix construction."""
        history = [
            {"amount_log": 4.0, "hour_of_day": 10.0, "day_of_week": 1.0},
            {"amount_log": 4.5, "hour_of_day": 14.0, "day_of_week": 3.0},
            {"amount_log": 4.2, "hour_of_day": 9.0, "day_of_week": 0.0},
        ]
        matrix = TransactionAnomalyScorer._build_feature_matrix(
            history, mean_amt=4.233, std_amt=0.25,
        )
        assert matrix.shape == (3, 4)
        assert matrix.dtype == np.float64

    async def test_scorer_without_redis(self) -> None:
        """Scorer should work without Redis (no history persistence)."""
        scorer = TransactionAnomalyScorer(redis=None)
        score = await scorer.score_transaction(amount=50000, agent_id="no-redis-agent")
        assert score.model_trained is False
        assert score.risk_score == 0.5
