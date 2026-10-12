"""Security unit tests for CORS policy, constant-time operator auth, rate limiting, and chaos scenario allowlisting."""

from types import SimpleNamespace
import pytest
from fastapi import HTTPException

from app.config import Settings
from app.security import MutationRateLimiter, verify_operator_access, get_mutation_rate_limiter
from app.api.v1.chaos import inject_chaos, ChaosInjectRequest


def _dummy_request(host: str = "127.0.0.1"):
    return SimpleNamespace(client=SimpleNamespace(host=host))


def test_cors_settings_never_combine_wildcard_with_credentials():
    """Verify CORS_ALLOWED_ORIGINS uses explicit origins and never '*'."""
    settings = Settings()
    assert "*" not in settings.CORS_ALLOWED_ORIGINS
    assert "http://localhost:5173" in settings.CORS_ALLOWED_ORIGINS


def test_verify_operator_access_enforces_token_when_configured():
    """Verify missing or mismatched token raises 401 when API_AUTH_TOKEN or REQUIRE_AUTH_FOR_MUTATIONS is active."""
    get_mutation_rate_limiter().reset()
    locked_settings = Settings(API_AUTH_TOKEN="sre-secret-token-2026", REQUIRE_AUTH_FOR_MUTATIONS=True)
    req = _dummy_request("10.10.1.5")

    # 1. Missing token -> 401
    with pytest.raises(HTTPException) as exc_info:
        verify_operator_access(request=req, settings=locked_settings, x_api_key=None, authorization=None)
    assert exc_info.value.status_code == 401

    # 2. Wrong token -> 401
    with pytest.raises(HTTPException) as exc_info2:
        verify_operator_access(request=req, settings=locked_settings, x_api_key="wrong-token", authorization=None)
    assert exc_info2.value.status_code == 401

    # 3. Valid X-API-Key -> passes
    role1 = verify_operator_access(
        request=req, settings=locked_settings, x_api_key="sre-secret-token-2026", authorization=None
    )
    assert role1 == "authenticated_operator"

    # 4. Valid Bearer token -> passes
    role2 = verify_operator_access(
        request=req,
        settings=locked_settings,
        x_api_key=None,
        authorization="Bearer sre-secret-token-2026",
    )
    assert role2 == "authenticated_operator"


def test_mutation_rate_limiter_blocks_excessive_bursts():
    """Verify sliding-window rate limiter raises HTTP 429 when burst threshold is exceeded."""
    limiter = MutationRateLimiter(max_requests=3, window_seconds=60.0)
    limiter.check_or_raise("192.0.2.99")
    limiter.check_or_raise("192.0.2.99")
    limiter.check_or_raise("192.0.2.99")

    with pytest.raises(HTTPException) as exc_info:
        limiter.check_or_raise("192.0.2.99")
    assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_chaos_inject_rejects_unapproved_scenario():
    """Verify inject_chaos rejects arbitrary scenario strings with HTTP 400."""
    with pytest.raises(HTTPException) as exc_info:
        await inject_chaos(
            payload=ChaosInjectRequest(scenario="drop_all_tables"),
            db=None,
            _operator="authenticated_operator",
        )
    assert exc_info.value.status_code == 400
    assert "Invalid chaos scenario" in exc_info.value.detail


def test_dockerfiles_enforce_multistage_non_root_and_healthcheck():
    """Verify backend/Dockerfile uses a multi-stage build, strips build-essential from runtime, and runs as non-root."""
    from pathlib import Path

    backend_dir = Path(__file__).resolve().parent.parent.parent
    dockerfile_text = (backend_dir / "Dockerfile").read_text(encoding="utf-8")
    grpc_dockerfile_text = (backend_dir / "app" / "grpc_services" / "Dockerfile.grpc").read_text(encoding="utf-8")

    # 1. Multi-stage builder + runtime stages
    assert "FROM python:3.12-slim AS builder" in dockerfile_text
    assert "FROM python:3.12-slim AS runtime" in dockerfile_text

    # 2. Runtime stage non-comment instructions must not install build-essential
    runtime_stage = dockerfile_text.split("FROM python:3.12-slim AS runtime", 1)[1]
    runtime_instructions = "\n".join(
        line for line in runtime_stage.splitlines() if not line.strip().startswith("#")
    )
    assert "build-essential" not in runtime_instructions
    assert "USER aiops" in runtime_instructions
    assert "HEALTHCHECK" in runtime_instructions

    # 3. gRPC Dockerfile must also run as non-root and define HEALTHCHECK
    assert "USER aiops" in grpc_dockerfile_text
    assert "HEALTHCHECK" in grpc_dockerfile_text

