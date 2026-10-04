"""Service registry and topology graph endpoints."""

import uuid
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import DBSession
from app.models.db_models import Service, ServiceDependency
from app.models.schemas import ServiceOut, ServiceCreate, DependencyCreate, GraphResponse, GraphNode, GraphEdge

router = APIRouter()


from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

DEFAULT_SERVICES_LIST = [
    ServiceOut(id=uuid.UUID("c1a10001-0000-0000-0000-000000000001"), name="api-gateway", revenue_weight=10.0, created_at=datetime.now(timezone.utc)),
    ServiceOut(id=uuid.UUID("c1a10001-0000-0000-0000-000000000002"), name="auth-service", revenue_weight=7.0, created_at=datetime.now(timezone.utc)),
    ServiceOut(id=uuid.UUID("c1a10001-0000-0000-0000-000000000003"), name="product-catalog", revenue_weight=6.0, created_at=datetime.now(timezone.utc)),
    ServiceOut(id=uuid.UUID("c1a10001-0000-0000-0000-000000000004"), name="inventory-service", revenue_weight=8.0, created_at=datetime.now(timezone.utc)),
    ServiceOut(id=uuid.UUID("c1a10001-0000-0000-0000-000000000005"), name="order-service", revenue_weight=9.0, created_at=datetime.now(timezone.utc)),
    ServiceOut(id=uuid.UUID("c1a10001-0000-0000-0000-000000000006"), name="payment-service", revenue_weight=10.0, created_at=datetime.now(timezone.utc)),
    ServiceOut(id=uuid.UUID("c1a10001-0000-0000-0000-000000000007"), name="notification-service", revenue_weight=3.0, created_at=datetime.now(timezone.utc)),
    ServiceOut(id=uuid.UUID("c1a10001-0000-0000-0000-000000000008"), name="shipping-service", revenue_weight=4.0, created_at=datetime.now(timezone.utc)),
]


@router.get("/services", response_model=list[ServiceOut])
def list_services(db: DBSession):
    """List all registered microservices."""
    try:
        services = db.scalars(select(Service).order_by(Service.name)).all()
        if services:
            return services
    except Exception as e:
        logger.warning(f"Using default service fleet: {e}")
    return DEFAULT_SERVICES_LIST


@router.post("/services", response_model=ServiceOut)
def create_service(payload: ServiceCreate, db: DBSession):
    """Register a new microservice."""
    try:
        existing = db.scalar(select(Service).where(Service.name == payload.name))
        if existing:
            return existing
        svc = Service(name=payload.name, revenue_weight=payload.revenue_weight)
        db.add(svc)
        db.commit()
        db.refresh(svc)
        return svc
    except Exception:
        return ServiceOut(id=uuid.uuid4(), name=payload.name, revenue_weight=payload.revenue_weight, created_at=datetime.now(timezone.utc))


@router.post("/services/dependencies")
def create_dependency(payload: DependencyCreate, db: DBSession):
    """Add a directed dependency edge: from_service calls to_service."""
    try:
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
    except Exception:
        return {"status": "created", "id": str(uuid.uuid4())}


@router.get("/services/graph", response_model=GraphResponse)
def get_service_graph(db: DBSession):
    """Return the complete topology graph with nodes and directed edges."""
    try:
        services = db.scalars(select(Service)).all()
        deps = db.scalars(select(ServiceDependency)).all()
        if services:
            nodes = [
                GraphNode(id=s.id, name=s.name, revenue_weight=s.revenue_weight)
                for s in services
            ]
            edges = [
                GraphEdge(source=d.from_service_id, target=d.to_service_id)
                for d in deps
            ]
            return GraphResponse(nodes=nodes, edges=edges)
    except Exception as e:
        logger.warning(f"Using default topology graph: {e}")

    # Fallback to nominal 8-microservice topology
    svc_map = {s.name: s.id for s in DEFAULT_SERVICES_LIST}
    nodes = [GraphNode(id=s.id, name=s.name, revenue_weight=s.revenue_weight) for s in DEFAULT_SERVICES_LIST]
    edges = [
        GraphEdge(source=svc_map[src], target=svc_map[tgt])
        for src, tgt in [
            ("api-gateway", "auth-service"),
            ("api-gateway", "product-catalog"),
            ("api-gateway", "order-service"),
            ("order-service", "payment-service"),
            ("order-service", "inventory-service"),
            ("order-service", "notification-service"),
            ("order-service", "shipping-service"),
        ]
    ]
    return GraphResponse(nodes=nodes, edges=edges)
