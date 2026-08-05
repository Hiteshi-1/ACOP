"""
ACOP — Autonomous Cloud Operations Platform
FastAPI application entry point.

Wires together: REST API routers, DB initialization, the multi-agent
orchestrator's background scheduler, and startup/shutdown lifecycle hooks.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import init_db
from app.core.logging_config import logger
from app.agents.orchestrator import orchestrator

from app.api.routes import clusters, incidents, remediations, metrics, agents, chat


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.APP_NAME} ({settings.APP_ENV})")
    init_db()
    orchestrator.start()
    yield
    orchestrator.stop()
    logger.info("ACOP shutdown complete.")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Autonomous Cloud Operations Platform — a multi-agent system that monitors "
        "Kubernetes clusters, forecasts resource trajectories with LSTM, classifies "
        "anomalies with XGBoost, diagnoses root causes with Claude + RAG (ChromaDB), "
        "and autonomously remediates incidents with human-in-the-loop approval gates."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clusters.router, prefix=settings.API_V1_PREFIX)
app.include_router(incidents.router, prefix=settings.API_V1_PREFIX)
app.include_router(remediations.router, prefix=settings.API_V1_PREFIX)
app.include_router(metrics.router, prefix=settings.API_V1_PREFIX)
app.include_router(agents.router, prefix=settings.API_V1_PREFIX)
app.include_router(chat.router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Health"])
def root():
    return {
        "service": settings.APP_NAME,
        "status": "online",
        "environment": settings.APP_ENV,
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "healthy"}
