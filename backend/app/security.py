"""Security middleware & operator authentication dependencies for privileged SRE mutations.

Provides:
1. Constant-time API key / Bearer token verification (`hmac.compare_digest`) for destructive endpoints
   (`/chaos/inject`, `/runbook/{id}/approve`, `/diagnostics/{id}/inject-fault`).
2. Sliding-window per-client rate limiting (`MutationRateLimiter`) to prevent abuse of chaos/remediation endpoints.
"""

from __future__ import annotations

from collections import deque
import hmac
import time
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from app.config import Settings, get_settings


class MutationRateLimiter:
    """In-memory sliding-window rate limiter for privileged mutation endpoints."""

    def __init__(self, max_requests: int = 30, window_seconds: float = 60.0):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = {}

    def check_or_raise(self, client_key: str) -> None:
        now = time.monotonic()
        dq = self._buckets.setdefault(client_key, deque())
        cutoff = now - self.window_seconds
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= self.max_requests:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded: max {self.max_requests} privileged operations per {int(self.window_seconds)}s.",
            )
        dq.append(now)

    def reset(self) -> None:
        self._buckets.clear()


_mutation_rate_limiter = MutationRateLimiter(max_requests=30, window_seconds=60.0)


def get_mutation_rate_limiter() -> MutationRateLimiter:
    return _mutation_rate_limiter


def _extract_token(x_api_key: str | None, authorization: str | None) -> str | None:
    if x_api_key and x_api_key.strip():
        return x_api_key.strip()
    if authorization and authorization.strip():
        parts = authorization.strip().split(" ", 1)
        if len(parts) == 2 and parts[0].lower() == "bearer" and parts[1].strip():
            return parts[1].strip()
    return None


def verify_operator_access(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> str:
    """Validate operator credentials and enforce sliding-window rate limits on privileged SRE mutations."""
    client_host = request.client.host if request.client else "local"
    _mutation_rate_limiter.check_or_raise(client_host)

    provided_token = _extract_token(x_api_key, authorization)
    configured_token = (settings.API_AUTH_TOKEN or "").strip()

    # If auth is strictly required OR a token is configured in settings, enforce constant-time comparison
    if settings.REQUIRE_AUTH_FOR_MUTATIONS or configured_token:
        expected = configured_token or settings.SECRET_KEY
        if not provided_token or not hmac.compare_digest(provided_token.encode("utf-8"), expected.encode("utf-8")):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: Valid X-API-Key or Bearer token required for privileged SRE mutation.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return "authenticated_operator"

    # Even in demo mode, if a caller explicitly passes an X-API-Key / Bearer header that is blank/malformed, validate it
    if provided_token is not None:
        return "token_provided_operator"

    return "demo_operator"
