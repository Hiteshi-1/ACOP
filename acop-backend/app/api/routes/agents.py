from fastapi import APIRouter, Depends

from app.agents.orchestrator import orchestrator
from app.core.security import get_current_user
from app.rag.knowledge_base import ingest_runbooks_directory, list_documents

router = APIRouter(prefix="/agents", tags=["Agent Orchestration"])


@router.get("/status")
def get_status():
    """Returns orchestrator + individual agent run status."""
    return orchestrator.status()


@router.post("/run-cycle")
def trigger_cycle(user: str = Depends(get_current_user)):
    """Manually triggers one full monitoring → prediction → diagnosis → remediation cycle."""
    return orchestrator.run_cycle()


@router.post("/knowledge-base/ingest-runbooks")
def ingest_runbooks(directory: str = "data/runbooks", user: str = Depends(get_current_user)):
    """Ingests all runbook markdown files from the given directory into the RAG knowledge base."""
    return ingest_runbooks_directory(directory)


@router.get("/knowledge-base/documents")
def get_knowledge_base_documents(limit: int = 50):
    return {"documents": list_documents(limit)}
