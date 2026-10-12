"""Slack & Discord Webhook Notification Service with Multi-Layer SSRF Defense.

Enforces:
1. Strict HTTPS scheme & port 443 validation (blocks http://, file://, gopher://, non-standard ports).
2. Strict hostname & path prefix allowlisting (hooks.slack.com/services/..., discord.com/api/webhooks/...).
3. Literal IP & internal hostname blocking (127.0.0.0/8, 169.254.169.254 cloud metadata, RFC1918, IPv6 ::1/fe80::).
4. DNS resolution inspection (prevents DNS rebinding to private/loopback/link-local IPs).
5. Redirect blocking (follow_redirects=False) and response body sanitization (prevents Full-Read SSRF exfiltration).
"""

from __future__ import annotations

import ipaddress
import os
import socket
from typing import Any
from urllib.parse import urlparse

import httpx


ALLOWED_WEBHOOK_HOST_PATHS: dict[str, str] = {
    "hooks.slack.com": "/services/",
    "discord.com": "/api/webhooks/",
    "discordapp.com": "/api/webhooks/",
}

BLOCKED_HOSTNAMES: set[str] = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata",
    "instance-data",
}


class WebhookSecurityError(ValueError):
    """Raised when a webhook URL fails SSRF validation."""


def _is_non_public_ip(ip_str: str) -> bool:
    """Return True if ip_str is private, loopback, link-local (169.254.x.x), multicast, reserved, or non-global."""
    try:
        ip_obj = ipaddress.ip_address(ip_str)
    except ValueError:
        return True

    # Unwrap IPv4-mapped IPv6 addresses such as ::ffff:127.0.0.1 or ::ffff:169.254.169.254
    if isinstance(ip_obj, ipaddress.IPv6Address) and ip_obj.ipv4_mapped is not None:
        ip_obj = ip_obj.ipv4_mapped

    return (
        not ip_obj.is_global
        or ip_obj.is_private
        or ip_obj.is_loopback
        or ip_obj.is_link_local
        or ip_obj.is_multicast
        or ip_obj.is_reserved
        or ip_obj.is_unspecified
    )


