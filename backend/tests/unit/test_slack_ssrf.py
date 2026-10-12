"""Security unit tests for Multi-Layer SSRF Protection in SlackNotifier."""

import socket
import pytest
import httpx

from app.services.slack_notifier import (
    SlackNotifier,
    WebhookSecurityError,
    validate_webhook_url,
    _is_non_public_ip,
)


@pytest.mark.parametrize(
    "malicious_url",
    [
        # 1. Cloud metadata endpoints (AWS IMDS, GCP metadata)
        "http://169.254.169.254/latest/meta-data/iam/security-credentials/",
        "https://169.254.169.254/latest/meta-data/",
        "https://metadata.google.internal/computeMetadata/v1/",
        # 2. Loopback & RFC1918 internal networks
        "https://127.0.0.1/services/T00/B00/X00",
        "https://localhost/services/T00/B00/X00",
        "https://10.0.0.15/services/T00/B00/X00",
        "https://172.16.0.5/services/T00/B00/X00",
        "https://192.168.1.10/services/T00/B00/X00",
        "https://[::1]/services/T00/B00/X00",
        # 3. Non-HTTPS schemes
        "http://hooks.slack.com/services/T000/B000/XXXX",
        "file:///etc/passwd",
        "gopher://127.0.0.1:6379/_INFO",
        # 4. Credential confusion & non-443 port smuggling
        "https://hooks.slack.com@169.254.169.254/services/T000/B000/XXXX",
        "https://hooks.slack.com:8443/services/T000/B000/XXXX",
        # 5. Unapproved external domains & path traversal
        "https://evil-exfil.example.com/services/T000/B000/XXXX",
        "https://hooks.slack.com/api/admin",
        "https://hooks.slack.com/services/../admin",
    ],
)
def test_ssrf_blocks_malicious_webhook_urls(malicious_url: str):
    with pytest.raises(WebhookSecurityError):
        validate_webhook_url(malicious_url, resolve_dns=False)


def test_ssrf_blocks_dns_rebinding_to_private_or_metadata_ips(monkeypatch):
    """Even if the hostname is hooks.slack.com, DNS rebinding to 169.254.169.254 or 127.0.0.1 must be blocked."""

    def fake_getaddrinfo_metadata(host, port, type=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo_metadata)

    with pytest.raises(WebhookSecurityError, match="non-public IP"):
        validate_webhook_url("https://hooks.slack.com/services/T000/B000/XXXX", resolve_dns=True)


def test_ssrf_allows_valid_slack_and_discord_webhooks_with_public_dns(monkeypatch):
    """Valid Slack and Discord webhook URLs resolving to public global IPs must pass."""

    def fake_getaddrinfo_public(host, port, type=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("52.94.236.248", 443))]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo_public)

    slack_url = "https://hooks.slack.com/services/T12345/B12345/SecretToken123"
    discord_url = "https://discord.com/api/webhooks/123456789/WebhookTokenAbc"

    assert validate_webhook_url(slack_url, resolve_dns=True) == slack_url
    assert validate_webhook_url(discord_url, resolve_dns=True) == discord_url


def test_ipv4_mapped_ipv6_loopback_and_metadata_detected():
    assert _is_non_public_ip("::ffff:127.0.0.1") is True
    assert _is_non_public_ip("::ffff:169.254.169.254") is True
    assert _is_non_public_ip("8.8.8.8") is False


@pytest.mark.asyncio
async def test_slack_notifier_prevents_full_read_response_exfiltration(monkeypatch):
    """Verify SlackNotifier disables redirects and never echoes raw upstream response text."""
    captured_kwargs = {}

    class DummyResponse:
        status_code = 200
        text = "SENSITIVE_INTERNAL_SECRET_BODY_DO_NOT_ECHO"

    class DummyAsyncClient:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, json=None):
            return DummyResponse()

    monkeypatch.setattr(httpx, "AsyncClient", DummyAsyncClient)

    notifier = SlackNotifier(resolve_dns=False)
    res = await notifier.send_incident_alert(
        incident_id="inc-ssrf-test",
        root_cause_service="payment",
        root_cause_type="db_pool_exhaustion",
        confidence=0.92,
        affected_services=["order", "api-gateway"],
        impact_score=85.0,
        webhook_url="https://hooks.slack.com/services/T123/B456/Token789",
    )

    assert captured_kwargs.get("follow_redirects") is False
    assert res["status"] == "delivered"
    assert res["delivery_ack"] == "accepted"
    assert "response" not in res
    assert "SENSITIVE_INTERNAL_SECRET_BODY_DO_NOT_ECHO" not in str(res)


def test_slack_webhook_endpoint_returns_http_422_for_loopback_and_metadata_urls():
    """Verify Gap #1 verification method: POST /api/v1/integrations/slack/webhook
    with http://127.0.0.1:8000 and http://169.254.169.254 asserts HTTP 422.
    """
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    for forbidden_url in ("http://127.0.0.1:8000", "http://169.254.169.254"):
        resp = client.post(
            "/api/v1/integrations/slack/webhook",
            json={"incident_id": "inc-default", "webhook_url": forbidden_url},
        )
        assert resp.status_code == 422, f"Expected HTTP 422 for {forbidden_url}, got {resp.status_code}"

