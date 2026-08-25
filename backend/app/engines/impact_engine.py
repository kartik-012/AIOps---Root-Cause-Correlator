"""Impact Engine — Quantifies business impact based on topology, severity, and revenue weights.

Impact score = severity_weight * service_revenue_weight * downstream_dependent_count.
"""

from dataclasses import dataclass
from app.graph.dependency_graph import DependencyGraph


@dataclass
class ImpactAssessment:
    """Detailed business impact assessment."""
    impact_score: float
    severity_label: str
    service_id: str
    service_name: str
    revenue_weight: float
    downstream_dependent_count: int
    revenue_weighted: bool = True


class ImpactEngine:
    """Computes business and financial criticality scores for active incidents."""

    SEVERITY_MULTIPLIERS = {
        "critical": 4.0,
        "high": 3.0,
        "medium": 2.0,
        "low": 1.0,
    }

    def __init__(self, dependency_graph: DependencyGraph):
        self.dep_graph = dependency_graph

    def calculate_impact(
        self,
        service_id: str,
        severity: str = "high",
        custom_affected_count: int | None = None,
    ) -> ImpactAssessment:
        """Calculate business impact score for a service.

        Formula: severity_weight * revenue_weight * (downstream_dependent_count + 1)
        """
        node_data = self.dep_graph.get_node_data(service_id)
        name = node_data.get("name", service_id)
        revenue_weight = float(node_data.get("revenue_weight", 1.0))

        if custom_affected_count is not None:
            downstream_count = custom_affected_count
        else:
            # Count all callers that depend on this service
            callers = self.dep_graph.get_all_upstream_callers(service_id)
            downstream_count = len(callers)

        sev_multiplier = self.SEVERITY_MULTIPLIERS.get(severity.lower(), 2.0)

        # Multiplier of 1 + dependents so even isolated services score proportional to revenue
        impact_score = round(sev_multiplier * revenue_weight * (1 + downstream_count), 2)

        return ImpactAssessment(
            impact_score=impact_score,
            severity_label=severity.lower(),
            service_id=service_id,
            service_name=name,
            revenue_weight=revenue_weight,
            downstream_dependent_count=downstream_count,
            revenue_weighted=True,
        )
