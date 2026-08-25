"""End-to-end integration tests for AIOps Root Cause Correlator API layer."""

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.dependencies import get_db, get_session_factory
from app.config import get_settings


@pytest.fixture
def client():
    return TestClient(app)


def test_full_incident_lifecycle(client):
    """Test full pipeline lifecycle from service registration to correlation, explain, and runbook approval."""
    # 1. Health check
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "healthy"

    # 2. Register 3 microservices: api-gateway, order-service, payment-service
    s1 = client.post("/api/v1/services", json={"name": "integ-gateway", "revenue_weight": 10.0}).json()
    s2 = client.post("/api/v1/services", json={"name": "integ-order", "revenue_weight": 8.0}).json()
    s3 = client.post("/api/v1/services", json={"name": "integ-payment", "revenue_weight": 9.0}).json()

    s1_id, s2_id, s3_id = s1["id"], s2["id"], s3["id"]

    # 3. Add dependencies: gateway -> order -> payment
    client.post("/api/v1/services/dependencies", json={"from_service_id": s1_id, "to_service_id": s2_id})
    client.post("/api/v1/services/dependencies", json={"from_service_id": s2_id, "to_service_id": s3_id})

    # 4. Verify graph
    graph_res = client.get("/api/v1/services/graph").json()
    assert len(graph_res["nodes"]) >= 3
    assert len(graph_res["edges"]) >= 2

    # 5. Ingest normal telemetry (burn in EWMA)
    t0 = datetime.now(timezone.utc)
    for _ in range(4):
        client.post("/api/v1/detection/ingest", json={
            "service_id": s3_id, "metric_type": "connection_pool", "value": 20.0, "recorded_at": t0.isoformat()
        })
        client.post("/api/v1/detection/ingest", json={
            "service_id": s2_id, "metric_type": "latency_ms", "value": 45.0, "recorded_at": t0.isoformat()
        })

    # 6. Ingest catastrophic anomalies
    t1 = t0 + timedelta(seconds=10)
    anom_pay = client.post("/api/v1/detection/ingest", json={
        "service_id": s3_id, "metric_type": "connection_pool", "value": 350.0, "recorded_at": t1.isoformat()
    }).json()
    assert anom_pay["anomaly_detected"] is True

    t2 = t1 + timedelta(seconds=10)
    anom_ord = client.post("/api/v1/detection/ingest", json={
        "service_id": s2_id, "metric_type": "latency_ms", "value": 450.0, "recorded_at": t2.isoformat()
    }).json()
    assert anom_ord["anomaly_detected"] is True

    # 7. Run correlation
    corr_res = client.post("/api/v1/correlation/run").json()
    assert len(corr_res["incidents"]) >= 1
    incident = next((i for i in corr_res["incidents"] if i["root_cause_service_id"] == s3_id), corr_res["incidents"][0])
    inc_id = incident["incident_id"]

    assert incident["root_cause_service_id"] == s3_id
    assert incident["confidence"] > 0.70

    # 8. Fetch incident detail
    detail = client.get(f"/api/v1/correlation/incidents/{inc_id}").json()
    assert detail["id"] == inc_id
    assert detail["root_cause_service_name"] == "integ-payment"
    assert len(detail["affected_services"]) >= 1

    # 9. Get blast radius predictions
    blast = client.get(f"/api/v1/prediction/blast-radius/{inc_id}").json()
    assert "predictions" in blast

    # 10. Run counterfactual simulation
    cf_res = client.post("/api/v1/counterfactual/simulate", json={
        "incident_id": inc_id,
        "modified_parameter": {
            "service": "integ-payment",
            "metric": "connection_pool",
            "capped_at": 1.0,
        }
    }).json()
    assert cf_res["would_cascade"] is False

    # 11. Get business impact score
    impact = client.get(f"/api/v1/impact/{inc_id}").json()
    assert impact["impact_score"] > 0.0

    # 12. Runbook lookup & human-in-the-loop approval
    rb = client.get(f"/api/v1/runbook/{detail['root_cause_type']}").json()
    assert len(rb["steps"]) > 0

    appr = client.post(f"/api/v1/runbook/{inc_id}/approve").json()
    assert appr["status"] == "approved"

    # 13. Generate structured AI explanation
    exp = client.post(f"/api/v1/explain/{inc_id}").json()
    assert "integ-payment" in exp["summary"]
    assert len(exp["evidence"]) >= 3

    # 14. Run benchmark evaluation endpoint
    eval_res = client.post("/api/v1/eval/run-scenarios").json()
    assert eval_res["total_scenarios"] == 30
    assert eval_res["top1_accuracy"] == 1.0