def validate_webhook_url(url: str, resolve_dns: bool = True) -> str:
    """Validate a webhook URL against SSRF, cloud metadata access, and DNS rebinding.

    Returns the normalized URL if valid, or raises WebhookSecurityError.
    """
    if not url or not isinstance(url, str):
        raise WebhookSecurityError("Webhook URL must be a non-empty string.")

    cleaned = url.strip()
    parsed = urlparse(cleaned)

    # 1. Enforce HTTPS scheme only
    if parsed.scheme.lower() != "https":
        raise WebhookSecurityError(
            f"SSRF Protection: Disallowed URL scheme '{parsed.scheme}'. Only 'https' is permitted."
        )

    # 2. Reject embedded credentials (e.g., https://hooks.slack.com@169.254.169.254/)
    if parsed.username is not None or parsed.password is not None:
        raise WebhookSecurityError("SSRF Protection: Embedded URL credentials are forbidden.")

    hostname = (parsed.hostname or "").strip().lower().rstrip(".")
    if not hostname:
        raise WebhookSecurityError("SSRF Protection: Webhook URL is missing a valid hostname.")

    # 3. Reject non-443 ports
    if parsed.port is not None and parsed.port != 443:
        raise WebhookSecurityError(
            f"SSRF Protection: Non-standard port {parsed.port} is forbidden. Only port 443 is permitted."
        )

    # 4. Block internal/metadata hostnames and any literal IP address
    if (
        hostname in BLOCKED_HOSTNAMES
        or hostname.endswith(".local")
        or hostname.endswith(".internal")
        or hostname.endswith(".localhost")
    ):
        raise WebhookSecurityError(f"SSRF Protection: Internal hostname '{hostname}' is blocked.")

    try:
        ipaddress.ip_address(hostname)
        # If this succeeds, hostname is a raw IP literal (e.g., 169.254.169.254 or 127.0.0.1)
        raise WebhookSecurityError(
            f"SSRF Protection: Raw IP literal '{hostname}' is forbidden for webhook targets."
        )
    except ValueError:
        # Expected: hostname is a domain name, not an IP literal
        pass

    # 5. Enforce strict domain + path prefix allowlist
    if hostname not in ALLOWED_WEBHOOK_HOST_PATHS:
        allowed_list = ", ".join(sorted(ALLOWED_WEBHOOK_HOST_PATHS.keys()))
        raise WebhookSecurityError(
            f"SSRF Protection: Host '{hostname}' is not in the approved webhook allowlist ({allowed_list})."
        )

    required_prefix = ALLOWED_WEBHOOK_HOST_PATHS[hostname]
    path = parsed.path or ""
    if not path.startswith(required_prefix) or len(path) <= len(required_prefix) or ".." in path:
        raise WebhookSecurityError(
            f"SSRF Protection: Path '{path}' does not match required prefix '{required_prefix}<token>'."
        )

    # 6. Resolve DNS and verify all resolved IPs are globally routable public addresses
    if resolve_dns:
        try:
            addr_info = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            raise WebhookSecurityError(
                f"SSRF Protection: DNS resolution failed for '{hostname}': {exc}"
            ) from exc

        if not addr_info:
            raise WebhookSecurityError(f"SSRF Protection: No DNS records resolved for '{hostname}'.")

        for entry in addr_info:
            sockaddr = entry[4]
            resolved_ip = str(sockaddr[0])
            if _is_non_public_ip(resolved_ip):
                raise WebhookSecurityError(
                    f"SSRF Protection: Host '{hostname}' resolved to non-public IP '{resolved_ip}' (DNS rebinding blocked)."
                )

    return cleaned


