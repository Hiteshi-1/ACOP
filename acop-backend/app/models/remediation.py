import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Remediation(Base):
    __tablename__ = "remediations"

    id = Column(String, primary_key=True, default=gen_uuid)
    incident_id = Column(String, ForeignKey("incidents.id"), nullable=False)

    action_type = Column(String, nullable=False)  # restart_pod, scale_deployment, drain_node, rollback, patch_config
    action_payload = Column(Text, nullable=True)  # JSON string of the exact action params
    reasoning = Column(Text, nullable=True)  # LLM-generated reasoning for this action
    confidence_score = Column(Float, nullable=True)

    requires_approval = Column(Boolean, default=True)
    approved = Column(Boolean, default=False)
    approved_by = Column(String, nullable=True)

    status = Column(String, default="proposed")  # proposed, approved, executing, succeeded, failed, rejected
    execution_log = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    executed_at = Column(DateTime, nullable=True)

    incident = relationship("Incident", back_populates="remediations")
