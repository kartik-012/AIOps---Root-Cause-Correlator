"""Suppression Engine — False-positive suppression using cosine similarity against historical patterns.

Compares new incident/anomaly feature signatures against stored vectors of known false positives.
Never silently drops alerts; returns audit records with match scores.
"""

from dataclasses import dataclass
import numpy as np


@dataclass
class SuppressionDecision:
    """Decision produced by the suppression engine."""
    should_suppress: bool
    similarity_score: float
    matched_incident_id: str | None
    matched_tag: str | None = None
    reason: str = ""


@dataclass
class FalsePositiveTemplate:
    """Stored representation of a verified past false positive."""
    incident_id: str
    tag: str
    signature: list[float]  # 7-dimensional vector


def build_signature(
    hour_bucket: float,
    day_of_week: float,
    service_id: str,
    metric_type: str,
    severity_z: float,
    depth: float = 1.0,
    speed: float = 10.0,
) -> list[float]:
    """Build a standardized 7-dimensional anomaly signature vector."""
    srv_hash = float((abs(hash(service_id)) % 100) / 10.0)
    metric_hash = float((abs(hash(metric_type)) % 10) / 1.0)
    return [
        float(hour_bucket),
        float(day_of_week),
        float(srv_hash),
        float(metric_hash),
        float(severity_z),
        float(depth),
        float(speed),
    ]


class SuppressionEngine:
    """Evaluates candidate incidents/anomalies against known false-positive signatures."""

    def __init__(self, similarity_threshold: float = 0.90):
        self.similarity_threshold = similarity_threshold
        self._fp_patterns: list[FalsePositiveTemplate] = []

    def register_false_positive(self, incident_id: str, signature: list[float], tag: str = "benign_pattern") -> None:
        """Register a known false positive signature template."""
        if len(signature) != 7:
            raise ValueError(f"Signature must be 7-dimensional, got {len(signature)}")
        self._fp_patterns.append(
            FalsePositiveTemplate(
                incident_id=str(incident_id),
                tag=tag,
                signature=[float(x) for x in signature],
            )
        )

    def clear_templates(self) -> None:
        """Clear all registered false-positive templates."""
        self._fp_patterns.clear()

    @staticmethod
    def cosine_similarity(v1: list[float], v2: list[float]) -> float:
        """Compute cosine similarity between two 7-dimensional vectors."""
        a = np.array(v1, dtype=float)
        b = np.array(v2, dtype=float)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        dot = np.dot(a, b)
        sim = float(dot / (norm_a * norm_b))
        return round(float(np.clip(sim, 0.0, 1.0)), 4)

    def evaluate(self, candidate_signature: list[float]) -> SuppressionDecision:
        """Check candidate 7-dim signature against stored false-positive signatures."""
        if len(candidate_signature) != 7:
            return SuppressionDecision(
                should_suppress=False,
                similarity_score=0.0,
                matched_incident_id=None,
                reason="Invalid signature dimension",
            )

        if not self._fp_patterns:
            return SuppressionDecision(
                should_suppress=False,
                similarity_score=0.0,
                matched_incident_id=None,
                reason="No historical false-positive templates registered",
            )

        best_score = 0.0
        best_match: FalsePositiveTemplate | None = None

        for template in self._fp_patterns:
            sim = self.cosine_similarity(candidate_signature, template.signature)
            if sim > best_score:
                best_score = sim
                best_match = template

        should_suppress = best_score >= self.similarity_threshold

        return SuppressionDecision(
            should_suppress=should_suppress,
            similarity_score=best_score,
            matched_incident_id=best_match.incident_id if best_match else None,
            matched_tag=best_match.tag if best_match else None,
            reason=f"Cosine similarity {best_score:.3f} vs threshold {self.similarity_threshold}"
            + (f" (matched template {best_match.tag})" if best_match else ""),
        )
