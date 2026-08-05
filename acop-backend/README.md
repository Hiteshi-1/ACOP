# ACOP Backend — Autonomous Cloud Operations Platform

Production-ready FastAPI backend implementing a multi-agent AI system for autonomous
Kubernetes operations: monitoring, forecasting, root-cause diagnosis, and remediation.

## Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │              ORCHESTRATOR                    │
                    │   (APScheduler background loop, every        │
                    │    AGENT_LOOP_INTERVAL_SECONDS)               │
                    └───────────────────┬───────────────────────────┘
                                        │
        ┌───────────────┬──────────────┼──────────────┬────────────────┐
        ▼               ▼              ▼               ▼
┌───────────────┐ ┌─────────────┐ ┌──────────────┐ ┌───────────────────┐
│ Monitoring    │ │ Prediction  │ │ Diagnosis    │ │ Remediation        │
│ Agent         │ │ Agent       │ │ Agent        │ │ Agent              │
│               │ │             │ │              │ │                    │
│ - Pulls pod/  │ │ - LSTM      │ │ - Claude LLM │ │ - Claude proposes  │
│   node status │ │   forecasts │ │   root-cause │ │   action           │
│   from K8s    │ │   CPU/mem   │ │   reasoning  │ │ - Auto-executes if │
│ - XGBoost     │ │   trajectory│ │ - RAG lookup │ │   confidence high  │
│   anomaly     │ │ - Early     │ │   (ChromaDB  │ │ - Else: queued for │
│   scoring     │ │   warnings  │ │   runbooks)  │ │   human approval   │
│ - Opens       │ │             │ │              │ │ - Executes via K8s │
│   Incidents   │ │             │ │              │ │   ops layer        │
└───────┬───────┘ └──────┬──────┘ └──────┬───────┘ └─────────┬──────────┘
        │                │               │                   │
        └────────────────┴───────────────┴───────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   PostgreSQL / SQLite    │
                    │ Clusters, Incidents,     │
                    │ Remediations, Metrics    │
                    └──────────────────────────┘
```

**Supporting layers:**
- `app/k8s/` — Kubernetes client + operations (restart pod, scale deployment, drain node, rollback, patch config). Runs against a real cluster (`incluster` or `kubeconfig` mode) or fully simulated `mock` mode.
- `app/ml/` — LSTM forecaster (TensorFlow/Keras) for resource-usage trajectories, XGBoost classifier for anomaly detection, both with statistical fallbacks when untrained.
- `app/rag/` — ChromaDB vector store using its built-in local ONNX embedder (no torch/transformers dependency), holding runbooks and resolved-incident history for retrieval-augmented diagnosis/remediation.
- `app/llm/` — Anthropic Claude client wrapper (diagnosis, remediation proposals, conversational chat), with deterministic mock fallback when no API key is set.
- `app/websocket/` — Live event broadcasting to dashboard clients.

## Quick Start (Demo Mode — no external dependencies required)

```bash
cd acop-backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Defaults already work: SQLite DB, K8S_MODE=mock, LLM mock fallback.
# Add your ANTHROPIC_API_KEY in .env to enable real Claude-powered reasoning.

uvicorn app.main:app --reload
```

Visit **http://localhost:8000/docs** for interactive Swagger UI.

> **Note:** On first run, ChromaDB downloads a small (~80MB) local embedding
> model automatically. This needs internet access once; it's then cached
> locally and every subsequent run is fully offline for RAG.

The orchestrator starts automatically on launch and runs a full
monitoring → prediction → diagnosis → remediation cycle every 60 seconds
(configurable via `AGENT_LOOP_INTERVAL_SECONDS`). You can also trigger a cycle
manually:

```bash
curl -X POST http://localhost:8000/api/v1/agents/run-cycle
```

## Running with Docker

```bash
cp .env.example .env   # set ANTHROPIC_API_KEY if you have one
docker compose up --build
```

This starts the backend + a PostgreSQL instance. Set `K8S_MODE=incluster` in
`.env` if deploying ACOP itself inside the cluster it manages, or `kubeconfig`
to point it at a cluster from your dev machine.

## Seeding the RAG Knowledge Base

Sample runbooks are included under `data/runbooks/`. Ingest them:

```bash
curl -X POST "http://localhost:8000/api/v1/agents/knowledge-base/ingest-runbooks?directory=data/runbooks"
```

Add your own `.md`/`.txt` runbooks to that directory and re-run the ingest
endpoint anytime. Resolved incidents are automatically fed back into the
knowledge base by the Remediation Agent, so ACOP's diagnostic quality
improves over time.

## Key API Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/clusters` | Register a cluster |
| GET | `/api/v1/clusters/{id}/live-pods` | Live pod status (real or mock) |
| GET | `/api/v1/incidents?status=open` | List incidents |
| POST | `/api/v1/metrics` | Ingest a metric snapshot |
| POST | `/api/v1/metrics/forecast` | LSTM forecast for a resource |
| POST | `/api/v1/metrics/anomaly-check` | XGBoost anomaly verdict |
| GET | `/api/v1/agents/status` | Orchestrator + agent run status |
| POST | `/api/v1/agents/run-cycle` | Manually trigger a full agent cycle |
| POST | `/api/v1/remediations/{id}/approve` | Approve/reject a queued remediation |
| POST | `/api/v1/chat` | Conversational ops assistant |
| WS | `/api/v1/ws/live` | Live incident/remediation event stream |

## Human-in-the-Loop Safety

Remediations only auto-execute when **both**:
1. `AUTO_REMEDIATION_ENABLED=true`, and
2. The LLM's proposal confidence ≥ `AUTO_REMEDIATION_CONFIDENCE_THRESHOLD` (default `0.8`)

Otherwise, remediations are queued with `requires_approval=true` and must be
approved via `POST /api/v1/remediations/{id}/approve` before execution —
ACOP never silently takes irreversible action on low-confidence diagnoses.

## Training the ML Models on Real Data

Both `lstm_forecaster.train(...)` (`app/ml/lstm_model.py`) and
`xgboost_detector.train(...)` (`app/ml/xgboost_model.py`) accept historical
data directly — wire them up to a scheduled retraining job once you have
enough `MetricSnapshot` history (and labeled anomalies for XGBoost) in your
database. Until trained, both fall back to statistically sound heuristics so
the system is usable from day one.

## Running Tests

```bash
pytest tests/ -v
```

## Project Structure

```
acop-backend/
├── app/
│   ├── main.py                 # FastAPI app, lifespan, router registration
│   ├── config.py               # Settings (env-driven)
│   ├── database.py              # SQLAlchemy engine/session
│   ├── models/                  # ORM models: Cluster, Node, Incident, Remediation, MetricSnapshot
│   ├── schemas/                  # Pydantic request/response schemas
│   ├── api/routes/               # clusters, incidents, remediations, metrics, agents, chat
│   ├── agents/                   # base_agent, monitoring, prediction, diagnosis, remediation, orchestrator
│   ├── ml/                       # lstm_model, xgboost_model, anomaly_detector
│   ├── rag/                      # chroma_client, knowledge_base, retriever
│   ├── k8s/                      # client, operations
│   ├── llm/                      # claude_client
│   ├── core/                     # security (JWT), logging_config
│   └── websocket/                # manager (live dashboard updates)
├── data/runbooks/                 # Sample runbook markdown for RAG seeding
├── tests/                          # pytest suite
├── requirements.txt
├── .env.example
├── Dockerfile
└── docker-compose.yml
```
