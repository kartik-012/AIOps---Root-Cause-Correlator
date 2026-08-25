"""Service registry and topology graph endpoints."""

import uuid
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import DBSession
from app.models.db_models import Service, ServiceDependency
from app.models.schemas import ServiceOut, ServiceCreate, DependencyCreate, GraphResponse, GraphNode, GraphEdge

router = APIRouter()


@router.get("/services", response_model=list[ServiceOut])
def list_services(db: DBSession):
    """List all registered microservices."""
    services = db.scalars(select(Service).order_by(Service.name)).all()
    return services


@router.post("/services", response_model=ServiceOut)
def create_service(payload: ServiceCreate, db: DBSession):
    """Register a new microservice."""
    existing = db.scalar(select(Service).where(Service.name == payload.name))
    if existing:
        return existing
    svc = Service(name=payload.name, revenue_weight=payload.revenue_weight)
    db.add(svc)
    db.commit()
    db.refresh(svc)
    return svc


@router.post("/services/dependencies")
def create_dependency(payload: DependencyCreate, db: DBSession):
    """Add a directed dependency edge: from_service calls to_service."""
    existing = db.scalar(
        select(ServiceDependency).where(
            ServiceDependency.from_service_id == payload.from_service_id,
            ServiceDependency.to_service_id == payload.to_service_id,
        )
    )
    if existing:
        return {"status": "exists", "id": str(existing.id)}
    dep = ServiceDependency(
        from_service_id=payload.from_service_id,
        to_service_id=payload.to_service_id,
    )
    db.add(dep)
    db.commit()
    return {"status": "created", "id": str(dep.id)}


@router.get("/services/graph", response_model=GraphResponse)
def get_service_graph(db: DBSession):
    """Return the complete topology graph with nodes and directed edges."""
    services = db.scalars(select(Service)).all()
    deps = db.scalars(select(ServiceDependency)).all()

    nodes = [
        GraphNode(id=s.id, name=s.name, revenue_weight=s.revenue_weight)
        for s in services
    ]
    edges = [
        GraphEdge(source=d.from_service_id, target=d.to_service_id)
        for d in deps
    ]

    return GraphResponse(nodes=nodes, edges=edges)
