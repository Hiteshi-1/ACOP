from typing import List, Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.llm.llm_client import llm_client
from app.models.incident import Incident
from app.models.cluster import Cluster
from app.websocket.manager import connection_manager
from app.core.security import get_current_user

router = APIRouter(tags=["Chat & Live Updates"])


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    cluster_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest, db: Session = Depends(get_db), user: str = Depends(get_current_user)):
    """
    Conversational interface: lets an operator ask ACOP questions like
    "why is payment-worker unhealthy?" or "what did the last remediation do?"
    Claude is given live cluster/incident context so answers are grounded.
    """
    context = None
    if payload.cluster_id:
        cluster = db.query(Cluster).filter(Cluster.id == payload.cluster_id).first()
        open_incidents = (
            db.query(Incident)
            .filter(Incident.cluster_id == payload.cluster_id, Incident.status != "resolved")
            .order_by(Incident.created_at.desc())
            .limit(10)
            .all()
        )
        if cluster:
            incident_lines = "\n".join(
                f"- [{i.severity.upper()}] {i.title} (status={i.status}, root_cause={i.root_cause or 'pending'})"
                for i in open_incidents
            ) or "No open incidents."
            context = f"Cluster: {cluster.name} ({cluster.provider})\nOpen incidents:\n{incident_lines}"

    conversation = [{"role": m.role, "content": m.content} for m in payload.messages]
    reply = llm_client.chat(conversation, context=context)
    return ChatResponse(reply=reply)


@router.websocket("/ws/live")
async def websocket_live_updates(websocket: WebSocket):
    """
    Real-time event stream for the dashboard: new incidents, agent cycle
    completions, and remediation outcomes are pushed here as they happen.
    """
    await connection_manager.connect(websocket)
    try:
        while True:
            # Keep the connection alive; clients don't need to send anything.
            await websocket.receive_text()
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)
