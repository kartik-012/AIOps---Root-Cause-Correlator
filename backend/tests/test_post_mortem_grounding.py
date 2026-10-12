"""Tests for Evidence-Grounded Post-Mortem Synthesizer & Hallucination Guard (Fix #1)."""

from datetime import datetime, timezone, timedelta
import json
import httpx

from app.services.llm_report_generator import (
    LLMReportGenerator,
    AnomalyEvidenceItem,
)


def test_deterministic_mode_honest_metadata_and_dynamic_mttd():
    """Verify deterministic synthesizer computes real MTTD & revenue exposure without fake LLM claims."""
    gen = LLMReportGenerator(api_key=None)
    t0 = datetime(2026, 10, 12, 10, 0, 0, tzinfo=timezone.utc)
    t_detected = t0 + timedelta(seconds=3.25)
    t_end = t0 + timedelta(minutes=20)

    anomalies = [
        AnomalyEvidenceItem(
            anomaly_id="anom-1",
            service_name="payment-service",
            metric_type="connection_pool",
            z_score=5.4,
            severity="critical",
            detected_at=t0,
        ),
        AnomalyEvidenceItem(
            anomaly_id="anom-2",
            service_name="order-service",
            metric_type="latency_ms",
            z_score=3.8,
            severity="high",
            detected_at=t0 + timedelta(seconds=2.5),
        ),
    ]

    report = gen.generate_post_mortem(
        incident_id="inc-test-001",
        root_cause_service="payment-service",
        root_cause_type="db_connection_exhaustion",
        confidence=0.94,
        affected_services=["order-service", "api-gateway"],
        impact_score=80.0,
        timestamp_start=t0,
        timestamp_detected=t_detected,
        timestamp_end=t_end,
        anomalies=anomalies,
        total_revenue_weight=29.0,  # payment(10) + order(9) + gateway(10)
    )

    assert report["generation_mode"] == "deterministic_evidence_synthesizer"
    assert report["grounding_verified"] is True
    assert report["mttd_seconds"] == 3.25
    assert report["mttd"] == "3.25s"
    assert report["mttr"] == "20m"
    # 29.0 weight * 20 min * $150/weight-min * 0.80 impact = $69,600
    assert report["financial_exposure"] == "$69,600"
    assert len(report["evidence_citations"]) == 3
    assert "[EVID-1]" in report["markdown"]
    assert "payment-service" in report["markdown"]


def test_grounding_validator_accepts_valid_and_rejects_hallucinated_services():
    """Verify validate_grounding catches hallucinated microservice names and missing root causes."""
    valid_md = (
        "Root cause isolated to `payment-service` [EVID-1], which cascaded upstream "
        "to `order-service` and `api-gateway`."
    )
    res_ok = LLMReportGenerator.validate_grounding(
        markdown_text=valid_md,
        root_cause_service="payment-service",
        allowed_services=["order-service", "api-gateway"],
    )
    assert res_ok.is_valid is True
    assert res_ok.hallucinated_services == []

    # Case 2: LLM invents 'kafka-billing-service' and 'redis-cache-proxy' not in topology
    hallucinated_md = (
        "The outage started in `payment-service` [EVID-1] and corrupted "
        "`kafka-billing-service` as well as `redis-cache-proxy`."
    )
    res_bad = LLMReportGenerator.validate_grounding(
        markdown_text=hallucinated_md,
        root_cause_service="payment-service",
        allowed_services=["order-service", "api-gateway"],
    )
    assert res_bad.is_valid is False
    assert "kafka-billing-service" in res_bad.hallucinated_services
    assert "redis-cache-proxy" in res_bad.hallucinated_services

    # Case 3: LLM omits the true root cause service entirely
    missing_root_md = "An outage occurred in `order-service` and `api-gateway`."
    res_missing = LLMReportGenerator.validate_grounding(
        markdown_text=missing_root_md,
        root_cause_service="payment-service",
        allowed_services=["order-service", "api-gateway"],
    )
    assert res_missing.is_valid is False
    assert res_missing.missing_root_cause is True


def test_llm_grounded_mode_with_mocked_provider_accepted():
    """Verify real LLM HTTP call succeeds when output passes grounding validation."""
    grounded_llm_markdown = (
        "# Executive Post-Mortem\n"
        "Root cause was isolated to `payment-service` due to DB Connection Exhaustion ([EVID-1]). "
        "Upstream callers `order-service` and `api-gateway` experienced cascading timeouts ([EVID-2])."
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": grounded_llm_markdown}}
                ]
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    gen = LLMReportGenerator(
        api_key="sk-test-key",
        provider="openai",
        model="gpt-4o-mini",
        http_client=mock_client,
    )

    report = gen.generate_post_mortem(
        incident_id="inc-llm-ok",
        root_cause_service="payment-service",
        root_cause_type="db_connection_exhaustion",
        confidence=0.95,
        affected_services=["order-service", "api-gateway"],
        impact_score=87.0,
    )

    assert report["generation_mode"] == "llm_grounded"
    assert report["model_used"] == "openai:gpt-4o-mini"
    assert report["grounding_verified"] is True
    assert report["markdown"] == grounded_llm_markdown


def test_llm_hallucination_rejected_and_falls_back_to_deterministic():
    """Verify that if the LLM hallucinates an unverified service, output is rejected and falls back safely."""
    ungrounded_llm_markdown = (
        "# Executive Post-Mortem\n"
        "The outage in `payment-service` was triggered by `quantum-ledger-service` failing."
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": ungrounded_llm_markdown}}
                ]
            },
        )

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))
    gen = LLMReportGenerator(
        api_key="sk-test-key",
        provider="openai",
        model="gpt-4o-mini",
        http_client=mock_client,
    )

    report = gen.generate_post_mortem(
        incident_id="inc-llm-hallucinated",
        root_cause_service="payment-service",
        root_cause_type="db_connection_exhaustion",
        confidence=0.95,
        affected_services=["order-service", "api-gateway"],
        impact_score=87.0,
    )

    # Must reject the hallucinated LLM output and fall back to deterministic synthesizer
    assert report["generation_mode"] == "deterministic_evidence_synthesizer"
    assert report["grounding_verified"] is False
    assert "quantum-ledger-service" in report["grounding_notes"]
    assert "quantum-ledger-service" not in report["markdown"]
    assert "Deterministic Evidence Synthesizer" in report["markdown"]
