from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict


class MetricSnapshotBase(BaseModel):
    cluster_id: str
    resource_name: str
    resource_type: str = "pod"
    cpu_usage_percent: float = 0.0
    memory_usage_percent: float = 0.0
    network_in_mbps: float = 0.0
    network_out_mbps: float = 0.0
    disk_io_ops: float = 0.0
    restart_count: float = 0.0
    error_rate: float = 0.0
    latency_ms: float = 0.0


class MetricSnapshotCreate(MetricSnapshotBase):
    pass


class MetricSnapshotOut(MetricSnapshotBase):
    model_config = ConfigDict(from_attributes=True)
    id: str
    timestamp: datetime


class ForecastRequest(BaseModel):
    cluster_id: str
    resource_name: str
    horizon_minutes: int = 30


class ForecastPoint(BaseModel):
    timestamp: datetime
    predicted_cpu_usage_percent: float
    predicted_memory_usage_percent: float


class ForecastResponse(BaseModel):
    cluster_id: str
    resource_name: str
    points: List[ForecastPoint]


class AnomalyCheckRequest(BaseModel):
    cluster_id: str
    resource_name: str


class AnomalyCheckResponse(BaseModel):
    resource_name: str
    is_anomalous: bool
    anomaly_score: float
    contributing_factors: List[str] = []
