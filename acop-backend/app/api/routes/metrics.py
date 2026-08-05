from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.metrics import MetricSnapshot
from app.schemas.metrics import (
    MetricSnapshotCreate, MetricSnapshotOut, ForecastRequest, ForecastResponse, ForecastPoint,
    AnomalyCheckRequest, AnomalyCheckResponse,
)
from app.ml.lstm_model import lstm_forecaster
from app.ml.anomaly_detector import evaluate_snapshot

router = APIRouter(prefix="/metrics", tags=["Metrics & ML"])


@router.post("", response_model=MetricSnapshotOut, status_code=201)
def ingest_metric(payload: MetricSnapshotCreate, db: Session = Depends(get_db)):
    snapshot = MetricSnapshot(**payload.model_dump())
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


@router.get("", response_model=List[MetricSnapshotOut])
def list_metrics(
    cluster_id: str = Query(...),
    resource_name: str = Query(...),
    limit: int = Query(50, le=500),
    db: Session = Depends(get_db),
):
    return (
        db.query(MetricSnapshot)
        .filter(MetricSnapshot.cluster_id == cluster_id, MetricSnapshot.resource_name == resource_name)
        .order_by(MetricSnapshot.timestamp.desc())
        .limit(limit)
        .all()
    )


@router.post("/forecast", response_model=ForecastResponse)
def forecast_resource(payload: ForecastRequest, db: Session = Depends(get_db)):
    history = (
        db.query(MetricSnapshot)
        .filter(MetricSnapshot.cluster_id == payload.cluster_id, MetricSnapshot.resource_name == payload.resource_name)
        .order_by(MetricSnapshot.timestamp.asc())
        .all()
    )
    cpu_series = [h.cpu_usage_percent for h in history]
    mem_series = [h.memory_usage_percent for h in history]

    horizon_points = max(1, payload.horizon_minutes // 5)  # assume ~5-min intervals between snapshots
    forecast = lstm_forecaster.forecast(cpu_series, mem_series, horizon=horizon_points)

    now = datetime.utcnow()
    points = [
        ForecastPoint(
            timestamp=now + timedelta(minutes=5 * (i + 1)),
            predicted_cpu_usage_percent=round(cpu, 2),
            predicted_memory_usage_percent=round(mem, 2),
        )
        for i, (cpu, mem) in enumerate(forecast)
    ]
    return ForecastResponse(cluster_id=payload.cluster_id, resource_name=payload.resource_name, points=points)


@router.post("/anomaly-check", response_model=AnomalyCheckResponse)
def anomaly_check(payload: AnomalyCheckRequest, db: Session = Depends(get_db)):
    latest = (
        db.query(MetricSnapshot)
        .filter(MetricSnapshot.cluster_id == payload.cluster_id, MetricSnapshot.resource_name == payload.resource_name)
        .order_by(MetricSnapshot.timestamp.desc())
        .first()
    )
    if not latest:
        return AnomalyCheckResponse(resource_name=payload.resource_name, is_anomalous=False,
                                     anomaly_score=0.0, contributing_factors=["No metric history available"])

    history = (
        db.query(MetricSnapshot)
        .filter(MetricSnapshot.cluster_id == payload.cluster_id, MetricSnapshot.resource_name == payload.resource_name)
        .order_by(MetricSnapshot.timestamp.asc())
        .limit(30)
        .all()
    )

    features = {
        "cpu_usage_percent": latest.cpu_usage_percent,
        "memory_usage_percent": latest.memory_usage_percent,
        "network_in_mbps": latest.network_in_mbps,
        "network_out_mbps": latest.network_out_mbps,
        "disk_io_ops": latest.disk_io_ops,
        "restart_count": latest.restart_count,
        "error_rate": latest.error_rate,
        "latency_ms": latest.latency_ms,
    }
    verdict = evaluate_snapshot(
        features,
        recent_cpu=[h.cpu_usage_percent for h in history],
        recent_memory=[h.memory_usage_percent for h in history],
    )
    return AnomalyCheckResponse(
        resource_name=payload.resource_name,
        is_anomalous=verdict["is_anomalous"],
        anomaly_score=verdict["anomaly_score"],
        contributing_factors=verdict["contributing_factors"],
    )
