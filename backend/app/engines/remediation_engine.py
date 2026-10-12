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
    pre_remediation_health: Dict[str, Any] = field(default_factory=dict)
    post_remediation_health: Dict[str, Any] = field(default_factory=dict)
    closed_loop_verified: bool = False


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
    """Manages remediation proposals, human approvals, closed-loop gRPC execution, and event tracking."""

    def __init__(self, state_manager: Any | None = None):
        self._plans: Dict[str, RemediationPlan] = {}
        self._state_manager = state_manager

    def _get_state_manager(self):
        if self._state_manager is not None:
            return self._state_manager
        from app.grpc_services.diagnostic_server import _global_state_manager
        return _global_state_manager

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

    async def approve_and_execute(
        self,
        plan_id: str,
        approver: str = "SRE Commander",
        db: Any | None = None,
    ) -> RemediationPlan:
        """Approve and execute a remediation action with closed-loop ServiceStateManager health restoration."""
        plan = self._plans.get(plan_id)
        if not plan:
            raise ValueError(f"Remediation plan {plan_id} not found")

        plan.status = "APPROVED"
        plan.approved_by = approver
        now = datetime.now(timezone.utc)

        # 1. Publish remediation.requested event to Kafka
        producer = get_kafka_producer()
        try:
            await producer.publish_remediation(
                RemediationEvent(
                    incident_id=plan.incident_id,
                    action=plan.action_title,
                    status="requested",
                    approved_by=approver,
                )
            )
        except Exception as exc:
            logger.debug("Kafka publish_remediation(requested) skipped: %s", exc)

        # 2. Differentiator #9: Closed-Loop gRPC & ServiceStateManager Execution
        state_mgr = self._get_state_manager()
        norm_svc = state_mgr._normalize_id(plan.target_service)
        pre_state = state_mgr.get_state(norm_svc, apply_drift=False)
        plan.pre_remediation_health = {
            "service_id": pre_state.service_id,
            "status": pre_state.status,
            "cpu_usage_percent": round(pre_state.cpu_usage_percent, 2),
            "memory_usage_percent": round(pre_state.memory_usage_percent, 2),
            "active_connections": pre_state.active_connections,
            "error_rate": round(pre_state.error_rate, 4),
            "p95_latency_ms": round(pre_state.p95_latency_ms, 2),
            "active_alerts": list(pre_state.active_alerts),
        }

        new_max_conn = None
        if plan.command_payload.get("action") == "scale_pool":
            new_max_conn = int(plan.command_payload.get("to", 1500))

        restored = state_mgr.restore_health(norm_svc, max_connections=new_max_conn)
        post_state = state_mgr.get_state(norm_svc, apply_drift=False)
        plan.post_remediation_health = {
            "service_id": post_state.service_id,
            "status": post_state.status,
            "cpu_usage_percent": round(post_state.cpu_usage_percent, 2),
            "memory_usage_percent": round(post_state.memory_usage_percent, 2),
            "active_connections": post_state.active_connections,
            "max_connections": post_state.max_connections,
            "error_rate": round(post_state.error_rate, 4),
            "p95_latency_ms": round(post_state.p95_latency_ms, 2),
            "active_alerts": list(post_state.active_alerts),
        }
        plan.closed_loop_verified = bool(
            restored
            and post_state.status == 0
            and post_state.error_rate == 0.0
            and len(post_state.active_alerts) == 0
        )

        logger.info(
            "[Remediation] Executed closed-loop action '%s' on %s (verified=%s) approved by %s",
            plan.action_title,
            plan.target_service,
            plan.closed_loop_verified,
            approver,
        )
        plan.status = "EXECUTED"
        plan.executed_at = now

        # Persist to DB if session provided
        if db is not None:
            try:
                from sqlalchemy import select
                from app.models.db_models import Incident, RunbookSuggestion

                inc_uuid = uuid.UUID(str(plan.incident_id))
                inc_row = db.scalar(select(Incident).where(Incident.id == inc_uuid))
                if inc_row is not None:
                    inc_row.resolution_action = plan.action_title
                    inc_row.timestamp_end = now

                sugg = db.scalar(
                    select(RunbookSuggestion)
                    .where(RunbookSuggestion.incident_id == inc_uuid)
                    .order_by(RunbookSuggestion.suggested_at.desc())
                )
                if sugg is not None:
                    sugg.was_approved = True
                    sugg.suggested_action = plan.action_title
                else:
                    db.add(
                        RunbookSuggestion(
                            incident_id=inc_uuid,
                            root_cause_type=plan.root_cause_type,
                            suggested_action=plan.action_title,
                            was_approved=True,
                            suggested_at=now,
                        )
                    )
                db.commit()
            except Exception as exc:
                logger.debug("Optional DB persistence in approve_and_execute skipped: %s", exc)

        # 3. Publish remediation.completed event to Kafka
        try:
            await producer.publish_remediation(
                RemediationEvent(
                    incident_id=plan.incident_id,
                    action=plan.action_title,
                    status="completed",
                    approved_by=approver,
                )
            )
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
                        "closed_loop_verified": plan.closed_loop_verified,
                        "executed_at": now.isoformat(),
                    },
                )
            )
        except Exception as exc:
            logger.debug("Kafka publish_audit skipped: %s", exc)

        return plan


# Global singleton instance
_remediation_engine = RemediationEngine()


def get_remediation_engine() -> RemediationEngine:
    return _remediation_engine

