# ATS AI-Powered Multi-Agent Hiring System

Retrieval-Augmented Insights · 8 Specialized Agents · MCP-Enabled Recommendations · Evaluation & Optimization

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      Presentation Layer                         │
│            Dashboard · Reports · API Endpoints · Alerts         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                     Orchestration Layer                         │
│         Coordinator Agent  ←→  Routing Agent                    │
└──────────┬──────────────────────────────────────────────────────┘
           │ dispatches to
┌──────────▼──────────────────────────────────────────────────────┐
│                  Specialist Insight Agents                       │
│  Sourcing Quality · Improvement Action · Resource Optimization  │
│  Offer Insights · Pipeline Health                               │
└──────────┬──────────────────────────────────────────────────────┘
           │ validated by
┌──────────▼──────────────────────────────────────────────────────┐
│                 Governance & Support Layer                       │
│           Evaluation Agent (Judge) · Optimization Agent         │
└──────────┬──────────────────────────────────────────────────────┘
           │
┌──────────▼──────────────────────────────────────────────────────┐
│              Data Ingestion & Knowledge Layer                    │
│  PostgreSQL (structured) · ChromaDB (vectors) · Redis (cache)   │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Roster

| # | Agent | Role | Model Tier |
|---|-------|------|------------|
| 1 | **Coordinator** | Orchestrates the full workflow & assembles final output | Opus (highest) |
| 2 | **Routing** | Selects which agents to invoke for a given query | Haiku (fast) |
| 3 | **Sourcing Quality** | Analyses which candidate channels deliver quality | Sonnet |
| 4 | **Improvement Action** | Translates rejection patterns into prioritised fixes (MCP) | Sonnet |
| 5 | **Resource Optimization** | Balances interviewer workload & capacity | Sonnet |
| 6 | **Offer Insights** | Tracks offer outcomes & compensation signals | Sonnet |
| 7 | **Pipeline Health** | Monitors funnel bottlenecks & stuck candidates | Sonnet |
| 8 | **Evaluation (Judge)** | Validates agent outputs for accuracy & evidence | Haiku |
| 9 | **Optimization** | Monitors cost/latency & recommends efficiency improvements | Haiku |

---

## Project Structure

```
ats_multi_agent_hiring/
├── app/                        # FastAPI application & API endpoints
│   └── api/v1/endpoints/
├── agents/                     # All AI agents
│   ├── base/                   # Shared base class for all agents
│   ├── coordinator/            # Coordinator Agent (Orchestrator)
│   ├── routing/                # Routing Agent (task selector)
│   ├── insight/                # 5 Specialist Insight Agents
│   │   ├── sourcing_quality/
│   │   ├── improvement_action/ # + MCP integration
│   │   ├── resource_optimization/
│   │   ├── offer_insights/
│   │   └── pipeline_health/
│   └── support/                # 2 Support / Governance Agents
│       ├── evaluation/
│       └── optimization/
├── orchestration/              # Workflow state machines & scenarios
│   ├── workflows/
│   ├── state/
│   └── scenarios/              # Fix Slow Hiring, Balance Workload, etc.
├── ingestion/                  # Data Ingestion Layer (ETL)
│   ├── pipeline/
│   ├── parsers/
│   ├── connectors/
│   └── validators/
├── rag/                        # Retrieval-Augmented Generation
│   ├── retriever/
│   ├── embeddings/
│   └── chunking/
├── vector_store/               # ChromaDB client & collection management
│   ├── chroma/
│   └── collections/
├── database/                   # PostgreSQL ORM models & repositories
│   ├── models/
│   ├── migrations/             # Alembic migrations
│   ├── repositories/
│   └── sessions/
├── shared/                     # Cross-cutting concerns
│   ├── contracts/              # Agent output schemas (structured contracts)
│   ├── models/                 # Shared Pydantic models
│   ├── utils/
│   ├── exceptions/
│   └── constants/
├── platform/                   # Key Architectural Services
│   ├── monitoring/             # OpenTelemetry, Prometheus, Jaeger
│   ├── memory/                 # Agent short/long-term memory
│   ├── security/               # Auth, secrets, rate limiting
│   ├── events/                 # Redis pub/sub, event bus
│   ├── mcp/                    # Internal MCP server & tools
│   │   └── tools/              # search_similar_interventions, etc.
│   └── compliance/             # Audit logging, PII detection
├── configs/                    # Settings & logging configuration
│   ├── settings.py
│   ├── logging.yaml
│   └── environments/           # Per-environment .env files
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docker/
│   ├── app/Dockerfile          # Multi-stage: development + production
│   ├── postgres/init.sql
│   └── chromadb/
├── scripts/
│   ├── setup.sh                # One-time dev setup
│   ├── migrate.sh              # Alembic wrapper
│   ├── seed_data.py
│   └── health_check.sh
├── docker-compose.yml
├── docker-compose.override.yml # Dev overrides (hot-reload, exposed ports)
├── pyproject.toml              # Poetry project & tool config
├── alembic.ini
└── .env.example
```

