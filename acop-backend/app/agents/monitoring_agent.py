"""
Monitoring Agent: continuously observes cluster resource metrics,
runs anomaly detection (XGBoost + LSTM forecast deviation), and opens
Incident records for resources that look unhealthy.
"""
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent
from app.models.cluster import Cluster
from app.models.incident import Incident
from app.models.metrics import MetricSnapshot
from app.k8s.operations import k8s_ops
from app.ml.anomaly_detector import evaluate_snapshot
from app.core.logging_config import logger


class MonitoringAgent(BaseAgent):
    name = "monitoring_agent"

    def __init__(self, db_factory):
        super().__init__()
        self.db_factory = db_factory

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        db: Session = self.db_factory()
        try:
            clusters = db.query(Cluster).filter(Cluster.is_active == True).all()  # noqa: E712
            new_incidents = []

            for cluster in clusters:
                pods = k8s_ops.list_pods()
                for pod in pods:
                    snapshot = self._collect_and_store_snapshot(db, cluster.id, pod)
                    history = self._get_recent_history(db, cluster.id, pod["name"])
                    features = self._snapshot_to_features(snapshot)

                    verdict = evaluate_snapshot(
                        features,
                        recent_cpu=[h.cpu_usage_percent for h in history],
                        recent_memory=[h.memory_usage_percent for h in history],
                    )

                    if verdict["is_anomalous"]:
                        incident = self._open_incident_if_new(db, cluster.id, pod, verdict)
                        if incident:
                            new_incidents.append(incident.id)

            db.commit()
            return {"agent": self.name, "new_incidents": new_incidents, "clusters_checked": len(clusters)}
        finally:
            db.close()

    def _collect_and_store_snapshot(self, db: Session, cluster_id: str, pod: Dict) -> MetricSnapshot:
        # In mock mode, simulate plausible telemetry; in real mode this would come from
        # a metrics backend (Prometheus/metrics-server) queried per pod.
        restart_count = pod.get("restart_count", 0)
        base_cpu = random.uniform(20, 60)
        base_mem = random.uniform(30, 65)
        stress_multiplier = 1 + (restart_count * 0.15)

        snapshot = MetricSnapshot(
            cluster_id=cluster_id,
            resource_name=pod["name"],
            resource_type="pod",
            cpu_usage_percent=min(100, base_cpu * stress_multiplier),
            memory_usage_percent=min(100, base_mem * stress_multiplier),
            network_in_mbps=random.uniform(1, 50),
            network_out_mbps=random.uniform(1, 50),
            disk_io_ops=random.uniform(10, 200),
            restart_count=restart_count,
            error_rate=min(20, restart_count * random.uniform(0.5, 2.0)),
            latency_ms=random.uniform(20, 300) * stress_multiplier,
            timestamp=datetime.utcnow(),
        )
        db.add(snapshot)
        db.flush()
        return snapshot

    @staticmethod
    def _get_recent_history(db: Session, cluster_id: str, resource_name: str, limit: int = 30) -> List[MetricSnapshot]:
        return (
            db.query(MetricSnapshot)
            .filter(MetricSnapshot.cluster_id == cluster_id, MetricSnapshot.resource_name == resource_name)
            .order_by(MetricSnapshot.timestamp.asc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def _snapshot_to_features(snapshot: MetricSnapshot) -> Dict:
        return {
            "cpu_usage_percent": snapshot.cpu_usage_percent,
            "memory_usage_percent": snapshot.memory_usage_percent,
            "network_in_mbps": snapshot.network_in_mbps,
            "network_out_mbps": snapshot.network_out_mbps,
            "disk_io_ops": snapshot.disk_io_ops,
            "restart_count": snapshot.restart_count,
            "error_rate": snapshot.error_rate,
            "latency_ms": snapshot.latency_ms,
        }

    @staticmethod
    def _open_incident_if_new(db: Session, cluster_id: str, pod: Dict, verdict: Dict) -> Incident | None:
        # Avoid duplicate open incidents for the same resource within a cooldown window
        recent_cutoff = datetime.utcnow() - timedelta(minutes=10)
        existing = (
            db.query(Incident)
            .filter(
                Incident.cluster_id == cluster_id,
                Incident.resource_name == pod["name"],
                Incident.status.in_(["open", "diagnosing", "remediating"]),
                Incident.created_at >= recent_cutoff,
            )
            .first()
        )
        if existing:
            return None

        severity = "critical" if verdict["anomaly_score"] > 0.9 else "high" if verdict["anomaly_score"] > 0.75 else "medium"

        incident = Incident(
            cluster_id=cluster_id,
            title=f"Anomaly detected on pod '{pod['name']}'",
            description="; ".join(verdict["contributing_factors"]) or "Anomalous metric pattern detected.",
            severity=severity,
            status="open",
            source="monitoring_agent",
            resource_type="pod",
            resource_name=pod["name"],
            anomaly_score=verdict["anomaly_score"],
        )
        db.add(incident)
        db.flush()
        logger.warning(f"New incident opened: {incident.title} (score={verdict['anomaly_score']:.2f})")
        return incident
