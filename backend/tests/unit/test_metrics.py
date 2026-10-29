"""Unit tests for Prometheus metrics scraping endpoint."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.metrics import ANOMALIES_DETECTED_TOTAL, ACTIVE_INCIDENTS_GAUGE


@pytest.fixture
def client():
    return TestClient(app)


def test_metrics_endpoint_returns_prometheus_format(client):
    """Test that /metrics returns valid text format with expected metrics."""
    # Increment counter
    ANOMALIES_DETECTED_TOTAL.labels(service_id="payment-service", metric_type="connection_pool", severity="critical").inc()
    ACTIVE_INCIDENTS_GAUGE.set(2)

    response = client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    text = response.text

    assert "aiops_anomalies_detected_total" in text
    assert 'service_id="payment-service"' in text
    assert "aiops_active_incidents 2.0" in text


def test_health_endpoint_returns_process_time_and_metadata(client):
    """Test that /health returns X-Process-Time-Ms header and system version metadata."""
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-Process-Time-Ms" in response.headers
    data = response.json()
    assert data["status"] == "healthy"
    assert data["version"] == "1.2.0"
    assert "timestamp" in data
