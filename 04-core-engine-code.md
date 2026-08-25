# 📘 core-engine-code.md

**Real starter implementations — not pseudocode.** These are working algorithm cores for the three most important engines. Wire them into the FastAPI endpoints from `api-spec.md`.

---

## 1. Detection Engine — Z-Score + EWMA Drift-Aware Thresholds

```python
# app/engines/detection_engine.py
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime

@dataclass
class MetricState:
    ewma_mean: float = 0.0
    ewma_var: float = 0.0
    initialized: bool = False
    alpha: float = 0.1  # EWMA decay factor — tune this

    def update(self, value: float) -> float:
        """Update EWMA baseline and return current z-score."""
        if not self.initialized:
            self.ewma_mean = value
            self.ewma_var = 0.0
            self.initialized = True
            return 0.0

        prev_mean = self.ewma_mean
        self.ewma_mean = self.alpha * value + (1 - self.alpha) * prev_mean
        diff = value - prev_mean
        self.ewma_var = (1 - self.alpha) * (self.ewma_var + self.alpha * diff ** 2)

        std = self.ewma_var ** 0.5
        if std == 0:
            return 0.0
        return (value - self.ewma_mean) / std


class DetectionEngine:
    """Maintains per-service, per-metric EWMA state and flags anomalies."""

    Z_SCORE_THRESHOLD = 3.0

    def __init__(self):
        self._states: dict[tuple[str, str], MetricState] = {}

    def _get_state(self, service_id: str, metric_type: str) -> MetricState:
        key = (service_id, metric_type)
        if key not in self._states:
            self._states[key] = MetricState()
        return self._states[key]

    def process_metric(self, service_id: str, metric_type: str, value: float, timestamp: datetime) -> dict:
        state = self._get_state(service_id, metric_type)
        z_score = state.update(value)
        is_anomaly = abs(z_score) > self.Z_SCORE_THRESHOLD

        return {
            "service_id": service_id,
            "metric_type": metric_type,
            "value": value,
            "z_score": round(z_score, 3),
            "is_anomaly": is_anomaly,
            "severity": self._severity(z_score),
            "timestamp": timestamp.isoformat(),
        }

    @staticmethod
    def _severity(z_score: float) -> str:
        abs_z = abs(z_score)
        if abs_z > 6:
            return "critical"
        elif abs_z > 4.5:
            return "high"
        elif abs_z > 3:
            return "medium"
        return "low"
```

**Why EWMA over a fixed rolling window:** a fixed window mean treats all past points equally and needs manual window-size tuning. EWMA gives recent points more weight and adapts continuously — this is what makes the threshold "drift-aware" instead of static.

---

## 2. Correlation Engine — Multi-Root-Cause Graph Walk

```python
# app/engines/correlation_engine.py
import networkx as nx
from datetime import datetime, timedelta

class CorrelationEngine:
    """
    Groups anomaly events into incidents and identifies root cause(s)
    using the service dependency graph. Supports multiple independent
    incidents happening simultaneously.
    """

    TIME_WINDOW_SECONDS = 90

    def __init__(self, dependency_graph: nx.DiGraph):
        self.graph = dependency_graph  # edges point downstream: A -> B means A calls B

    def correlate(self, anomalies: list[dict]) -> list[dict]:
        """
        anomalies: list of {"service_id": str, "timestamp": datetime, "severity": float}
        Returns: list of incidents, each with a root cause and affected services.
        """
        if not anomalies:
            return []

        # Step 1: build the anomaly subgraph (only anomalous services + their real edges)
        anomalous_services = {a["service_id"] for a in anomalies}
        subgraph = self.graph.subgraph(anomalous_services).copy()

        # Step 2: find connected components (undirected view) — each is a candidate incident
        undirected = subgraph.to_undirected()
        components = list(nx.connected_components(undirected))

        incidents = []
        for component in components:
            component_anomalies = [a for a in anomalies if a["service_id"] in component]
            incident = self._analyze_component(component_anomalies, subgraph)
            incidents.append(incident)

        return incidents

    def _analyze_component(self, anomalies: list[dict], subgraph: nx.DiGraph) -> dict:
        # Sort by timestamp — earliest anomaly is the leading candidate
        sorted_anomalies = sorted(anomalies, key=lambda a: a["timestamp"])

        # Root cause candidate: earliest anomaly with no anomalous upstream dependency
        root_candidate = None
        for anomaly in sorted_anomalies:
            service = anomaly["service_id"]
            upstream = list(subgraph.predecessors(service))
            anomalous_upstream = [u for u in upstream if u in [a["service_id"] for a in anomalies]]
            if not anomalous_upstream:
                root_candidate = anomaly
                break

        if root_candidate is None:
            root_candidate = sorted_anomalies[0]  # fallback: earliest overall

        affected = [a["service_id"] for a in sorted_anomalies if a["service_id"] != root_candidate["service_id"]]

        confidence = self._score_confidence(root_candidate, sorted_anomalies, subgraph)

        return {
            "root_cause_service": root_candidate["service_id"],
            "confidence": confidence,
            "affected_services": affected,
            "is_multi_root_cause": False,  # this flag is set at the caller level if len(incidents) > 1
            "timeline": [
                {"service": a["service_id"], "timestamp": a["timestamp"].isoformat()}
                for a in sorted_anomalies
            ],
        }

    def _score_confidence(self, root: dict, all_anomalies: list[dict], subgraph: nx.DiGraph) -> float:
        # Weighted combination: timestamp precedence + severity + graph centrality
        severity_score = min(root["severity"] / 6.0, 1.0)  # normalize against a z-score cap of ~6
        centrality = nx.out_degree_centrality(subgraph).get(root["service_id"], 0)
        precedence_score = 1.0  # root was chosen as earliest with no anomalous upstream

        confidence = 0.5 * severity_score + 0.3 * precedence_score + 0.2 * centrality
        return round(min(confidence, 0.99), 2)
```

