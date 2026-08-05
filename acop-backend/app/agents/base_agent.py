"""
Common interface all ACOP agents implement, so the Orchestrator can
run them uniformly in the autonomous operations loop.
"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict

from app.core.logging_config import logger


class BaseAgent(ABC):
    name: str = "base_agent"

    def __init__(self):
        self.last_run: datetime | None = None
        self.run_count: int = 0

    @abstractmethod
    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute one cycle of this agent's responsibility.
        `context` carries shared state produced by upstream agents in the pipeline.
        Returns a dict that gets merged into the shared context for downstream agents.
        """
        raise NotImplementedError

    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Wraps run() with logging, timing, and error isolation."""
        started = datetime.utcnow()
        logger.info(f"[{self.name}] starting run #{self.run_count + 1}")
        try:
            result = self.run(context)
            self.run_count += 1
            self.last_run = started
            duration = (datetime.utcnow() - started).total_seconds()
            logger.info(f"[{self.name}] completed in {duration:.2f}s")
            return result
        except Exception as e:
            logger.exception(f"[{self.name}] failed: {e}")
            return {"error": str(e), "agent": self.name}
