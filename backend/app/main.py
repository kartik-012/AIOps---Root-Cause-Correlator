from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
)
from app.dependencies import get_session_factory
from app.models.db_models import Service, ServiceDependency

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

    yield


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


# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(ws.router, prefix=prefix, tags=["WebSocket"])
app.include_router(ws.router, tags=["WebSocket Direct"])


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }
