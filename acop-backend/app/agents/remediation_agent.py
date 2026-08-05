"""
Remediation Agent: for diagnosed incidents, asks Claude to propose a
concrete remediation action, records it, and — if auto-remediation is
enabled and confidence clears the configured threshold — executes it
directly against the cluster via app.k8s.operations.
"""
import json
from datetime import datetime
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent
from app.models.incident import Incident
from app.models.remediation import Remediation
from app.llm.llm_client import llm_client
from app.rag.retriever import build_context_block
from app.rag.knowledge_base import add_incident_resolution
from app.k8s.operations import k8s_ops
from app.config import settings
from app.core.logging_config import logger


class RemediationAgent(BaseAgent):
    name = "remediation_agent"

    def __init__(self, db_factory):
        super().__init__()
        self.db_factory = db_factory

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        db: Session = self.db_factory()
        try:
            candidates = (
                db.query(Incident)
                .filter(Incident.status == "open", Incident.root_cause.isnot(None))
                .all()
            )
            actions_taken = []

            for incident in candidates:
                existing = (
                    db.query(Remediation)
                    .filter(Remediation.incident_id == incident.id)
                    .first()
                )
                if existing:
                    continue  # already have a proposed/executed remediation for this incident

                incident.status = "remediating"
                db.flush()

                rag_context = build_context_block(incident.root_cause, n_results=2)
                incident_context = (
                    f"Incident: {incident.title}\nResource: {incident.resource_type} '{incident.resource_name}'\n"
                    f"Severity: {incident.severity}\n\n{rag_context}"
                )
                proposal = llm_client.propose_remediation(incident_context, incident.root_cause)

                confidence = float(proposal.get("confidence", 0.5))
                requires_approval = not (
                    settings.AUTO_REMEDIATION_ENABLED
                    and confidence >= settings.AUTO_REMEDIATION_CONFIDENCE_THRESHOLD
                )

                remediation = Remediation(
                    incident_id=incident.id,
                    action_type=proposal.get("action_type", "restart_pod"),
                    action_payload=json.dumps(proposal.get("payload", {})),
                    reasoning=proposal.get("reasoning", ""),
                    confidence_score=confidence,
                    requires_approval=requires_approval,
                    status="proposed",
                )
                db.add(remediation)
                db.flush()

                if not requires_approval:
                    self._execute(db, remediation, incident)
                else:
                    logger.info(f"[remediation_agent] Remediation {remediation.id} awaiting manual approval "
                                f"(confidence={confidence:.2f})")

                actions_taken.append({
                    "incident_id": incident.id,
                    "remediation_id": remediation.id,
                    "action_type": remediation.action_type,
                    "auto_executed": not requires_approval,
                })

            db.commit()
            return {"agent": self.name, "actions": actions_taken}
        finally:
            db.close()

    def _execute(self, db: Session, remediation: Remediation, incident: Incident):
        """Executes an approved/auto-approved remediation action against the cluster."""
        payload = json.loads(remediation.action_payload or "{}")
        remediation.status = "executing"
        db.flush()

        result = {"success": False, "message": "Unknown action_type"}
        try:
            if remediation.action_type == "restart_pod":
                result = k8s_ops.restart_pod(incident.resource_name, **{
                    k: v for k, v in payload.items() if k == "grace_period_seconds"
                })
            elif remediation.action_type == "scale_deployment":
                result = k8s_ops.scale_deployment(incident.resource_name, payload.get("replicas", 3))
            elif remediation.action_type == "drain_node":
                result = k8s_ops.drain_node(incident.resource_name)
            elif remediation.action_type == "rollback":
                result = k8s_ops.rollback_deployment(incident.resource_name)
            elif remediation.action_type == "patch_config":
                result = k8s_ops.patch_config(incident.resource_name, payload.get("patch", {}))
        except Exception as e:
            result = {"success": False, "message": str(e)}
            logger.exception(f"Remediation execution failed: {e}")

        remediation.status = "succeeded" if result.get("success") else "failed"
        remediation.execution_log = json.dumps(result)
        remediation.executed_at = datetime.utcnow()
        remediation.approved = True
        remediation.approved_by = "auto_remediation_agent"

        if result.get("success"):
            incident.status = "resolved"
            incident.resolved_at = datetime.utcnow()
            add_incident_resolution(
                incident_title=incident.title,
                root_cause=incident.root_cause or "",
                remediation_summary=f"{remediation.action_type}: {remediation.reasoning}",
                outcome="Resolved successfully via autonomous remediation.",
            )
        else:
            incident.status = "escalated"

        db.flush()
