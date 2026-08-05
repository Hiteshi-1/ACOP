from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict


class NodeBase(BaseModel):
    name: str
    role: str = "worker"
    cpu_capacity: Optional[str] = None
    memory_capacity: Optional[str] = None
    status: str = "Ready"


class NodeCreate(NodeBase):
    pass


class NodeOut(NodeBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    cluster_id: str
    created_at: datetime


class ClusterBase(BaseModel):
    name: str
    provider: str = "on-prem"
    region: Optional[str] = None


class ClusterCreate(ClusterBase):
    pass


class ClusterUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    region: Optional[str] = None
    is_active: Optional[bool] = None


class ClusterOut(ClusterBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    is_active: bool
    node_count: int
    created_at: datetime
    updated_at: datetime


class ClusterDetailOut(ClusterOut):
    nodes: List[NodeOut] = []