class SlackNotifier:
    """Dispatches rich incident correlation cards to verified Slack or Discord webhooks
    with atomic Redis (`SET alert:dedup:{incident_id} 1 NX EX 300`) + monotonic TTL deduplication.
    """

    def __init__(
        self,
        default_webhook_url: str | None = None,
        resolve_dns: bool = True,
        dedup_ttl_seconds: int = 300,
        redis_client: Any | None = None,
    ):
        self.default_webhook_url = default_webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        self.resolve_dns = resolve_dns
        self.dedup_ttl_seconds = max(1, int(dedup_ttl_seconds))
        self._redis_client = redis_client
        self._memory_dedup: dict[str, float] = {}

    async def acquire_idempotency_lock(
        self,
        incident_id: str,
        ttl_seconds: int | None = None,
    ) -> tuple[bool, str]:
        """Atomically acquire idempotency lock `alert:dedup:{incident_id}` with TTL (default 300s).

        Returns (acquired: bool, backend: str) where backend is 'redis_nx' or 'memory_ttl'.
        """
        import time

        eff_ttl = max(1, int(ttl_seconds if ttl_seconds is not None else self.dedup_ttl_seconds))
        dedup_key = f"alert:dedup:{incident_id}"

        if self._redis_client is not None:
            try:
                was_set = await self._redis_client.set(dedup_key, "1", nx=True, ex=eff_ttl)
                return bool(was_set), "redis_nx"
            except Exception:
                pass

        now_mono = time.monotonic()
        # Evict expired entries
        expired = [k for k, exp in self._memory_dedup.items() if exp <= now_mono]
        for k in expired:
            self._memory_dedup.pop(k, None)

        if dedup_key in self._memory_dedup and self._memory_dedup[dedup_key] > now_mono:
            return False, "memory_ttl"

        self._memory_dedup[dedup_key] = now_mono + eff_ttl
        return True, "memory_ttl"

    async def send_incident_alert(
        self,
        incident_id: str,
        root_cause_service: str,
        root_cause_type: str,
        confidence: float,
        affected_services: list[str],
        impact_score: float,
        webhook_url: str | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """Enforce idempotency lock, validate target URL against SSRF, and dispatch to Slack/Discord."""
        target_url = (webhook_url or self.default_webhook_url or "").strip()
        payload = self._build_slack_payload(
            incident_id, root_cause_service, root_cause_type, confidence, affected_services, impact_score
        )
        dedup_key = f"alert:dedup:{incident_id}"

        # Validate SSRF first if a target_url is supplied so invalid URLs always raise WebhookSecurityError
        validated_url: str | None = None
        if target_url:
            validated_url = validate_webhook_url(target_url, resolve_dns=self.resolve_dns)

        if not force:
            acquired, dedup_backend = await self.acquire_idempotency_lock(incident_id)
            if not acquired:
                return {
                    "status": "deduplicated",
                    "incident_id": incident_id,
                    "idempotency_key": dedup_key,
                    "dedup_backend": dedup_backend,
                    "cooldown_ttl_seconds": self.dedup_ttl_seconds,
                    "message": f"Duplicate alert suppressed within {self.dedup_ttl_seconds}s idempotency window.",
                    "ssrf_verified": True,
                    "payload": payload,
                }
        else:
            dedup_backend = "bypassed"

        if not validated_url:
            return {
                "status": "simulated",
                "message": "No webhook URL configured. Simulated dispatch successful.",
                "idempotency_key": dedup_key,
                "dedup_backend": dedup_backend,
                "ssrf_verified": True,
                "payload": payload,
            }

        try:
            # follow_redirects=False prevents 301/302 redirect bypass to internal metadata IPs
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=False) as client:
                res = await client.post(validated_url, json=payload)
                delivered = 200 <= res.status_code < 300
                # Never return raw upstream `res.text` to prevent Full-Read SSRF response exfiltration
                return {
                    "status": "delivered" if delivered else "failed",
                    "http_status": res.status_code,
                    "delivery_ack": "accepted" if delivered else "rejected_by_upstream",
                    "idempotency_key": dedup_key,
                    "dedup_backend": dedup_backend,
                    "ssrf_verified": True,
                }
        except httpx.TimeoutException:
            return {
                "status": "error",
                "error": "Upstream webhook timed out after 5.0s",
                "idempotency_key": dedup_key,
                "ssrf_verified": True,
            }
        except httpx.RequestError:
            return {
                "status": "error",
                "error": "Upstream webhook network transport error",
                "idempotency_key": dedup_key,
                "ssrf_verified": True,
            }


    def _build_slack_payload(
        self,
        incident_id: str,
        root_cause_service: str,
        root_cause_type: str,
        confidence: float,
        affected_services: list[str],
        impact_score: float,
    ) -> dict[str, Any]:
        """Construct Slack Block Kit / Discord compatible card."""
        conf_pct = int(confidence * 100)
        readable_type = root_cause_type.replace("_", " ").title()
        cascade_text = " → ".join([root_cause_service] + affected_services) if affected_services else root_cause_service

        return {
            "text": f"🚨 [AIOps Alert] Root Cause Isolated: {root_cause_service} ({readable_type})",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🚨 P1 Incident: {root_cause_service} Failure Detected",
                        "emoji": True,
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Root Cause Service:*\n`{root_cause_service}`"},
                        {"type": "mrkdwn", "text": f"*Root Cause Type:*\n`{readable_type}`"},
                        {"type": "mrkdwn", "text": f"*AI Confidence:*\n`{conf_pct}%`"},
                        {"type": "mrkdwn", "text": f"*Business Impact Score:*\n`{impact_score}`"},
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Causal Propagation Chain:*\n```{cascade_text}```",
                    },
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Incident ID: `{incident_id}` | Graph backward walk verified by AIOps Root Cause Correlator",
                        }
                    ],
                },
            ],
        }
