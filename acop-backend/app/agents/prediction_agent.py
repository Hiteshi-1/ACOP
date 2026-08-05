"""
Prediction Agent: uses the LSTM forecaster to project resource usage
forward in time, surfacing early-warning signals in the shared context
for incidents that haven't materialized yet but are trending toward one.
"""
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent
from app.models.metrics import MetricSnapshot
from app.ml.lstm_model import lstm_forecaster
from app.core.logging_config import logger


class PredictionAgent(BaseAgent):
    name = "prediction_agent"

    def __init__(self, db_factory):
        super().__init__()
        self.db_factory = db_factory

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        db: Session = self.db_factory()
        try:
            resources = (
                db.query(MetricSnapshot.cluster_id, MetricSnapshot.resource_name)
                .distinct()
                .all()
            )

            warnings = []
            for cluster_id, resource_name in resources:
                history = self._get_history(db, cluster_id, resource_name)
                if len(history) < 5:
                    continue

                forecast = lstm_forecaster.forecast(
                    [h.cpu_usage_percent for h in history],
                    [h.memory_usage_percent for h in history],
                    horizon=5,
                )
                max_cpu = max(p[0] for p in forecast)
                max_mem = max(p[1] for p in forecast)

                if max_cpu > 90 or max_mem > 90:
                    warnings.append({
                        "cluster_id": cluster_id,
                        "resource_name": resource_name,
                        "forecast_max_cpu": round(max_cpu, 1),
                        "forecast_max_memory": round(max_mem, 1),
                    })
                    logger.info(
                        f"[prediction_agent] Early warning for '{resource_name}': "
                        f"CPU→{max_cpu:.1f}% MEM→{max_mem:.1f}% within 5 intervals"
                    )

            return {"agent": self.name, "forecast_warnings": warnings}
        finally:
            db.close()

    @staticmethod
    def _get_history(db: Session, cluster_id: str, resource_name: str, limit: int = 30) -> List[MetricSnapshot]:
        return (
            db.query(MetricSnapshot)
            .filter(MetricSnapshot.cluster_id == cluster_id, MetricSnapshot.resource_name == resource_name)
            .order_by(MetricSnapshot.timestamp.asc())
            .limit(limit)
            .all()
        )
