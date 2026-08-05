import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Float, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class Incident(Base):
    __tablename__ = "incidents"

    id = Column(String, primary_key=True, default=gen_uuid)
    cluster_id = Column(String, ForeignKey("clusters.id"), nullable=False)

    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    severity = Column(String, default="low")  # low, medium, high, critical
    status = Column(String, default="open")  # open, diagnosing, remediating, resolved, escalated
    source = Column(String, default="monitoring_agent")  # which agent/system raised it
    resource_type = Column(String, nullable=True)  # pod, node, deployment, service
    resource_name = Column(String, nullable=True)

    anomaly_score = Column(Float, nullable=True)
    root_cause = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    cluster = relationship("Cluster", back_populates="incidents")
    remediations = relationship("Remediation", back_populates="incident", cascade="all, delete-orphan")
