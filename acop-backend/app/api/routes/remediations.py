from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.remediation import Remediation
from app.models.incident import Incident
from app.schemas.remediation import RemediationOut, RemediationApproval
from app.core.security import get_current_user
from app.k8s.operations import k8s_ops
from app.rag.knowledge_base import add_incident_resolution
from app.core.logging_config import logger

import json

router = APIRouter(prefix="/remediations", tags=["Remediations"])


@router.get("", response_model=List[RemediationOut])
def list_remediations(
    status: Optional[str] = Query(None),
    requires_approval: Optional[bool] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Remediation)
    if status:
        q = q.filter(Remediation.status == status)
    if requires_approval is not None:
        q = q.filter(Remediation.requires_approval == requires_approval)
    return q.order_by(Remediation.created_at.desc()).limit(limit).all()


@router.get("/{remediation_id}", response_model=RemediationOut)
def get_remediation(remediation_id: str, db: Session = Depends(get_db)):
    remediation = db.query(Remediation).filter(Remediation.id == remediation_id).first()
    if not remediation:
        raise HTTPException(status_code=404, detail="Remediation not found")
    return remediation


@router.post("/{remediation_id}/approve", response_model=RemediationOut)
def approve_remediation(remediation_id: str, payload: RemediationApproval, db: Session = Depends(get_db),
                         user: str = Depends(get_current_user)):
    """
    Human-in-the-loop approval gate. When a remediation was flagged as
    requiring approval (low confidence or auto-remediation disabled),
    an operator calls this endpoint to approve or reject execution.
    """
    remediation = db.query(Remediation).filter(Remediation.id == remediation_id).first()
    if not remediation:
        raise HTTPException(status_code=404, detail="Remediation not found")
    if remediation.status not in ("proposed",):
        raise HTTPException(status_code=400, detail=f"Remediation is already '{remediation.status}'")

    incident = db.query(Incident).filter(Incident.id == remediation.incident_id).first()

    if not payload.approved:
        remediation.status = "rejected"
        remediation.approved = False
        remediation.approved_by = payload.approved_by
        if incident:
            incident.status = "escalated"
        db.commit()
        db.refresh(remediation)
        return remediation

    remediation.approved = True
    remediation.approved_by = payload.approved_by
    remediation.status = "executing"
    db.flush()

    action_payload = json.loads(remediation.action_payload or "{}")
    result = _execute_action(remediation.action_type, incident.resource_name if incident else "", action_payload)

    remediation.status = "succeeded" if result.get("success") else "failed"
    remediation.execution_log = json.dumps(result)
    remediation.executed_at = datetime.utcnow()

    if incident:
        if result.get("success"):
            incident.status = "resolved"
            incident.resolved_at = datetime.utcnow()
            add_incident_resolution(
                incident_title=incident.title,
                root_cause=incident.root_cause or "",
                remediation_summary=f"{remediation.action_type}: {remediation.reasoning}",
                outcome="Resolved via manually-approved remediation.",
            )
        else:
            incident.status = "escalated"

    db.commit()
    db.refresh(remediation)
    return remediation


def _execute_action(action_type: str, resource_name: str, payload: dict) -> dict:
    try:
        if action_type == "restart_pod":
            return k8s_ops.restart_pod(resource_name, **{k: v for k, v in payload.items() if k == "grace_period_seconds"})
        elif action_type == "scale_deployment":
            return k8s_ops.scale_deployment(resource_name, payload.get("replicas", 3))
        elif action_type == "drain_node":
            return k8s_ops.drain_node(resource_name)
        elif action_type == "rollback":
            return k8s_ops.rollback_deployment(resource_name)
        elif action_type == "patch_config":
            return k8s_ops.patch_config(resource_name, payload.get("patch", {}))
        return {"success": False, "message": f"Unknown action_type: {action_type}"}
    except Exception as e:
        logger.exception(f"Manual remediation execution failed: {e}")
        return {"success": False, "message": str(e)}
