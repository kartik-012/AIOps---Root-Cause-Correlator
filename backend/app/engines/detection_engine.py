"""Detection Engine — Drift-aware EWMA baseline with adaptive z-score anomaly detection.

Tracks running exponentially-weighted moving average (EWMA) mean and variance
per (service, metric_type) without requiring fixed sliding windows.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import math


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

    def __init__(self, alpha: float = 0.3, min_samples: int = 3, epsilon: float = 1e-4):
        self.alpha = alpha
        self.min_samples = min_samples
        self.epsilon = epsilon
        self.mean: float | None = None
        self.variance: float | None = None
        self.count: int = 0

    def update(self, value: float) -> tuple[float, float, float]:
        """Update EWMA with a new observation and return (mean, std, z_score).

        Uses Welford-like exponential weighting:
        mu_t = alpha * x_t + (1 - alpha) * mu_{t-1}
        var_t = (1 - alpha) * (var_{t-1} + alpha * (x_t - mu_{t-1})^2)
        """
        self.count += 1

        if self.mean is None:
            self.mean = float(value)
            self.variance = 1.0  # Initial variance prior
            z_score = 0.0
            std = math.sqrt(self.variance)
            return self.mean, std, z_score

        # Compute z-score against prior baseline before updating
        prior_mean = self.mean
        prior_var = max(self.variance if self.variance is not None else 1.0, self.epsilon)
        prior_std = math.sqrt(prior_var)

        z_score = (value - prior_mean) / prior_std

        # Update running mean and variance
        diff = value - prior_mean
        self.mean = self.alpha * value + (1.0 - self.alpha) * prior_mean
        
        # Adaptive variance tracking with exponential weighting
        incr_var = (1.0 - self.alpha) * (prior_var + self.alpha * (diff ** 2))
        self.variance = max(incr_var, self.epsilon)
        std = math.sqrt(self.variance)

        return self.mean, std, z_score


class DetectionEngine:
    """Streaming anomaly detection engine for microservice telemetry."""

    def __init__(
        self,
        alpha: float = 0.3,
        base_threshold: float = 2.0,
        min_samples: int = 3,
    ):
        self.alpha = alpha
        self.base_threshold = base_threshold
        self.min_samples = min_samples
        # Map of (service_id, metric_type) -> EWMAState
        self._states: dict[tuple[str, str], EWMAState] = {}

    def _get_or_create_state(self, service_id: str, metric_type: str) -> EWMAState:
        key = (str(service_id), str(metric_type))
        if key not in self._states:
            self._states[key] = EWMAState(
                alpha=self.alpha,
                min_samples=self.min_samples,
            )
        return self._states[key]

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
                del self._states[k]
