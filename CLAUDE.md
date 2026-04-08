# CLAUDE.md — HealthFlow Engine

## Project Context
AI-native healthcare integration engine that replaces InterSystems IRIS/Ensemble.
- **Language:** Python 3.12 (backend), TypeScript (frontend)
- **Framework:** FastAPI + asyncio (backend), Next.js 14 (frontend)
- **AI:** Claude (Opus + Sonnet) via AWS Bedrock (boto3)
- **Message Bus:** NATS JetStream
- **Database:** PostgreSQL + TimescaleDB
- **Cache:** Redis
- **Observability:** OpenTelemetry → Grafana/Tempo

## Communication
- Respond in **Spanish** unless the user writes in English.
- Use technical terms in their original language (HL7, MLLP, FHIR, SOAP, ACK, etc.).

## Architecture Principles

### The Hybrid Rule
- **Design-time:** Claude AI generates routing rules, transformation code, and configuration
- **Runtime:** Compiled Python executes those artifacts deterministically (<1ms per message)
- **Slow-path:** Claude AI handles the 5% of messages that don't match any rule (~500ms)
- **Operations:** Claude AI for diagnostics, self-healing, anomaly detection

### AI Agents (the core of the product)
- **TransformDesigner** (Opus): Generates Python transform code from natural language specs
- **AI Router** (Sonnet): Routes unmatched messages, auto-generates deterministic rules
- **SelfHealer** (Sonnet): Diagnoses errors, generates fixes, tests in sandbox
- **OpsAgent** (Sonnet + tool_use): ChatOps interface for natural language operations
- **AnomalyDetector** (local ML): Statistical baseline, drift detection, no LLM needed

### NEVER do these:
1. **Put Claude in the hot path** for every message — latency and cost make it unviable
2. **Ignore HL7v2** — it's 80%+ of real hospital traffic, FHIR-only is not realistic
3. **Vendor lock-in** — use standard formats (FHIR R4 canonical), standard languages (Python/TS), containers
4. **Skip audit trail** — healthcare requires ATNA-compliant logging of every message
5. **Assume determinism from LLMs** — AI generates code, code executes deterministically

## Directory Structure
```
backend/
  app/
    core/
      hl7/            # HL7v2 parser, ACK generator, segment handling
      fhir/           # FHIR R4 resources, v2→FHIR mapper, RESTful server
      routing/        # Deterministic routing engine + rules
      transform/      # Sandboxed transformation engine (compiled transforms)
      pipeline.py     # Message pipeline orchestrator (MLLP→NATS→Route→Transform→Outbound)
      loader.py       # Startup loader (DB→runtime config)
    agents/           # Claude AI agents via AWS Bedrock
      bedrock.py      # Bedrock Converse API client wrapper
      base.py         # BaseAgent with agentic loop + tool_use
      transform_designer.py  # Opus — code generation
      router.py       # Sonnet — slow-path routing
      self_healer.py  # Sonnet — error diagnosis
      ops.py          # Sonnet — ChatOps
      anomaly_detector.py  # Local ML — no LLM
      manager.py      # AgentManager
    adapters/         # Protocol adapters (MLLP, SOAP)
    api/              # FastAPI REST API (schemas + routes)
    bus/              # NATS JetStream client
    cache/            # Redis client
    models/           # SQLAlchemy models (11 tables)
    middleware/       # Tenant isolation middleware
    config.py         # Pydantic Settings (HF_ prefix)
    db.py             # Async SQLAlchemy engine
    telemetry.py      # OpenTelemetry setup
  alembic/            # Database migrations
  tests/              # pytest tests (142+)
frontend/             # Next.js 14 dashboard (Tailwind CSS)
  src/app/            # Pages: Dashboard, Flows, Messages, Agents
docs/                 # Architecture, standards reference, research
infra/                # OTEL collector, Tempo, Grafana provisioning
scripts/              # Utility scripts, test message senders
test_data/            # Sample HL7 messages, FHIR resources
```

## Healthcare Standards Reference

### HL7 v2.x
- Parser must handle ER7 (pipe-delimited) with configurable delimiters from MSH.2
- MLLP framing: VT (0x0B) + message + FS (0x1C) + CR (0x0D)
- ACK: MSA.1 = AA/AE/AR, MSA.2 = original MSH.10
- Z-segments: preserve in transit, never reject unknown segments
- Segment separator: CR (0x0D), normalize LF→CR on input

### HL7 FHIR R4
- FHIR R4 as canonical internal format
- v2→FHIR mapping: ADT→Patient+Encounter, ORM/OML→ServiceRequest, ORU→DiagnosticReport+Observation
- RESTful API: CRUD + Search + $convert
- Subscriptions (R5 topic-based) for pub/sub

### Key Message Types
- ADT (A01/A02/A03/A04/A08/A28/A31/A40): Demographics, movements
- ORM/OML (O01/O21): Orders (lab, radiology, procedures)
- ORU/OUL (R01/R22): Results
- SIU (S12/S13/S14/S15): Scheduling
- DFT (P03): Financial transactions/charges
- MDM (T02): Clinical documents

## Configuration
All settings use the `HF_` prefix and load from `.env`:
```bash
HF_DATABASE_URL=postgresql+asyncpg://healthflow:healthflow@localhost:5432/healthflow
HF_NATS_URL=nats://localhost:4222
HF_REDIS_URL=redis://localhost:6379
HF_AWS_REGION=us-east-1
HF_AWS_ACCESS_KEY_ID=...
HF_AWS_SECRET_ACCESS_KEY=...
HF_BEDROCK_MODEL_SONNET=us.anthropic.claude-sonnet-4-6-20250514-v1:0
HF_BEDROCK_MODEL_OPUS=us.anthropic.claude-opus-4-6-20250514-v1:0
```

## Testing
- `pytest` for backend tests (142+ tests)
- Test HL7 messages in `test_data/`
- MLLP test sender: `scripts/send_test_hl7.py`
- Run all tests: `pytest tests/ -v`

## Development
```bash
# Backend
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm install && npm run dev

# Full stack
docker-compose up -d

# Run tests
pytest tests/ -v
```
