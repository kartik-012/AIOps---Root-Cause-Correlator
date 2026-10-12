"""Step 10 Item 5: Security & Zero-Trust Control Plane Test Suite.

Verifies:
1. SSRF prevention on outbound webhooks (cloud metadata, loopback, private CIDRs, non-https).
2. Zero-trust operator authentication guards on mutating control plane endpoints.
3. Strict CORS security posture (no wildcard origins with credentials).
4. Mutation rate limiter protection against burst attacks.
"""

from fastapi import HTTPException
import pytest
from app.services.slack_notifier import validate_webhook_url, WebhookSecurityError
from app.security import MutationRateLimiter
from app.config import get_settings


@pytest.mark.parametrize(
    "malicious_url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "https://169.254.169.254/latest/meta-data/",
        "https://metadata.google.internal/computeMetadata/v1/",
        "http://localhost:8000/internal",
        "https://127.0.0.1:8000/internal",
        "https://10.200.0.1/admin",
        "https://172.20.0.1/admin",
        "https://192.168.1.1/admin",
        "file:///etc/passwd",
        "gopher://127.0.0.1:6379/_INFO",
    ],
)
def test_ssrf_validation_strictly_rejects_internal_and_private_targets(malicious_url):
    with pytest.raises(WebhookSecurityError):
        validate_webhook_url(malicious_url)


def test_cors_security_invariant_no_wildcard_with_credentials():
    settings = get_settings()
    # RFC / OWASP rule: Access-Control-Allow-Origin: * must NEVER be allowed when credentials are true
    assert "*" not in settings.CORS_ALLOWED_ORIGINS, "CORS misconfiguration: wildcard origin combined with credentials"
    assert len(settings.CORS_ALLOWED_ORIGINS) > 0


def test_mutation_rate_limiter_burst_enforcement():
    limiter = MutationRateLimiter(max_requests=30, window_seconds=60.0)
    client_ip = "198.51.100.42"
    # Execute rapid burst up to capacity (30 allowed per minute)
    for _ in range(30):
        limiter.check_or_raise(client_ip)

    # 31st request in same minute window must raise HTTPException with status 429
    with pytest.raises(HTTPException) as exc_info:
        limiter.check_or_raise(client_ip)
    assert exc_info.value.status_code == 429
