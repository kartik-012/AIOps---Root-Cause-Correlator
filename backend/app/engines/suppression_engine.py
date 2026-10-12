"""Suppression Engine — Deterministic 7D anomaly signature encoding & pgvector cosine similarity.

Eliminates process-dependent Python `hash()` randomization (PYTHONHASHSEED) by using
cryptographically deterministic SHA-256 angular projections and centered bipolar [-1, 1]
feature scaling so unrelated incidents are orthogonal in cosine space.
Supports both in-memory template evaluation and native PostgreSQL `pgvector`
cosine distance (`<=>`) nearest-neighbor queries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import math
from typing import Any

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session


@dataclass
class SuppressionDecision:
    """Auditable decision produced by the suppression engine."""
    should_suppress: bool
    similarity_score: float
    matched_incident_id: str | None
    matched_tag: str | None = None
    reason: str = ""
    evaluation_backend: str = "in_memory"  # 'pgvector_sql' or 'in_memory'


@dataclass
class FalsePositiveTemplate:
    """Stored representation of a verified past false positive."""
    incident_id: str
    tag: str
    signature: list[float]  # 7-dimensional vector
    service_id: str | None = None
    metric_type: str | None = None


def _deterministic_unit_coord(label: str, salt: str = "") -> float:
    """Map a categorical string deterministically to [-1.0, -0.5] U [+0.5, +1.0] via SHA-256.

    Bounding magnitude >= 0.5 ensures categorical identity never vanishes near zero in cosine space.
    """
    digest = hashlib.sha256(f"{salt}:{label.strip().lower()}".encode("utf-8")).digest()
    uint32 = int.from_bytes(digest[:4], byteorder="big", signed=False)
    sign = 1.0 if (digest[4] & 1) == 0 else -1.0
    mag = 0.5 + 0.5 * (uint32 / 4294967295.0)
    return round(float(sign * mag), 6)


def encode_cyclical_time(
    hour_value: float,
    day_of_week: float,
    period_hours: float = 4.0,
) -> tuple[float, float]:
    """Project (hour, day_of_week) onto the unit circle (cos, sin) in [-1, 1]^2.

    Supports both 4-bucket hour encoding (`period_hours=4.0`) and continuous 24-hour
    timestamps (`period_hours=24.0`), ensuring boundary times such as 23:55 and 00:05
    have cosine similarity ~1.0 rather than jumping across a linear discontinuity.
    """
    if period_hours == 24.0:
        # Continuous 24-hour wraparound (e.g. 23:55 -> 23.917h wraps smoothly into 00:05 -> 0.083h)
        angle = (float(hour_value) % 24.0) * (2.0 * math.pi / 24.0)
    else:
        angle = (
            (float(hour_value) % period_hours) * (2.0 * math.pi / period_hours)
            + (float(day_of_week) % 7.0) * (2.0 * math.pi / 7.0)
        )
    return round(math.cos(angle), 6), round(math.sin(angle), 6)


def build_signature(
    hour_bucket: float,
    day_of_week: float,
    service_id: str,
    metric_type: str,
    severity_z: float,
    depth: float = 1.0,
    speed: float = 10.0,
    period_hours: float = 4.0,
) -> list[float]:
    """Build a deterministic, PYTHONHASHSEED-invariant 7-dimensional signature vector in [-1, 1]^7.

    Why centered [-1, 1] encoding matters for cosine similarity:
    In strictly positive [0, 10]^7 space, two random unrelated vectors have an expected
    cosine similarity of ~0.75 because all components share the positive orthant.
    Centering continuous and cyclical features into [-1, 1] ensures unrelated anomaly
    patterns have near-zero or negative cosine similarity while recurring benign patterns
    cluster above 0.90.
    """
    # Dim 0 & 1: Cyclical temporal encoding onto the unit circle [-1, 1]^2
    temporal_cos, temporal_sin = encode_cyclical_time(hour_bucket, day_of_week, period_hours=period_hours)

    # Dim 2 & 3: Deterministic SHA-256 bipolar coordinates for (service_id, metric_type)
    srv_coord = _deterministic_unit_coord(str(service_id), salt="svc")
    metric_coord = _deterministic_unit_coord(str(metric_type), salt="metric")

    # Dim 4: Centered Z-score magnitude around z=3.0 boundary (mild < 3.0 is negative, severe > 3.0 is positive)
    clamped_z = min(max(abs(float(severity_z)), 1.5), 6.0)
    z_centered = round(max(-1.0, min(1.0, (clamped_z - 3.0) / 1.2)), 6)

    # Dim 5: Centered cascade hop depth: maps depth 1.0 (isolated) -> -0.5, depth >= 5 -> +0.5
    clamped_depth = min(max(float(depth), 1.0), 6.0)
    depth_centered = round(((clamped_depth - 3.0) / 4.0), 6)

    # Dim 6: Centered propagation speed: maps fast cascade (speed <= 2s) -> -0.5, slow/isolated (10s) -> +0.5
    clamped_speed = min(max(float(speed), 0.5), 12.0)
    speed_centered = round(((clamped_speed - 6.0) / 8.0), 6)

    return [
        temporal_cos,
        temporal_sin,
        srv_coord,
        metric_coord,
        z_centered,
        depth_centered,
        speed_centered,
    ]


def build_signature_from_timestamp(
    timestamp: datetime,
    service_id: str,
    metric_type: str,
    severity_z: float,
    depth: float = 1.0,
    speed: float = 10.0,
) -> list[float]:
    """Build a 7D signature using continuous 24-hour cyclical time encoding from a `datetime`.

    Guarantees that recurring midnight jobs (e.g., 23:55 vs 00:05) produce near-identical
    unit-circle coordinates `(cos(2*pi*h/24), sin(2*pi*h/24))` with cosine similarity > 0.99.
    """
    fractional_hour = timestamp.hour + (timestamp.minute / 60.0) + (timestamp.second / 3600.0)
    return build_signature(
        hour_bucket=fractional_hour,
        day_of_week=float(timestamp.weekday()),
        service_id=service_id,
        metric_type=metric_type,
        severity_z=severity_z,
        depth=depth,
        speed=speed,
        period_hours=24.0,
    )



class SuppressionEngine:
    """Evaluates candidate 7D incident signatures against historical false-positive templates."""

    def __init__(self, similarity_threshold: float = 0.90):
        self.similarity_threshold = similarity_threshold
        self._fp_patterns: list[FalsePositiveTemplate] = []

    def register_false_positive(
        self,
        incident_id: str,
        signature: list[float],
        tag: str = "benign_pattern",
        service_id: str | None = None,
        metric_type: str | None = None,
    ) -> None:
        """Register a known false-positive signature template in memory."""
        if len(signature) != 7:
            raise ValueError(f"Signature must be 7-dimensional, got {len(signature)}")
        self._fp_patterns.append(
            FalsePositiveTemplate(
                incident_id=str(incident_id),
                tag=tag,
                signature=[float(x) for x in signature],
                service_id=service_id,
                metric_type=metric_type,
            )
        )

    def clear_templates(self) -> None:
        """Clear all in-memory false-positive templates."""
        self._fp_patterns.clear()

    @staticmethod
    def cosine_similarity(v1: list[float], v2: list[float]) -> float:
        """Compute cosine similarity between two 7-dimensional vectors."""
        a = np.array(v1, dtype=float)
        b = np.array(v2, dtype=float)
        norm_a = float(np.linalg.norm(a))
        norm_b = float(np.linalg.norm(b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        dot = float(np.dot(a, b))
        sim = dot / (norm_a * norm_b)
        return round(float(np.clip(sim, -1.0, 1.0)), 4)

    def evaluate_pgvector(
        self,
        db: Session,
        candidate_signature: list[float],
        service_id: str | None = None,
        metric_type: str | None = None,
    ) -> SuppressionDecision | None:
        """Execute a native PostgreSQL `pgvector` cosine distance (`<=>`) query against `incidents`,
        with optional exact metadata filtering on `(root_cause_service_id, root_cause_type)`.

        Returns a `SuppressionDecision` if the database query succeeds and finds false-positive
        records; returns `None` if no DB false positives exist or if running without pgvector.
        """
        if len(candidate_signature) != 7:
            return SuppressionDecision(
                should_suppress=False,
                similarity_score=0.0,
                matched_incident_id=None,
                reason="Invalid signature dimension",
                evaluation_backend="pgvector_sql",
            )

        try:
            import uuid
            from app.models.db_models import Incident

            distance_col = Incident.anomaly_signature.cosine_distance(candidate_signature).label("cos_dist")
            conditions = [
                Incident.was_false_positive.is_(True),
                Incident.anomaly_signature.is_not(None),
            ]
            if service_id:
                try:
                    conditions.append(Incident.root_cause_service_id == uuid.UUID(str(service_id)))
                except ValueError:
                    pass
            if metric_type:
                conditions.append(Incident.root_cause_type == str(metric_type))

            stmt = (
                select(Incident, distance_col)
                .where(*conditions)
                .order_by(distance_col.asc())
                .limit(1)
            )
            row = db.execute(stmt).first()
            if row is None:
                return None

            matched_inc, cos_dist = row[0], float(row[1])
            # Cosine similarity = 1.0 - cosine_distance
            best_score = round(float(np.clip(1.0 - cos_dist, -1.0, 1.0)), 4)
            should_suppress = best_score >= self.similarity_threshold
            tag = matched_inc.learned_pattern_tag or matched_inc.root_cause_type or "benign_pattern"

            return SuppressionDecision(
                should_suppress=should_suppress,
                similarity_score=best_score,
                matched_incident_id=str(matched_inc.id),
                matched_tag=tag,
                reason=(
                    f"pgvector cosine similarity {best_score:.3f} vs threshold "
                    f"{self.similarity_threshold} (matched template {tag})"
                ),
                evaluation_backend="pgvector_sql",
            )
        except Exception:
            # Fallback to in-memory evaluation if database dialect does not support pgvector
            return None

    def evaluate(
        self,
        candidate_signature: list[float],
        db: Session | None = None,
        service_id: str | None = None,
        metric_type: str | None = None,
    ) -> SuppressionDecision:
        """Check candidate 7D signature via PostgreSQL pgvector first (if db provided), then in-memory,
        applying exact `(service_id, metric_type)` metadata filtering when specified.
        """
        if len(candidate_signature) != 7:
            return SuppressionDecision(
                should_suppress=False,
                similarity_score=0.0,
                matched_incident_id=None,
                reason="Invalid signature dimension",
            )

        if db is not None:
            pg_decision = self.evaluate_pgvector(
                db,
                candidate_signature,
                service_id=service_id,
                metric_type=metric_type,
            )
            if pg_decision is not None:
                return pg_decision

        if not self._fp_patterns:
            return SuppressionDecision(
                should_suppress=False,
                similarity_score=0.0,
                matched_incident_id=None,
                reason="No historical false-positive templates registered",
            )

        best_score = -1.0
        best_match: FalsePositiveTemplate | None = None

        for template in self._fp_patterns:
            if service_id and template.service_id and template.service_id != service_id:
                continue
            if metric_type and template.metric_type and template.metric_type != metric_type:
                continue
            sim = self.cosine_similarity(candidate_signature, template.signature)
            if sim > best_score:
                best_score = sim
                best_match = template

        if best_match is None:
            return SuppressionDecision(
                should_suppress=False,
                similarity_score=0.0,
                matched_incident_id=None,
                reason="No historical false-positive templates matched metadata filter",
                evaluation_backend="in_memory",
            )

        should_suppress = best_score >= self.similarity_threshold

        return SuppressionDecision(
            should_suppress=should_suppress,
            similarity_score=max(best_score, 0.0),
            matched_incident_id=best_match.incident_id if best_match else None,
            matched_tag=best_match.tag if best_match else None,
            reason=f"Cosine similarity {best_score:.3f} vs threshold {self.similarity_threshold}"
            + (f" (matched template {best_match.tag})" if best_match else ""),
            evaluation_backend="in_memory",
        )

    def retrieve_similar_incidents(
        self,
        candidate_signature: list[float],
        db: Session | None = None,
        top_k: int = 5,
        false_positives_only: bool = False,
    ) -> list[dict[str, Any]]:
        """Retrieve Top-K nearest historical incidents via PostgreSQL `pgvector` `<=>` cosine distance,
        falling back to SQLite/in-memory cosine similarity ranking when pgvector is unavailable.
        """
        if len(candidate_signature) != 7 or top_k <= 0:
            return []

        if db is not None:
            bind = getattr(db, "bind", None)
            dialect_name = getattr(getattr(bind, "dialect", None), "name", "postgresql")

            # 1. Attempt native PostgreSQL pgvector HNSW cosine_distance query
            if dialect_name != "sqlite":
                try:
                    from app.models.db_models import Incident

                    distance_col = Incident.anomaly_signature.cosine_distance(candidate_signature).label("cos_dist")
                    conditions = [Incident.anomaly_signature.is_not(None)]
                    if false_positives_only:
                        conditions.append(Incident.was_false_positive.is_(True))

                    stmt = (
                        select(Incident, distance_col)
                        .where(*conditions)
                        .order_by(distance_col.asc())
                        .limit(top_k)
                    )
                    rows = db.execute(stmt).all()
                    if rows:
                        results: list[dict[str, Any]] = []
                        for inc, dist in rows:
                            sim = round(float(np.clip(1.0 - float(dist), -1.0, 1.0)), 4)
                            results.append({
                                "incident_id": str(inc.id),
                                "similarity": sim,
                                "root_cause_type": inc.root_cause_type,
                                "was_false_positive": bool(inc.was_false_positive),
                                "learned_pattern_tag": inc.learned_pattern_tag,
                                "backend": "pgvector_sql",
                            })
                        return results
                except Exception:
                    try:
                        db.rollback()
                    except Exception:
                        pass

            # 2. Fallback: fetch Incident rows from DB (e.g. SQLite) and rank in-memory by cosine_similarity
            try:
                from app.models.db_models import Incident

                conditions = [Incident.anomaly_signature.is_not(None)]
                if false_positives_only:
                    conditions.append(Incident.was_false_positive.is_(True))
                inc_rows = db.scalars(select(Incident).where(*conditions)).all()
                scored: list[dict[str, Any]] = []
                for inc in inc_rows:
                    raw_sig = inc.anomaly_signature
                    if raw_sig is not None and len(raw_sig) == 7:
                        sim = self.cosine_similarity(
                            candidate_signature,
                            [float(x) for x in raw_sig],
                        )
                        scored.append({
                            "incident_id": str(inc.id),
                            "similarity": sim,
                            "root_cause_type": inc.root_cause_type,
                            "was_false_positive": bool(inc.was_false_positive),
                            "learned_pattern_tag": inc.learned_pattern_tag,
                            "backend": "db_cosine_fallback",
                        })
                if scored:
                    scored.sort(key=lambda r: r["similarity"], reverse=True)
                    return scored[:top_k]
            except Exception:
                pass

        # 3. Final fallback: in-memory registered false positive templates
        mem_scored = [
            {
                "incident_id": tpl.incident_id,
                "similarity": self.cosine_similarity(candidate_signature, tpl.signature),
                "root_cause_type": tpl.metric_type,
                "was_false_positive": True,
                "learned_pattern_tag": tpl.tag,
                "backend": "in_memory",
            }
            for tpl in self._fp_patterns
        ]
        mem_scored.sort(key=lambda r: r["similarity"], reverse=True)
        return mem_scored[:top_k]


