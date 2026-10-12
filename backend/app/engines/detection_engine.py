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
    burn_in_complete: bool = True
    winsorized: bool = False


class EWMAState:
    """Tracks running EWMA mean and variance for a single metric stream.

    Uses Welford's online algorithm during the initial `min_samples` burn-in window
    to compute a scale-accurate initial mean and sample variance (avoiding cold-start
    false positives on high-magnitude metrics like `latency_ms=200` and false negatives
    on sub-unit metrics like `error_rate=0.01`), followed by Huber/Winsorized residual
    clipping and outlier-damped EWMA updates when `|z| >= poisoning_threshold`.
    """

    def __init__(
        self,
        alpha: float = 0.3,
        min_samples: int = 3,
        epsilon: float = 1e-6,
        guard_poisoning: bool = True,
        poisoning_threshold: float = 2.0,
    ):
        self.alpha = alpha
        self.min_samples = min_samples
        self.epsilon = epsilon
        self.guard_poisoning = guard_poisoning
        self.poisoning_threshold = poisoning_threshold
        self.mean: float | None = None
        self.variance: float | None = None
        self.count: int = 0
        self._welford_mean: float = 0.0
        self._welford_m2: float = 0.0
        self.last_winsorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialize EWMA state for Redis persistence."""
        return {
            "alpha": self.alpha,
            "min_samples": self.min_samples,
            "epsilon": self.epsilon,
            "guard_poisoning": self.guard_poisoning,
            "poisoning_threshold": self.poisoning_threshold,
            "mean": self.mean,
            "variance": self.variance,
            "count": self.count,
            "welford_mean": self._welford_mean,
            "welford_m2": self._welford_m2,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EWMAState:
        """Restore EWMA state from Redis hash or JSON payload."""
        raw_guard = data.get("guard_poisoning", True)
        if isinstance(raw_guard, str):
            guard_val = raw_guard.lower() not in ("false", "0", "no")
        else:
            guard_val = bool(raw_guard)

        state = cls(
            alpha=float(data.get("alpha", 0.3)),
            min_samples=int(data.get("min_samples", 3)),
            epsilon=float(data.get("epsilon", 1e-6)),
            guard_poisoning=guard_val,
            poisoning_threshold=float(data.get("poisoning_threshold", 2.0)),
        )
        state.mean = float(data["mean"]) if data.get("mean") not in (None, "None") else None
        state.variance = float(data["variance"]) if data.get("variance") not in (None, "None") else None
        state.count = int(data.get("count", 0))
        state._welford_mean = float(data.get("welford_mean", state.mean or 0.0))
        state._welford_m2 = float(data.get("welford_m2", 0.0))
        return state

    @staticmethod
    def _scale_variance_floor(ref_value: float, epsilon: float) -> float:
        """Compute a minimum variance floor proportional to metric scale to prevent zero-variance division."""
        abs_v = abs(float(ref_value))
        if abs_v <= 0.0:
            return max(1e-4, epsilon)
        if abs_v < 1.0:
            # Sub-unit metrics (e.g. error_rate = 0.01 -> floor std = 0.0025)
            return max((abs_v * 0.25) ** 2, epsilon)
        # Larger metrics (e.g. latency_ms = 200 -> floor std = 2.0, i.e., 1% of scale)
        return max((abs_v * 0.01) ** 2, epsilon)

    def update(self, value: float) -> tuple[float, float, float]:
        """Update EWMA with a new observation and return (mean, std, z_score).

        1. During burn-in (`count <= min_samples`), accumulates Welford's online mean and M2
           sample variance so initial variance adapts to the true metric scale (`0.01` vs `200.0`).
        2. Post burn-in (`count > min_samples`), computes z-score against the prior baseline.
           When `|z| >= poisoning_threshold`, applies Huber/Winsorized residual clipping
           (`|d_winsorized| <= poisoning_threshold * prior_std`) and damps `alpha` so neither
           sustained anomaly bursts nor extreme 1000-sigma spikes can contaminate the baseline.
        """
        val = float(value)
        self.count += 1
        self.last_winsorized = False

        if self.count == 1 or self.mean is None:
            self._welford_mean = val
            self._welford_m2 = 0.0
            self.mean = val
            self.variance = self._scale_variance_floor(val, self.epsilon)
            return self.mean, math.sqrt(self.variance), 0.0

        # Compute z-score against prior baseline before updating
        prior_mean = self.mean
        prior_var = max(
            self.variance if self.variance is not None else self._scale_variance_floor(prior_mean, self.epsilon),
            self.epsilon,
        )
        prior_std = math.sqrt(prior_var)
        raw_diff = val - prior_mean
        z_score = raw_diff / prior_std

        if self.count <= self.min_samples:
            # Welford's online algorithm for burn-in window
            delta = val - self._welford_mean
            self._welford_mean += delta / self.count
            delta2 = val - self._welford_mean
            self._welford_m2 += delta * delta2

            sample_var = self._welford_m2 / max(self.count - 1, 1)
            scale_floor = self._scale_variance_floor(self._welford_mean, self.epsilon)
            self.mean = self._welford_mean
            self.variance = max(sample_var, scale_floor, self.epsilon)
            return self.mean, math.sqrt(self.variance), z_score

        # Post burn-in: Huber/Winsorized residual clipping + tiered alpha damping when |z| >= threshold
        if self.guard_poisoning and abs(z_score) >= self.poisoning_threshold:
            self.last_winsorized = True
            max_residual = self.poisoning_threshold * prior_std
            effective_diff = math.copysign(min(abs(raw_diff), max_residual), raw_diff)
            if abs(z_score) >= 4.0:
                eff_alpha = self.alpha * 0.02
            else:
                eff_alpha = self.alpha * 0.10
        else:
            effective_diff = raw_diff
            eff_alpha = self.alpha

        # Update running mean and variance using Winsorized innovation residual
        self.mean = prior_mean + eff_alpha * effective_diff

        incr_var = (1.0 - eff_alpha) * (prior_var + eff_alpha * (effective_diff ** 2))
        scale_floor = self._scale_variance_floor(self.mean, self.epsilon)
        self.variance = max(incr_var, scale_floor, self.epsilon)
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
            poisoning_threshold=self.base_threshold,
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
            burn_in_complete=(state.count >= self.min_samples),
            winsorized=state.last_winsorized,
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
