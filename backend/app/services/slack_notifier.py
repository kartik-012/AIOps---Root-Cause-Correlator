"""Slack & Discord Webhook Notification Service for AIOps Incident Alerts."""

import os
import httpx
from typing import Any


class SlackNotifier:
    """Dispatches rich incident correlation cards to Slack or Discord webhooks."""

    def __init__(self, default_webhook_url: str | None = None):
        self.default_webhook_url = default_webhook_url or os.getenv("SLACK_WEBHOOK_URL")

    async def send_incident_alert(
        self,
        incident_id: str,
        root_cause_service: str,
        root_cause_type: str,
        confidence: float,
        affected_services: list[str],
        impact_score: float,
        webhook_url: str | None = None,
    ) -> dict[str, Any]:
        """Format and dispatch an alert card to Slack/Discord."""
        target_url = webhook_url or self.default_webhook_url
        if not target_url:
            return {
                "status": "simulated",
                "message": "No webhook URL configured. Simulated dispatch successful.",
                "payload": self._build_slack_payload(
                    incident_id, root_cause_service, root_cause_type, confidence, affected_services, impact_score
                ),
            }

        payload = self._build_slack_payload(
            incident_id, root_cause_service, root_cause_type, confidence, affected_services, impact_score
        )

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.post(target_url, json=payload)
                return {
                    "status": "delivered" if res.status_code == 200 else "failed",
                    "http_status": res.status_code,
                    "response": res.text,
                }
        except Exception as e:
            return {"status": "error", "error": str(e)}

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
