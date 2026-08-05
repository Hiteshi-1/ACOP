from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class RemediationBase(BaseModel):
    action_type: str
    action_payload: Optional[str] = None
    reasoning: Optional[str] = None
    confidence_score: Optional[float] = None
    requires_approval: bool = True


class RemediationCreate(RemediationBase):
    incident_id: str


class RemediationApproval(BaseModel):
    approved: bool
    approved_by: str


class RemediationOut(RemediationBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    incident_id: str
    approved: bool
    approved_by: Optional[str] = None
    status: str
    execution_log: Optional[str] = None
    created_at: datetime
    executed_at: Optional[datetime] = None
