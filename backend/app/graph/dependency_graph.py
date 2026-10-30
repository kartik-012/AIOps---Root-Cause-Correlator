"""NetworkX-based dependency graph module for microservices topology.

Provides utilities for building directed dependency graphs, querying upstream/downstream
nodes, extracting anomalous subgraphs, and finding connected components.
"""

import math
from typing import Any
import networkx as nx


# DependencyGraph represents directed microservice service topology in NetworkX
class DependencyGraph:
    """Represents the directed microservice dependency graph.

    Edges represent dependency direction: (A, B) means Service A depends on Service B
    (i.e. A calls B, requests flow A -> B, upstream is A, downstream is B).
    """

    def __init__(self, graph: nx.DiGraph | None = None):
        self.graph = graph if graph is not None else nx.DiGraph()

    @classmethod
    def from_nodes_and_edges(
        cls,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> "DependencyGraph":
        """Build graph from node and edge list dicts.

        Args:
            nodes: List of dicts, each with 'id' or 'name', and optional metadata like 'revenue_weight'.
            edges: List of dicts, each with 'from'/'source' and 'to'/'target'.
        """
        g = nx.DiGraph()
        for node in nodes:
            node_id = str(node.get("id", node.get("name")))
            attrs = {k: v for k, v in node.items() if k != "id"}
            attrs.setdefault("name", node_id)
            attrs.setdefault("revenue_weight", 1.0)
            g.add_node(node_id, **attrs)

        for edge in edges:
            source = str(edge.get("from", edge.get("source", edge.get("from_service_id"))))
            target = str(edge.get("to", edge.get("target", edge.get("to_service_id"))))
            if source and target:
                g.add_edge(source, target)

        return cls(g)

    def add_service(self, service_id: str, name: str, revenue_weight: float = 1.0) -> None:
        """Add a service node to the graph."""
        self.graph.add_node(service_id, name=name, revenue_weight=revenue_weight)

    def add_dependency(self, from_service_id: str, to_service_id: str, weight: float = 1.0) -> None:
        """Add directed dependency: from_service depends on to_service."""
        self.graph.add_edge(from_service_id, to_service_id, weight=float(weight))

    def set_edge_weight(
        self,
        from_service_id: str,
        to_service_id: str,
        weight: float = 1.0,
        rps: float = 0.0,
        covariance: float = 0.0,
    ) -> None:
        """Set dynamic edge weight based on call volume (RPS) and metric covariance (MicroRCA++)."""
        computed_weight = float(weight)
        if rps > 0.0:
            computed_weight *= (1.0 + math.log1p(rps))
        if covariance > 0.0:
            computed_weight *= (1.0 + min(covariance, 2.0))
        self.graph.add_edge(
            from_service_id,
            to_service_id,
            weight=round(computed_weight, 4),
            rps=rps,
            covariance=covariance,
        )

    def get_edge_weight(self, from_service_id: str, to_service_id: str) -> float:
        """Return dynamic edge weight or default 1.0."""
        if self.graph.has_edge(from_service_id, to_service_id):
            return float(self.graph[from_service_id][to_service_id].get("weight", 1.0))
        return 1.0

    def get_upstream_services(self, service_id: str) -> set[str]:
        """Get services that depend on this service (predecessors: callers)."""
        if service_id not in self.graph:
            return set()
        return set(self.graph.predecessors(service_id))

    def get_downstream_services(self, service_id: str) -> set[str]:
        """Get services that this service depends on (successors: callees / dependencies)."""
        if service_id not in self.graph:
            return set()
        return set(self.graph.successors(service_id))

    def get_all_downstream_reach(self, service_id: str) -> set[str]:
        """Get all services reachable by walking forward from service_id (all transitive dependencies)."""
        if service_id not in self.graph:
            return set()
        return set(nx.descendants(self.graph, service_id))

    def get_all_upstream_callers(self, service_id: str) -> set[str]:
        """Get all services that transitively call / depend on service_id (all ancestors)."""
        if service_id not in self.graph:
            return set()
        return set(nx.ancestors(self.graph, service_id))

    def get_shortest_path_distance(self, source: str, target: str) -> int | None:
        """Return shortest path distance between two nodes, or None if unreachable."""
        try:
            return nx.shortest_path_length(self.graph, source, target)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

    def get_subgraph(self, service_ids: list[str] | set[str]) -> nx.DiGraph:
        """Extract induced subgraph containing only specified service IDs."""
        valid_ids = [sid for sid in service_ids if sid in self.graph]
        return self.graph.subgraph(valid_ids).copy()

    def get_weakly_connected_components(self, subgraph: nx.DiGraph | None = None) -> list[set[str]]:
        """Get connected components (treating edges as undirected) for incident separation."""
        target_g = subgraph if subgraph is not None else self.graph
        return [set(c) for c in nx.weakly_connected_components(target_g)]

    def has_cycles(self, subgraph: nx.DiGraph | None = None) -> bool:
        """Return True if the directed graph (or subgraph) contains at least one cycle."""
        target_g = subgraph if subgraph is not None else self.graph
        if len(target_g) == 0:
            return False
        return not nx.is_directed_acyclic_graph(target_g)

    def get_strongly_connected_components(self, subgraph: nx.DiGraph | None = None) -> list[set[str]]:
        """Return strongly connected components (SCCs) for cycle-safe condensation."""
        target_g = subgraph if subgraph is not None else self.graph
        return [set(c) for c in nx.strongly_connected_components(target_g)]

    def get_betweenness_centrality(self) -> dict[str, float]:
        """Calculate betweenness centrality for all nodes in the graph."""
        if len(self.graph) == 0:
            return {}
        return nx.betweenness_centrality(self.graph)

    def get_node_data(self, service_id: str) -> dict[str, Any]:
        """Get attributes dictionary for a service."""
        return self.graph.nodes.get(service_id, {})

