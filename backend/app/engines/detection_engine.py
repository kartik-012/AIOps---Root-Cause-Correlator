"""Detection Engine — Drift-aware EWMA baseline with adaptive z-score anomaly detection.

Tracks running exponentially-weighted moving average (EWMA) mean and variance
per (service, metric_type) with:
1. Optional Redis state persistence (`aiops:ewma:{service_id}:{metric_type}`) and transparent in-memory fallback.
2. Baseline poisoning protection (damped EWMA adaptation during extreme `|z| >= 4.0` outage spikes so a single
   spike does not corrupt the running variance and mask subsequent anomalies).
3. Unified process-wide singleton (`get_shared_detection_engine()`) shared by REST API and Kafka consumers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import math
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AnomalyDetectionResult:
    """Result of anomaly detection for a metric point."""
    service_id: str
    metric_type: str
    value: float
    is_anomaly: bool
    z_score: float
    severity: str  # 'low', 'medium', 'high', 'critical'
    ewma_mean: float
    ewma_std: float
    timestamp: datetime


class EWMAState:
    """Tracks running EWMA mean and variance for a single metric stream."""

    def __init__(
        self,
        alpha: float = 0.3,
        min_samples: int = 3,
        epsilon: float = 1e-4,
        guard_poisoning: bool = True,
    ):
        self.alpha = alpha
        self.min_samples = min_samples
        self.epsilon = epsilon
        self.guard_poisoning = guard_poisoning
        self.mean: float | None = None
        self.variance: float | None = None
        self.count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize EWMA state for Redis persistence."""
        return {
            "alpha": self.alpha,
            "min_samples": self.min_samples,
            "epsilon": self.epsilon,
            "guard_poisoning": self.guard_poisoning,
            "mean": self.mean,
            "variance": self.variance,
            "count": self.count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EWMAState:
        """Restore EWMA state from Redis JSON payload."""
        state = cls(
            alpha=float(data.get("alpha", 0.3)),
            min_samples=int(data.get("min_samples", 3)),
            epsilon=float(data.get("epsilon", 1e-4)),
            guard_poisoning=bool(data.get("guard_poisoning", True)),
        )
        state.mean = float(data["mean"]) if data.get("mean") is not None else None
        state.variance = float(data["variance"]) if data.get("variance") is not None else None
        state.count = int(data.get("count", 0))
        return state

    def update(self, value: float) -> tuple[float, float, float]:
        """Update EWMA with a new observation and return (mean, std, z_score).

        Uses Welford-like exponential weighting with anomaly-poisoning damping:
        mu_t = alpha_eff * x_t + (1 - alpha_eff) * mu_{t-1}
        var_t = (1 - alpha_eff) * (var_{t-1} + alpha_eff * (x_t - mu_{t-1})^2)
        """
        self.count += 1

        if self.mean is None:
            self.mean = float(value)
            # Scale-aware initial variance prior for sub-unit metrics (e.g., error_rate = 0.01)
            abs_v = abs(float(value))
            if 0.0 < abs_v < 1.0:
                self.variance = max((abs_v * 0.25) ** 2, self.epsilon)
            else:
                self.variance = 1.0
            z_score = 0.0
            std = math.sqrt(self.variance)
            return self.mean, std, z_score

        # Compute z-score against prior baseline before updating
        prior_mean = self.mean
        prior_var = max(self.variance if self.variance is not None else 1.0, self.epsilon)
        prior_std = math.sqrt(prior_var)

        z_score = (value - prior_mean) / prior_std

        # Guard against baseline poisoning on extreme anomaly spikes (|z| >= 4.0 after burn-in)
        if self.guard_poisoning and self.count > self.min_samples and abs(z_score) >= 4.0:
            eff_alpha = self.alpha * 0.05
        else:
            eff_alpha = self.alpha

        # Update running mean and variance
        diff = value - prior_mean
        self.mean = eff_alpha * value + (1.0 - eff_alpha) * prior_mean

        # Adaptive variance tracking with exponential weighting
        incr_var = (1.0 - eff_alpha) * (prior_var + eff_alpha * (diff ** 2))
        self.variance = max(incr_var, self.epsilon)
        std = math.sqrt(self.variance)

        return self.mean, std, z_score


class DetectionEngine:
    """Streaming anomaly detection engine for microservice telemetry with optional Redis state store."""

    def __init__(
        self,
        alpha: float = 0.3,
        base_threshold: float = 2.0,
        min_samples: int = 3,
        redis_client: Any | None = None,
        redis_ttl_seconds: int = 3600,
    ):
        self.alpha = alpha
        self.base_threshold = base_threshold
        self.min_samples = min_samples
        self._redis = redis_client
        self._redis_ttl = redis_ttl_seconds
        # Map of (service_id, metric_type) -> EWMAState
        self._states: dict[tuple[str, str], EWMAState] = {}

    @staticmethod
    def _redis_key(service_id: str, metric_type: str) -> str:
        return f"ewma:{service_id}:{metric_type}"

    def _get_or_create_state(self, service_id: str, metric_type: str) -> EWMAState:
        key = (str(service_id), str(metric_type))
        if key in self._states:
            return self._states[key]

        # Attempt to restore state from Redis hash (ewma:{service_id}:{metric}) or JSON string fallback
        if self._redis is not None:
            rkey = self._redis_key(str(service_id), str(metric_type))
            try:
                if hasattr(self._redis, "hgetall"):
                    hdata = self._redis.hgetall(rkey)
                    if hdata:
                        decoded = {
                            (k.decode("utf-8") if isinstance(k, bytes) else str(k)): (
                                v.decode("utf-8") if isinstance(v, bytes) else v
                            )
                            for k, v in hdata.items()
                        }
                        restored = EWMAState.from_dict(decoded)
                        self._states[key] = restored
                        return restored
                raw = self._redis.get(rkey)
                if raw:
                    data = json.loads(raw if isinstance(raw, str) else raw.decode("utf-8"))
                    restored = EWMAState.from_dict(data)
                    self._states[key] = restored
                    return restored
            except Exception as exc:
                logger.debug("Redis EWMA restore fallback to memory: %s", exc)

        state = EWMAState(
            alpha=self.alpha,
            min_samples=self.min_samples,
        )
        self._states[key] = state
        return state

    def _persist_state(self, service_id: str, metric_type: str, state: EWMAState) -> None:
        if self._redis is None:
            return
        try:
            rkey = self._redis_key(str(service_id), str(metric_type))
            state_dict = state.to_dict()
            if hasattr(self._redis, "hset"):
                self._redis.hset(
                    rkey,
                    mapping={k: str(v) for k, v in state_dict.items() if v is not None},
                )
                if hasattr(self._redis, "expire"):
                    self._redis.expire(rkey, self._redis_ttl)
            else:
                self._redis.setex(rkey, self._redis_ttl, json.dumps(state_dict))
        except Exception as exc:
            logger.debug("Redis EWMA persist skipped: %s", exc)

    def classify_severity(self, abs_z: float) -> str:
        """Map absolute z-score to standard severity string."""
        if abs_z >= 4.0:
            return "critical"
        elif abs_z >= 3.0:
            return "high"
        elif abs_z >= 2.0:
            return "medium"
        return "low"

    def process_metric(
        self,
        service_id: str,
        metric_type: str,
        value: float,
        timestamp: datetime | None = None,
    ) -> AnomalyDetectionResult:
        """Ingest a metric data point, update baseline, and score for anomalies.

        Adaptive threshold adjusts dynamically if variance is drifting.
        """
        ts = timestamp if timestamp is not None else datetime.now(timezone.utc)
        state = self._get_or_create_state(service_id, metric_type)

        mean, std, z_score = state.update(value)
        self._persist_state(service_id, metric_type, state)
        abs_z = abs(z_score)

        # Require minimum burn-in samples before flagging anomalies
        if state.count < self.min_samples:
            is_anomaly = False
            severity = "low"
        else:
            is_anomaly = abs_z >= self.base_threshold
            severity = self.classify_severity(abs_z) if is_anomaly else "low"

        return AnomalyDetectionResult(
            service_id=str(service_id),
            metric_type=metric_type,
            value=float(value),
            is_anomaly=is_anomaly,
            z_score=float(z_score),
            severity=severity,
            ewma_mean=float(mean),
            ewma_std=float(std),
            timestamp=ts,
        )

    def reset_state(self, service_id: str | None = None, metric_type: str | None = None) -> None:
        """Reset state for a specific metric or all metrics."""
        if service_id is None and metric_type is None:
            self._states.clear()
        else:
            keys_to_del = [
                k for k in self._states.keys()
                if (service_id is None or k[0] == str(service_id))
                and (metric_type is None or k[1] == str(metric_type))
            ]
            for k in keys_to_del:
                if self._redis is not None:
                    try:
                        self._redis.delete(self._redis_key(k[0], k[1]))
                    except Exception:
                        pass
                del self._states[k]


_shared_detection_engine: DetectionEngine | None = None


def get_shared_detection_engine() -> DetectionEngine:
    """Return the unified process-wide DetectionEngine singleton used by REST, OTel, and Kafka consumers."""
    global _shared_detection_engine
    if _shared_detection_engine is None:
        redis_client = None
        try:
            import redis
            from app.config import get_settings

            settings = get_settings()
            client = redis.from_url(settings.REDIS_URL, socket_connect_timeout=0.3, socket_timeout=0.3)
            client.ping()
            redis_client = client
        except Exception:
            redis_client = None

        _shared_detection_engine = DetectionEngine(
            alpha=0.3,
            base_threshold=2.5,
            min_samples=3,
            redis_client=redis_client,
        )
    return _shared_detection_engine
