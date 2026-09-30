"""Unit tests for Strawberry GraphQL endpoint."""

import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_graphql_incident_query(client):
    """Test GraphQL query for incident details matching spec."""
    query = """
    query {
      incident(id: "inc-sample-1") {
        id
        severity
        status
        rootCause {
          service
          component
          confidence
          verificationStatus
        }
        affectedServices {
          name
          errorRate
          latency
        }
        timeline {
          timestamp
          event
          severity
        }
      }
    }
    """
    response = client.post("/graphql", json={"query": query})
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert "incident" in data["data"]
    inc = data["data"]["incident"]
    assert inc["id"] is not None
    assert len(inc["id"]) > 0
    assert inc["rootCause"]["service"] is not None
    assert inc["rootCause"]["confidence"] > 0.0


def test_graphql_remediation_mutation(client):
    """Test proposing and approving a remediation plan via GraphQL mutation."""
    propose_mutation = """
    mutation {
      proposeRemediation(
        incidentId: "inc-1024",
        rootCauseType: "db_connection_exhaustion",
        targetService: "payment-service"
      ) {
        planId
        incidentId
        actionTitle
        riskLevel
        status
      }
    }
    """
    prop_res = client.post("/graphql", json={"query": propose_mutation})
    assert prop_res.status_code == 200
    prop_data = prop_res.json()["data"]["proposeRemediation"]
    plan_id = prop_data["planId"]
    assert prop_data["status"] == "PENDING_APPROVAL"
    assert "pool" in prop_data["actionTitle"].lower()

    # Now approve it
    approve_mutation = f"""
    mutation {{
      approveRemediation(planId: "{plan_id}", approver: "Lead SRE") {{
        planId
        status
        actionTitle
      }}
    }}
    """
    appr_res = client.post("/graphql", json={"query": approve_mutation})
    assert appr_res.status_code == 200
    appr_data = appr_res.json()["data"]["approveRemediation"]
    assert appr_data["status"] == "EXECUTED"
