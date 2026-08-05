"""
Diagnosis Agent: for each open incident, gathers metric history and
retrieves relevant runbook precedent via RAG, then asks Claude to
determine the most likely root cause with a confidence score.
"""
from typing import Any, Dict, List

from sqlalchemy.orm import Session

from app.agents.base_agent import BaseAgent
from app.models.incident import Incident
from app.models.metrics import MetricSnapshot
from app.llm.llm_client import llm_client
from app.rag.retriever import build_context_block
from app.core.logging_config import logger


class DiagnosisAgent(BaseAgent):
    name = "diagnosis_agent"

    def __init__(self, db_factory):
        super().__init__()
        self.db_factory = db_factory

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        db: Session = self.db_factory()
        try:
            open_incidents = db.query(Incident).filter(Incident.status == "open").all()
            diagnosed = []

            for incident in open_incidents:
                incident.status = "diagnosing"
                db.flush()

                history = self._get_history(db, incident.cluster_id, incident.resource_name)
                incident_context = self._build_incident_context(incident, history)
                rag_context = build_context_block(
                    f"{incident.title} {incident.description or ''}", n_results=2
                )

                full_context = f"{incident_context}\n\n{rag_context}"
                diagnosis = llm_client.diagnose_incident(full_context)

                incident.root_cause = diagnosis.get("root_cause", "Unable to determine root cause.")
                incident.confidence_score = float(diagnosis.get("confidence", 0.5))
                incident.status = "open"  # remains open until remediation resolves it
                db.flush()

                diagnosed.append({
                    "incident_id": incident.id,
                    "root_cause": incident.root_cause,
                    "confidence": incident.confidence_score,
                })
                logger.info(f"[diagnosis_agent] Incident {incident.id} diagnosed "
                            f"(confidence={incident.confidence_score:.2f})")

            db.commit()
            return {"agent": self.name, "diagnosed": diagnosed}
        finally:
            db.close()

    @staticmethod
    def _get_history(db: Session, cluster_id: str, resource_name: str, limit: int = 15) -> List[MetricSnapshot]:
        if not resource_name:
            return []
        return (
            db.query(MetricSnapshot)
            .filter(MetricSnapshot.cluster_id == cluster_id, MetricSnapshot.resource_name == resource_name)
            .order_by(MetricSnapshot.timestamp.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def _build_incident_context(incident: Incident, history: List[MetricSnapshot]) -> str:
        lines = [
            f"Incident: {incident.title}",
            f"Severity: {incident.severity}",
            f"Resource: {incident.resource_type} '{incident.resource_name}'",
            f"Anomaly score: {incident.anomaly_score}",
            f"Description: {incident.description}",
        ]
        if history:
            lines.append("\nRecent metric history (most recent first):")
            for h in history[:10]:
                lines.append(
                    f"  t={h.timestamp}: CPU={h.cpu_usage_percent:.1f}% MEM={h.memory_usage_percent:.1f}% "
                    f"restarts={h.restart_count} errors={h.error_rate:.1f}% latency={h.latency_ms:.0f}ms"
                )
        return "\n".join(lines)
