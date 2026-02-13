"""Transaction anomaly scoring using scikit-learn IsolationForest.

Detects anomalous payout patterns by learning from historical transaction
features: amount, hour of day, day of week, and per-agent frequency.

Reference: .reference/scikit-learn/sklearn/ensemble/_iforest.py
Example:   .reference/scikit-learn/examples/ensemble/plot_isolation_forest.py

Key design choices:
  • IsolationForest with contamination='auto' (original paper threshold)
  • score_samples() returns raw anomaly scores (lower = more anomalous)
  • Normalised to 0.0–1.0 risk score (1.0 = most anomalous)
  • Redis-backed feature history for incremental learning
  • Async-safe: sklearn operations run in thread executor
  • Graceful degradation: returns neutral score 0.5 when model is untrained
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

import numpy as np

from vyapaar_mcp.db.redis_client import RedisClient

logger = logging.getLogger("vyapaar_mcp.reputation.anomaly")

# Minimum samples needed before the model starts scoring
_MIN_TRAINING_SAMPLES = 10

# Maximum samples to keep in Redis history
_MAX_HISTORY_SIZE = 1000

# Redis key TTL for transaction history (7 days)
_HISTORY_TTL = 604800

# Default risk threshold — scores above this are flagged
DEFAULT_RISK_THRESHOLD = 0.75


class AnomalyScore:
    """Result of anomaly scoring for a transaction."""

    def __init__(
        self,
        risk_score: float,
        raw_score: float,
        is_anomalous: bool,
        features: dict[str, float],
        model_trained: bool,
        training_samples: int,
        detail: str = "",
    ) -> None:
        self.risk_score = risk_score        # 0.0 (normal) to 1.0 (anomalous)
        self.raw_score = raw_score           # Raw IsolationForest score
        self.is_anomalous = is_anomalous     # True if risk_score > threshold
        self.features = features             # Feature vector used
        self.model_trained = model_trained   # Whether model had enough data
        self.training_samples = training_samples
        self.detail = detail

    def to_dict(self) -> dict[str, Any]:
        return {
            "risk_score": round(self.risk_score, 4),
            "raw_score": round(self.raw_score, 4),
            "is_anomalous": self.is_anomalous,
            "features": {k: round(v, 4) for k, v in self.features.items()},
            "model_trained": self.model_trained,
            "training_samples": self.training_samples,
            "detail": self.detail,
        }


class TransactionAnomalyScorer:
    """Anomaly detection for financial transactions using IsolationForest.

    Learns normal transaction patterns per agent and flags outliers.

    Features used:
      1. amount_log      — log10(amount_paise) to handle wide range
      2. hour_of_day     — 0-23, captures time-of-day patterns
      3. day_of_week     — 0-6 (Monday=0), captures day patterns
      4. amount_zscore   — how many std devs from agent's mean amount

    Usage:
        scorer = TransactionAnomalyScorer(redis=redis_client)
        score = await scorer.score_transaction(
            amount=5000000,  # ₹50,000
            agent_id="agent-001",
        )
        if score.is_anomalous:
            print(f"ANOMALY: risk={score.risk_score}")
    """

    def __init__(
        self,
        redis: RedisClient | None = None,
        risk_threshold: float = DEFAULT_RISK_THRESHOLD,
        contamination: float | str = "auto",
        n_estimators: int = 100,
        random_state: int = 42,
    ) -> None:
        self._redis = redis
        self._risk_threshold = risk_threshold
        self._contamination = contamination
        self._n_estimators = n_estimators
        self._random_state = random_state

        # Lazy import — only needed when scoring
        self._IsolationForest: type | None = None
        self._models: dict[str, Any] = {}  # per-agent trained models

    def _get_isolation_forest(self) -> type:
        """Lazy-load sklearn to avoid import overhead at startup."""
        if self._IsolationForest is None:
            from sklearn.ensemble import IsolationForest
            self._IsolationForest = IsolationForest
        return self._IsolationForest

    # ----------------------------------------------------------------
    # Public API
    # ----------------------------------------------------------------

    async def score_transaction(
        self,
        amount: int,
        agent_id: str,
        timestamp: datetime | None = None,
    ) -> AnomalyScore:
        """Score a transaction for anomaly risk.

        Args:
            amount: Transaction amount in paise.
            agent_id: The agent initiating the transaction.
            timestamp: When the transaction occurred (defaults to now).

        Returns:
            AnomalyScore with risk assessment.
        """
        ts = timestamp or datetime.now(timezone.utc)
        features = self._extract_features(amount, ts)

        # Get historical data for this agent BEFORE recording current transaction
        # to avoid polluting training data with placeholder z-score.
        history = await self._get_history(agent_id)

        if len(history) < _MIN_TRAINING_SAMPLES:
            # Record transaction even with insufficient data (builds history)
            await self._record_transaction(agent_id, amount, features, ts)
            return AnomalyScore(
                risk_score=0.5,
                raw_score=0.0,
                is_anomalous=False,
                features=features,
                model_trained=False,
                training_samples=len(history),
                detail=f"Insufficient data ({len(history)}/{_MIN_TRAINING_SAMPLES} samples). "
                       "Using neutral score.",
            )

        # Compute z-score feature using history
        amounts = [h["amount_log"] for h in history]
        mean_amt = np.mean(amounts)
        std_amt = np.std(amounts) if len(amounts) > 1 else 1.0
        features["amount_zscore"] = (features["amount_log"] - mean_amt) / max(std_amt, 0.001)

        # Record transaction AFTER computing z-score so it includes the real value
        await self._record_transaction(agent_id, amount, features, ts)

        # Also add z-scores to history for training
        history_matrix = self._build_feature_matrix(history, mean_amt, std_amt)

        # Train model and score — run in executor to avoid blocking event loop
        try:
            loop = asyncio.get_running_loop()
            score_result = await loop.run_in_executor(
                None,
                self._fit_and_score,
                agent_id,
                history_matrix,
                features,
            )
            return score_result
        except Exception as e:
            logger.error("Anomaly scoring failed for agent %s: %s", agent_id, e)
            return AnomalyScore(
                risk_score=0.5,
                raw_score=0.0,
                is_anomalous=False,
                features=features,
                model_trained=False,
                training_samples=len(history),
                detail=f"Scoring error: {e}",
            )

    async def get_agent_profile(self, agent_id: str) -> dict[str, Any]:
        """Get the transaction profile for an agent.

        Returns statistics about the agent's historical transactions.
        """
        history = await self._get_history(agent_id)
        if not history:
            return {
                "agent_id": agent_id,
                "total_transactions": 0,
                "profile": "no_data",
            }

        amounts_paise = [10 ** h["amount_log"] for h in history]
        hours = [int(h["hour_of_day"]) for h in history]

        return {
            "agent_id": agent_id,
            "total_transactions": len(history),
            "amount_stats": {
                "mean_paise": int(np.mean(amounts_paise)),
                "median_paise": int(np.median(amounts_paise)),
                "min_paise": int(np.min(amounts_paise)),
                "max_paise": int(np.max(amounts_paise)),
                "std_paise": int(np.std(amounts_paise)),
            },
            "time_stats": {
                "most_active_hour": int(np.argmax(np.bincount(hours, minlength=24))),
                "hour_distribution": {str(h): int(c) for h, c in enumerate(np.bincount(hours, minlength=24)) if c > 0},
            },
        }

    # ----------------------------------------------------------------
    # Private: Feature extraction
    # ----------------------------------------------------------------

    @staticmethod
    def _extract_features(amount: int, ts: datetime) -> dict[str, float]:
        """Extract feature vector from a transaction."""
        return {
            "amount_log": float(np.log10(max(amount, 1))),
            "hour_of_day": float(ts.hour),
            "day_of_week": float(ts.weekday()),
            "amount_zscore": 0.0,  # Computed later with history
        }

    @staticmethod
    def _build_feature_matrix(
        history: list[dict[str, float]],
        mean_amt: float,
        std_amt: float,
    ) -> np.ndarray:
        """Build feature matrix from history, including z-score computation."""
        rows = []
        for h in history:
            zscore = (h["amount_log"] - mean_amt) / max(std_amt, 0.001)
            rows.append([
                h["amount_log"],
                h["hour_of_day"],
                h["day_of_week"],
                zscore,
            ])
        return np.array(rows, dtype=np.float64)

    # ----------------------------------------------------------------
    # Private: Model fitting and scoring
    # ----------------------------------------------------------------

    def _fit_and_score(
        self,
        agent_id: str,
        history_matrix: np.ndarray,
        features: dict[str, float],
    ) -> AnomalyScore:
        """Fit IsolationForest on history and score the current transaction.

        Reference: .reference/scikit-learn/sklearn/ensemble/_iforest.py
        - score_samples() returns the opposite of anomaly score
        - More negative = more anomalous
        - We normalise to 0.0–1.0 where 1.0 = most anomalous
        """
        IsolationForest = self._get_isolation_forest()

        model = IsolationForest(
            n_estimators=self._n_estimators,
            contamination=self._contamination,
            random_state=self._random_state,
            max_samples=min(256, len(history_matrix)),
        )
        model.fit(history_matrix)

        # Score the current transaction
        feature_vector = np.array([[
            features["amount_log"],
            features["hour_of_day"],
            features["day_of_week"],
            features["amount_zscore"],
        ]])

        # decision_function: positive = inlier, negative = outlier, centred at ~0
        raw_score = float(model.decision_function(feature_vector)[0])

        # Normalise: map decision_function output to [0, 1] risk scale
        # raw > 0 → normal (low risk), raw < 0 → anomalous (high risk)
        risk_score = max(0.0, min(1.0, 0.5 - raw_score))

        is_anomalous = risk_score >= self._risk_threshold

        detail = ""
        if is_anomalous:
            # Identify which features contributed most
            contributing = []
            if abs(features["amount_zscore"]) > 2.0:
                contributing.append(f"unusual amount (z={features['amount_zscore']:.1f})")
            if features["hour_of_day"] < 6 or features["hour_of_day"] > 22:
                contributing.append(f"unusual hour ({int(features['hour_of_day'])}:00)")
            detail = f"Anomaly detected: {', '.join(contributing) if contributing else 'multi-feature deviation'}"
        else:
            detail = "Transaction appears normal"

        logger.info(
            "Anomaly score for agent %s: risk=%.3f raw=%.3f anomalous=%s (%d training samples)",
            agent_id, risk_score, raw_score, is_anomalous, len(history_matrix),
        )

        return AnomalyScore(
            risk_score=risk_score,
            raw_score=raw_score,
            is_anomalous=is_anomalous,
            features=features,
            model_trained=True,
            training_samples=len(history_matrix),
            detail=detail,
        )

    # ----------------------------------------------------------------
    # Private: Redis-backed transaction history
    # ----------------------------------------------------------------

    async def _record_transaction(
        self,
        agent_id: str,
        amount: int,
        features: dict[str, float],
        ts: datetime,
    ) -> None:
        """Record a transaction in Redis for future model training."""
        if not self._redis:
            return

        key = f"anomaly:history:{agent_id}"
        entry = json.dumps({
            **features,
            "amount_paise": amount,
            "timestamp": ts.isoformat(),
        })

        try:
            # LPUSH + LTRIM to maintain bounded list
            await self._redis._client.lpush(key, entry)
            await self._redis._client.ltrim(key, 0, _MAX_HISTORY_SIZE - 1)
            await self._redis._client.expire(key, _HISTORY_TTL)
        except Exception as e:
            logger.warning("Failed to record transaction history: %s", e)

    async def _get_history(self, agent_id: str) -> list[dict[str, float]]:
        """Retrieve transaction history from Redis."""
        if not self._redis:
            return []

        key = f"anomaly:history:{agent_id}"
        try:
            raw_entries = await self._redis._client.lrange(key, 0, _MAX_HISTORY_SIZE - 1)
            entries: list[dict[str, float]] = []
            for raw in raw_entries:
                try:
                    entry = json.loads(raw)
                    entries.append({
                        "amount_log": float(entry.get("amount_log", 0)),
                        "hour_of_day": float(entry.get("hour_of_day", 12)),
                        "day_of_week": float(entry.get("day_of_week", 0)),
                    })
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
            return entries
        except Exception as e:
            logger.warning("Failed to read transaction history: %s", e)
            return []
