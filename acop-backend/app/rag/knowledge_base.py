"""
Knowledge base management: ingest runbook documents (markdown/text) into
ChromaDB so the Diagnosis/Remediation agents can retrieve relevant precedent
via app.rag.retriever.
"""
import os
import glob
import hashlib
from typing import List, Dict

from app.rag.chroma_client import chroma_manager
from app.core.logging_config import logger


def _doc_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def ingest_text(content: str, metadata: Dict) -> str:
    doc_id = _doc_id(content)
    chroma_manager.collection.upsert(ids=[doc_id], documents=[content], metadatas=[metadata])
    return doc_id


def ingest_runbooks_directory(directory: str) -> Dict:
    """Ingest every .md/.txt file in `directory` as a separate runbook document."""
    files = glob.glob(os.path.join(directory, "*.md")) + glob.glob(os.path.join(directory, "*.txt"))
    ingested = []
    for filepath in files:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        doc_id = ingest_text(content, metadata={"source": os.path.basename(filepath), "type": "runbook"})
        ingested.append({"file": os.path.basename(filepath), "doc_id": doc_id})
    logger.info(f"Ingested {len(ingested)} runbook documents from {directory}")
    return {"ingested_count": len(ingested), "documents": ingested}


def add_incident_resolution(incident_title: str, root_cause: str, remediation_summary: str, outcome: str):
    """
    After an incident is resolved, feed the resolution back into the knowledge base
    so future similar incidents benefit from this precedent (continuous learning loop).
    """
    content = (
        f"INCIDENT: {incident_title}\n"
        f"ROOT CAUSE: {root_cause}\n"
        f"REMEDIATION APPLIED: {remediation_summary}\n"
        f"OUTCOME: {outcome}"
    )
    return ingest_text(content, metadata={"type": "resolved_incident", "source": "incident_history"})


def list_documents(limit: int = 50) -> List[Dict]:
    result = chroma_manager.collection.get(limit=limit)
    docs = []
    for i, doc_id in enumerate(result["ids"]):
        docs.append({
            "id": doc_id,
            "content_preview": result["documents"][i][:200],
            "metadata": result["metadatas"][i],
        })
    return docs
