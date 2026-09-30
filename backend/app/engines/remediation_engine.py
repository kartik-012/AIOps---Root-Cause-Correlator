"""Remediation Engine — Automated remediation recommendation and human-in-the-loop approval workflow.

Maps incident root cause patterns to safe, deterministic runbook actions.
Supports approval gating, Kafka audit event emission, and execution tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import logging
import uuid

from app.kafka import get_kafka_producer
from app.kafka.events import RemediationEvent, AuditEvent

logger = logging.getLogger(__name__)


@dataclass
class RemediationPlan:
    plan_id: str
    incident_id: str
    root_cause_type: str
    target_service: str
    action_title: str
    command_payload: Dict[str, Any]
    risk_level: str  # LOW, MEDIUM, HIGH
    requires_approval: bool
    status: str  # PENDING_APPROVAL, APPROVED, EXECUTED, REJECTED
    suggested_at: datetime
    executed_at: Optional[datetime] = None
    approved_by: Optional[str] = None


RECOMMENDED_ACTIONS = {
    "db_connection_exhaustion": {
        "title": "Scale database connection pool & kill idle connections",
        "command": {"action": "scale_pool", "parameter": "max_connections", "from": 100, "to": 150, "kill_idle_sec": 30},
        "risk": "LOW",
    },
    "memory_leak": {
        "title": "Perform progressive rolling restart & capture heap profile",
        "command": {"action": "rolling_restart", "batch_percent": 25, "capture_dump": True},
        "risk": "MEDIUM",
    },
    "cpu_spike": {
        "title": "Scale replica count & throttle non-critical batch processing",
        "command": {"action": "scale_replicas", "from": 2, "to": 5, "throttle_priority": "batch"},
        "risk": "LOW",
    },
    "network_latency_injection": {
        "title": "Engage circuit breaker & reroute traffic to standby zone",
        "command": {"action": "circuit_breaker", "threshold_ms": 250, "reroute_zone": "us-east-1b"},
        "risk": "LOW",
    },
    "disk_io_saturation": {
        "title": "Flush temporary WAL queues & increase provisioned IOPS",
        "command": {"action": "flush_wal", "provision_iops": 3000},
        "risk": "MEDIUM",
    },
    "pod_crash_loop": {
        "title": "Roll back recent deployment to previous stable SHA",
        "command": {"action": "rollback", "target_revision": "HEAD~1"},
        "risk": "HIGH",
    },
}


class RemediationEngine:
    """Manages remediation proposals, human approvals, and event tracking."""

    def __init__(self):
        self._plans: Dict[str, RemediationPlan] = {}

    def generate_plan(self, incident_id: str, root_cause_type: str, target_service: str) -> RemediationPlan:
        template = RECOMMENDED_ACTIONS.get(
            root_cause_type,
            {
                "title": f"Execute diagnostic triage on {target_service}",
                "command": {"action": "diagnose", "service": target_service},
                "risk": "LOW",
            },
        )

        plan_id = f"rem-{uuid.uuid4().hex[:8]}"
        plan = RemediationPlan(
            plan_id=plan_id,
            incident_id=str(incident_id),
            root_cause_type=root_cause_type,
            target_service=target_service,
            action_title=template["title"],
            command_payload=template["command"],
            risk_level=template["risk"],
            requires_approval=True,
            status="PENDING_APPROVAL",
            suggested_at=datetime.now(timezone.utc),
        )

        self._plans[plan_id] = plan
        return plan

    def get_plan(self, plan_id: str) -> Optional[RemediationPlan]:
        return self._plans.get(plan_id)

    def get_plans_for_incident(self, incident_id: str) -> List[RemediationPlan]:
        return [p for p in self._plans.values() if p.incident_id == str(incident_id)]

    async def approve_and_execute(self, plan_id: str, approver: str = "SRE Commander") -> RemediationPlan:
        """Approve and execute a remediation action with full Kafka audit trail."""
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError(f"Remediation plan {plan_id} not found")

        plan.status = "APPROVED"
        plan.approved_by = approver
        now = datetime.now(timezone.utc)

        # 1. Publish remediation.requested event to Kafka
        producer = get_kafka_producer()
        await producer.publish_remediation(
            RemediationEvent(
                incident_id=plan.incident_id,
                action=plan.action_title,
                status="requested",
                approved_by=approver,
            )
        )

        # 2. Simulate safe automated execution
        logger.info(f"[Remediation] Executing action '{plan.action_title}' on {plan.target_service} approved by {approver}")
        plan.status = "EXECUTED"
        plan.executed_at = now

        # 3. Publish remediation.completed event to Kafka
        await producer.publish_remediation(
            RemediationEvent(
                incident_id=plan.incident_id,
                action=plan.action_title,
                status="completed",
                approved_by=approver,
            )
        )

        # 4. Publish structured Audit event
        await producer.publish_audit(
            AuditEvent(
                event_type="remediation_executed",
                actor=approver,
                details={
                    "plan_id": plan.plan_id,
                    "incident_id": plan.incident_id,
                    "target_service": plan.target_service,
                    "action": plan.action_title,
                    "payload": plan.command_payload,
                    "risk_level": plan.risk_level,
                    "executed_at": now.isoformat(),
                },
            )
        )

        return plan


# Global singleton instance
_remediation_engine = RemediationEngine()


def get_remediation_engine() -> RemediationEngine:
    return _remediation_engine