**Why connected components solves multi-root-cause:** if `payment-service` and `notification-service` fail independently with no dependency path between them, they land in separate connected components — each gets its own root-cause analysis instead of being incorrectly merged into one incident.

---

## 3. Suppression Engine — Historical Memory via Cosine Similarity

```python
# app/engines/suppression_engine.py
import numpy as np
from dataclasses import dataclass

@dataclass
class HistoricalIncident:
    incident_id: str
    signature: np.ndarray
    was_false_positive: bool
    root_cause_type: str

class SuppressionEngine:
    """Checks new anomaly signatures against known benign historical patterns."""

    SUPPRESSION_THRESHOLD = 0.90  # tune against your evaluation scenarios

    def __init__(self, historical_incidents: list[HistoricalIncident]):
        self.history = [h for h in historical_incidents if h.was_false_positive]

    def check(self, new_signature: np.ndarray) -> dict:
        if not self.history:
            return {"suppress": False}

        best_match = None
        best_similarity = -1.0

        for record in self.history:
            similarity = self._cosine_similarity(new_signature, record.signature)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = record

        if best_similarity >= self.SUPPRESSION_THRESHOLD:
            return {
                "suppress": True,
                "matched_incident_id": best_match.incident_id,
                "similarity": round(best_similarity, 3),
            }

        return {"suppress": False, "best_similarity": round(best_similarity, 3)}

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
```

**Signature vector construction** (build this before calling `check`):
```python
def build_signature(anomaly: dict) -> np.ndarray:
    return np.array([
        anomaly["time_of_day_bucket"],   # 0-3 encoded
        anomaly["day_of_week"],          # 0-6
        anomaly["service_hash"],         # stable numeric hash of service_id
        anomaly["metric_type_encoded"],  # 0-3 encoded
        anomaly["severity_zscore"],
        anomaly["propagation_depth"],
        anomaly["propagation_speed_seconds"],
    ])
```

---

## 4. Wiring It Together (pipeline sketch)

```python
# app/api/v1/detection.py (simplified)
from fastapi import APIRouter
from app.engines.detection_engine import DetectionEngine
from app.engines.suppression_engine import SuppressionEngine, build_signature
from app.engines.correlation_engine import CorrelationEngine

router = APIRouter()
detection_engine = DetectionEngine()
# suppression_engine and correlation_engine constructed with real DB-backed data at startup

@router.post("/detection/ingest")
async def ingest_metric(payload: dict):
    result = detection_engine.process_metric(
        payload["service_id"], payload["metric_type"], payload["value"], payload["recorded_at"]
    )

    if result["is_anomaly"]:
        signature = build_signature(result)
        suppression_result = suppression_engine.check(signature)

        if suppression_result["suppress"]:
            # log suppression, do NOT proceed to correlation
            return {**result, "suppressed": True, **suppression_result}

        # proceed to correlation engine, store anomaly, etc.

    return result
```

This is the actual skeleton — next step is writing the unit tests in `tests/unit/` against your 25-30 scenarios (see `05-evaluation-scenarios.md`) to get real accuracy numbers.
