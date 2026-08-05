"""
Orchestrator: coordinates the ACOP multi-agent pipeline.

Pipeline order per cycle:
  1. MonitoringAgent   — collect metrics, detect anomalies, open incidents
  2. PredictionAgent   — forecast trajectories, surface early warnings
  3. DiagnosisAgent     — determine root cause for open incidents (LLM + RAG)
  4. RemediationAgent  — propose/execute remediation actions

Runs on an APScheduler background job at AGENT_LOOP_INTERVAL_SECONDS, and can
also be triggered manually via the /agents/run-cycle API endpoint.
"""
from datetime import datetime
from typing import Any, Dict, List

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.agents.monitoring_agent import MonitoringAgent
from app.agents.prediction_agent import PredictionAgent
from app.agents.diagnosis_agent import DiagnosisAgent
from app.agents.remediation_agent import RemediationAgent
from app.config import settings
from app.core.logging_config import logger


class Orchestrator:
    def __init__(self):
        self.agents = [
            MonitoringAgent(SessionLocal),
            PredictionAgent(SessionLocal),
            DiagnosisAgent(SessionLocal),
            RemediationAgent(SessionLocal),
        ]
        self.scheduler = BackgroundScheduler()
        self.last_cycle_result: Dict[str, Any] | None = None
        self.last_cycle_at: datetime | None = None
        self.cycle_count = 0

    def run_cycle(self) -> Dict[str, Any]:
        logger.info("===== ACOP orchestrator cycle starting =====")
        context: Dict[str, Any] = {}
        results: List[Dict[str, Any]] = []

        for agent in self.agents:
            result = agent.execute(context)
            results.append(result)
            context.update(result)

        self.cycle_count += 1
        self.last_cycle_at = datetime.utcnow()
        self.last_cycle_result = {
            "cycle": self.cycle_count,
            "timestamp": str(self.last_cycle_at),
            "results": results,
        }
        logger.info("===== ACOP orchestrator cycle complete =====")
        return self.last_cycle_result

    def start(self):
        self.scheduler.add_job(
            self.run_cycle,
            "interval",
            seconds=settings.AGENT_LOOP_INTERVAL_SECONDS,
            id="acop_main_loop",
            replace_existing=True,
            max_instances=1,
        )
        self.scheduler.start()
        logger.info(f"Orchestrator scheduler started (interval={settings.AGENT_LOOP_INTERVAL_SECONDS}s)")

    def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Orchestrator scheduler stopped")

    def status(self) -> Dict[str, Any]:
        return {
            "running": self.scheduler.running,
            "cycle_count": self.cycle_count,
            "last_cycle_at": str(self.last_cycle_at) if self.last_cycle_at else None,
            "last_cycle_result": self.last_cycle_result,
            "agents": [
                {"name": a.name, "run_count": a.run_count, "last_run": str(a.last_run) if a.last_run else None}
                for a in self.agents
            ],
        }


orchestrator = Orchestrator()
