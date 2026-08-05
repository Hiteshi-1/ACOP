"""
Retrieval interface used by agents to pull relevant runbook / historical
incident context before asking the LLM to diagnose or propose remediation.
"""
from typing import List, Dict

from app.rag.chroma_client import chroma_manager
from app.core.logging_config import logger


def retrieve_relevant_context(query: str, n_results: int = 3) -> List[Dict]:
    try:
        if chroma_manager.collection.count() == 0:
            return []
        results = chroma_manager.collection.query(query_texts=[query], n_results=n_results)
        matches = []
        for i in range(len(results["ids"][0])):
            matches.append({
                "id": results["ids"][0][i],
                "content": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if results.get("distances") else None,
            })
        return matches
    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}")
        return []


def build_context_block(query: str, n_results: int = 3) -> str:
    """Formats retrieved documents into a text block ready to inject into an LLM prompt."""
    matches = retrieve_relevant_context(query, n_results)
    if not matches:
        return "No relevant historical runbooks or precedent found in knowledge base."

    lines = ["Relevant historical context from ACOP knowledge base:"]
    for m in matches:
        source = m["metadata"].get("source", "unknown")
        lines.append(f"\n---\nSource: {source}\n{m['content'][:800]}")
    return "\n".join(lines)
