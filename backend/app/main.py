from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from strawberry.fastapi import GraphQLRouter

from app.config import get_settings
from app.api.v1 import (
    services,
    detection,
    correlation,
    incidents,
    prediction,
    counterfactual,
    explain,
    impact,
    suppression,
    runbook,
    evaluation,
    ws,
    chaos,
    integrations,
    kafka_ingest,
    diagnostics,
)
from app.dependencies import get_session_factory
from app.models.db_models import Service, ServiceDependency
from app.kafka import get_kafka_producer
from app.kafka.consumers import TelemetryConsumer, AuditConsumer
from app.graphql import schema as graphql_schema

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager with automatic DB auto-seeding."""
    try:
        session_factory = get_session_factory(settings)
        with session_factory() as session:
            count = session.query(Service).count()
            if count == 0:
                services_def = [
                    ("api-gateway", 10.0),
                    ("auth-service", 7.0),
                    ("product-catalog", 6.0),
                    ("inventory-service", 8.0),
                    ("order-service", 9.0),
                    ("payment-service", 10.0),
                    ("notification-service", 3.0),
                    ("shipping-service", 4.0),
                ]
                svc_objs = {}
                for name, weight in services_def:
                    s = Service(name=name, revenue_weight=weight)
                    session.add(s)
                    session.flush()
                    svc_objs[name] = s

                deps_def = [
                    ("api-gateway", "auth-service"),
                    ("api-gateway", "product-catalog"),
                    ("product-catalog", "inventory-service"),
                    ("api-gateway", "order-service"),
                    ("order-service", "payment-service"),
                    ("order-service", "inventory-service"),
                    ("order-service", "notification-service"),
                    ("order-service", "shipping-service"),
                ]
                for src, tgt in deps_def:
                    dep = ServiceDependency(from_service_id=svc_objs[src].id, to_service_id=svc_objs[tgt].id)
                    session.add(dep)

                session.commit()
                print("[AIOps Startup] Successfully auto-seeded 8-microservice topology into PostgreSQL!")
    except Exception as e:
        print(f"[AIOps Startup] Note: Could not auto-seed database: {e}")

    embedded_grpc = None
    try:
        from app.grpc_services.diagnostic_server import start_embedded_grpc_server

        embedded_grpc = start_embedded_grpc_server(port=50051)
        app.state.embedded_grpc = embedded_grpc
    except Exception as e:
        print(f"[AIOps Startup] Note: Could not start embedded gRPC loopback server: {e}")

    try:
        producer = get_kafka_producer()
        await producer.start()
        
        telemetry_consumer = TelemetryConsumer()
        audit_consumer = AuditConsumer()
        await telemetry_consumer.start()
        await audit_consumer.start()
        app.state.telemetry_consumer = telemetry_consumer
        app.state.audit_consumer = audit_consumer
    except Exception as e:
        print(f"[AIOps Startup] Note: Could not start Kafka: {e}")

    yield
    
    if embedded_grpc is not None:
        try:
            embedded_grpc.stop(grace=1.0)
        except Exception:
            pass

    try:
        producer = get_kafka_producer()
        await producer.stop()
        if hasattr(app.state, "telemetry_consumer"):
            await app.state.telemetry_consumer.stop()
        if hasattr(app.state, "audit_consumer"):
            await app.state.audit_consumer.stop()
    except Exception as e:
        print(f"[AIOps Shutdown] Note: Error stopping Kafka: {e}")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "AI-powered incident correlation and root-cause analysis "
        "for distributed microservices."
    ),
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# CORS — explicit origin allowlist (never combine wildcard '*' with allow_credentials=True)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "Accept"],
)

@app.middleware("http")
async def add_process_time_header(request, call_next):
    """Inject high-resolution latency header into HTTP response for SRE observability."""
    import time
    start_time = time.perf_counter()
    response = await call_next(request)
    process_time_ms = (time.perf_counter() - start_time) * 1000.0
    response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"
    return response


# Mount all v1 routers
prefix = settings.API_V1_PREFIX
app.include_router(services.router, prefix=prefix, tags=["Services"])
app.include_router(detection.router, prefix=prefix, tags=["Detection"])
app.include_router(correlation.router, prefix=prefix, tags=["Correlation"])
app.include_router(incidents.router, prefix=prefix, tags=["Incidents"])
app.include_router(prediction.router, prefix=prefix, tags=["Prediction"])
app.include_router(counterfactual.router, prefix=prefix, tags=["Counterfactual"])
app.include_router(explain.router, prefix=prefix, tags=["Explain"])
app.include_router(impact.router, prefix=prefix, tags=["Impact"])
app.include_router(suppression.router, prefix=prefix, tags=["Suppression"])
app.include_router(runbook.router, prefix=prefix, tags=["Runbook"])
app.include_router(evaluation.router, prefix=prefix, tags=["Evaluation"])
app.include_router(chaos.router, prefix=prefix, tags=["Chaos Studio"])
app.include_router(integrations.router, prefix=prefix, tags=["Integrations"])
app.include_router(kafka_ingest.router, prefix=prefix, tags=["Kafka Ingest"])
app.include_router(diagnostics.router, prefix=prefix, tags=["Diagnostics"])
app.include_router(ws.router, prefix=prefix, tags=["WebSocket"])
app.include_router(ws.router, tags=["WebSocket Direct"])

# Mount GraphQL endpoint with subscriptions support
graphql_app = GraphQLRouter(graphql_schema, subscription_protocols=["graphql-transport-ws", "graphql-ws"])
app.include_router(graphql_app, prefix="/graphql", tags=["GraphQL Control Plane"])


@app.get("/", tags=["Health"])
def root():
    """Root welcoming endpoint with API links."""
    return {
        "service": settings.PROJECT_NAME,
        "status": "online",
        "version": settings.VERSION,
        "docs": "/docs",
        "graphql": "/graphql",
        "health": "/health",
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint with UTC ISO timestamp and environment metadata."""
    from datetime import datetime, timezone

    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": getattr(settings, "ENVIRONMENT", "production"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/metrics", tags=["Observability"])
def prometheus_metrics():
    """Prometheus scraping endpoint exposing custom SRE metrics."""
    from app.metrics import get_metrics_response
    return get_metrics_response()
