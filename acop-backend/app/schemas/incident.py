from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class IncidentBase(BaseModel):
    title: str
    description: Optional[str] = None
    severity: str = "low"
    resource_type: Optional[str] = None
    resource_name: Optional[str] = None


class IncidentCreate(IncidentBase):
    cluster_id: str
    source: str = "monitoring_agent"
    anomaly_score: Optional[float] = None


class IncidentUpdate(BaseModel):
    status: Optional[str] = None
    root_cause: Optional[str] = None
    confidence_score: Optional[float] = None
    severity: Optional[str] = None


class IncidentOut(IncidentBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    cluster_id: str
    status: str
    source: str
    anomaly_score: Optional[float] = None
    root_cause: Optional[str] = None
    confidence_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
