"""Unit tests for Integrations: Slack Alerts, LLM Post-Mortem, and OpenTelemetry ingestion."""

import pytest
from app.services.slack_notifier import SlackNotifier
from app.services.llm_report_generator import LLMReportGenerator


@pytest.mark.asyncio
async def test_slack_notifier_payload_generation():
    notifier = SlackNotifier()
    res = await notifier.send_incident_alert(
        incident_id="test-inc-123",
        root_cause_service="payment-service",
        root_cause_type="db_connection_exhaustion",
        confidence=0.94,
        affected_services=["order-service", "api-gateway"],
        impact_score=87.0,
    )
    assert res["status"] == "simulated"
    payload = res["payload"]
    assert "payment-service" in payload["text"]
    assert len(payload["blocks"]) >= 4


def test_llm_post_mortem_generator():
    generator = LLMReportGenerator()
    report = generator.generate_post_mortem(
        incident_id="test-inc-456",
        root_cause_service="payment-service",
        root_cause_type="db_connection_exhaustion",
        confidence=0.95,
        affected_services=["order-service", "api-gateway"],
        impact_score=88.0,
    )
    assert "INCIDENT POST-MORTEM REPORT" in report["markdown"]
    assert "payment-service" in report["markdown"]
    assert report["mttd"] == "0.78s"
    assert "$36,960" in report["financial_exposure"]
