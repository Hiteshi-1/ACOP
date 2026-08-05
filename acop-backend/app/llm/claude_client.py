"""
Thin wrapper around the Anthropic API used by ACOP's agents for:
  - Root-cause diagnosis reasoning
  - Remediation action proposal + justification
  - Conversational ops-chat interface (chat.py route)

Falls back to a deterministic mock response when no API key is configured,
so the backend is fully runnable in demo mode without external dependencies.
"""
import json
from typing import List, Dict, Optional

from anthropic import Anthropic, APIError

from app.config import settings
from app.core.logging_config import logger


class ClaudeClient:
    def __init__(self):
        self.model = settings.CLAUDE_MODEL
        self.enabled = bool(settings.ANTHROPIC_API_KEY)
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY) if self.enabled else None
        if not self.enabled:
            logger.warning("ANTHROPIC_API_KEY not set — ClaudeClient running in MOCK mode.")

    def _mock_response(self, purpose: str) -> str:
        mocks = {
            "diagnosis": json.dumps({
                "root_cause": "Memory pressure caused by a slow leak in the application container, "
                               "triggering repeated OOMKilled restarts.",
                "confidence": 0.82,
                "evidence": [
                    "Memory usage climbed steadily over 20 minutes before each restart",
                    "Restart count spiked in correlation with memory saturation",
                ],
            }),
            "remediation": json.dumps({
                "action_type": "restart_pod",
                "reasoning": "A clean restart clears the leaked memory immediately; "
                             "a follow-up ticket should track a permanent code fix.",
                "confidence": 0.78,
                "payload": {"grace_period_seconds": 30},
            }),
            "chat": "I'm running in demo/mock mode right now because no ANTHROPIC_API_KEY is configured. "
                    "Add your key to .env to enable live Claude-powered reasoning.",
        }
        return mocks.get(purpose, "Mock response: no ANTHROPIC_API_KEY configured.")

    def complete(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        purpose: str = "chat",
        max_tokens: int = 1024,
    ) -> str:
        """
        messages: list of {"role": "user"|"assistant", "content": "..."}
        Returns raw text content of the model's reply.
        """
        if not self.enabled:
            return self._mock_response(purpose)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
            )
            return "".join(block.text for block in response.content if block.type == "text")
        except APIError as e:
            logger.error(f"Anthropic API error during '{purpose}': {e}")
            return self._mock_response(purpose)

    def diagnose_incident(self, incident_context: str) -> Dict:
        system = (
            "You are ACOP's Diagnosis Agent, an expert SRE reasoning system. "
            "Given telemetry and incident context from a Kubernetes cluster, identify the most "
            "likely root cause. Respond ONLY with valid JSON: "
            '{"root_cause": str, "confidence": float 0-1, "evidence": [str, ...]}'
        )
        raw = self.complete(system, [{"role": "user", "content": incident_context}], purpose="diagnosis")
        return self._safe_json(raw, default={"root_cause": raw, "confidence": 0.5, "evidence": []})

    def propose_remediation(self, incident_context: str, root_cause: str) -> Dict:
        system = (
            "You are ACOP's Remediation Agent. Given an incident and its diagnosed root cause, "
            "propose exactly one concrete remediation action for a Kubernetes cluster. "
            "Valid action_type values: restart_pod, scale_deployment, drain_node, rollback, patch_config. "
            "Respond ONLY with valid JSON: "
            '{"action_type": str, "reasoning": str, "confidence": float 0-1, "payload": object}'
        )
        user_msg = f"Incident context:\n{incident_context}\n\nDiagnosed root cause:\n{root_cause}"
        raw = self.complete(system, [{"role": "user", "content": user_msg}], purpose="remediation")
        return self._safe_json(raw, default={
            "action_type": "restart_pod", "reasoning": raw, "confidence": 0.5, "payload": {}
        })

    def chat(self, conversation: List[Dict[str, str]], context: Optional[str] = None) -> str:
        system = (
            "You are ACOP Assistant, the conversational interface of an Autonomous Cloud Operations "
            "Platform. Help the operator understand cluster health, incidents, and remediation history. "
            "Be concise and precise, like a senior SRE."
        )
        if context:
            system += f"\n\nCurrent cluster context:\n{context}"
        return self.complete(system, conversation, purpose="chat")

    @staticmethod
    def _safe_json(raw: str, default: Dict) -> Dict:
        try:
            start = raw.index("{")
            end = raw.rindex("}") + 1
            return json.loads(raw[start:end])
        except (ValueError, json.JSONDecodeError):
            logger.warning(f"Failed to parse JSON from LLM response, using default. Raw: {raw[:200]}")
            return default


claude_client = ClaudeClient()