---

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.11+ | [python.org](https://www.python.org) |
| Poetry | 1.8+ | `curl -sSL https://install.python-poetry.org \| python3 -` |
| Docker Desktop | latest | [docker.com](https://www.docker.com) |
| Git | any | — |

---

## Quick Start

### 1. Clone & configure

```bash
git clone <repo-url>
cd ats_multi_agent_hiring
cp .env.example .env
# Edit .env and set OPENAI_API_KEY
```

### 2. One-command setup (installs deps + starts services + migrates DB)

```bash
bash scripts/setup.sh
```

### 3. Start the app (hot-reload dev mode)

```bash
# Option A — local Python process
poetry run uvicorn app.main:app --reload

# Option B — full Docker stack
docker compose up
```

### 4. Verify everything is running

```bash
bash scripts/health_check.sh

# Service URLs:
#   App        http://localhost:8080
#   API docs   http://localhost:8080/docs
#   ChromaDB   http://localhost:8001
#   PostgreSQL localhost:5432
#   Redis      localhost:6379
```

---

## Common Commands

```bash
# Install / update dependencies
poetry install
poetry add <package>
poetry add --group dev <package>

# Database migrations
bash scripts/migrate.sh                                          # apply all pending
bash scripts/migrate.sh revision --autogenerate -m "add_table"  # create new migration
bash scripts/migrate.sh downgrade -1                             # roll back one step

# Run tests
poetry run pytest                        # all tests
poetry run pytest tests/unit/            # unit only
poetry run pytest -m "not integration"   # skip integration

# Code quality
poetry run black .
poetry run ruff check .
poetry run mypy .

# Docker helpers
docker compose up -d          # start all services in background
docker compose down           # stop all services
docker compose down -v        # stop + wipe volumes (fresh start)
docker compose logs -f app    # stream app logs
```

---

## Environment Variables

Copy `.env.example` → `.env`. Key variables:

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | Required — your OpenAI API key |
| `DATABASE_URL` | PostgreSQL async connection string |
| `CHROMA_TOKEN` | Bearer token for ChromaDB auth |
| `REDIS_URL` | Redis connection string |
| `OPENAI_MODEL_*` | Model selection per agent tier (all `gpt-4o-mini`) |

---

## Build Order (Step-by-Step Learning Path)

This project is built incrementally. Suggested order:

1. **Step 1** — Shared contracts & Pydantic models (`shared/`)
2. **Step 2** — Database models & Alembic migrations (`database/`)
3. **Step 3** — Vector store collections & ChromaDB client (`vector_store/`)
4. **Step 4** — Data ingestion pipeline (`ingestion/`)
5. **Step 5** — RAG layer: embeddings & retrieval (`rag/`)
6. **Step 6** — Base agent class & individual insight agents (`agents/`)
7. **Step 7** — MCP tools for Improvement Action Agent (`platform/mcp/`)
8. **Step 8** — Orchestration: workflows & state management (`orchestration/`)
9. **Step 9** — FastAPI app & API endpoints (`app/`)
10. **Step 10** — Platform services: monitoring, memory, compliance (`platform/`)

---

## License

MIT
