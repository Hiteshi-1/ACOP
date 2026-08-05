import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Float

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class MetricSnapshot(Base):
    """
    Time-series resource metrics used as input for the LSTM forecaster
    and XGBoost anomaly classifier.
    """
    __tablename__ = "metric_snapshots"

    id = Column(String, primary_key=True, default=gen_uuid)
    cluster_id = Column(String, index=True, nullable=False)
    resource_name = Column(String, index=True, nullable=False)
    resource_type = Column(String, default="pod")

    cpu_usage_percent = Column(Float, default=0.0)
    memory_usage_percent = Column(Float, default=0.0)
    network_in_mbps = Column(Float, default=0.0)
    network_out_mbps = Column(Float, default=0.0)
    disk_io_ops = Column(Float, default=0.0)
    restart_count = Column(Float, default=0.0)
    error_rate = Column(Float, default=0.0)
    latency_ms = Column(Float, default=0.0)

    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
