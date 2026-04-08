# CLAUDE.md — HealthFlow Engine

## Project Context
AI-native healthcare integration engine that replaces InterSystems IRIS/Ensemble.
- **Language:** Python 3.12 (backend), TypeScript (frontend)
- **Framework:** FastAPI + asyncio (backend), Next.js 14 (frontend)
- **AI:** Claude API via Anthropic SDK
- **Message Bus:** NATS JetStream
- **Database:** PostgreSQL + TimescaleDB

## Communication
- Respond in **Spanish** unless the user writes in English.
- Use technical terms in their original language (HL7, MLLP, FHIR, SOAP, ACK, etc.).

## Architecture Principles

### The Hybrid Rule
- **Design-time:** Claude AI generates routing rules, transformation code, and configuration
- **Runtime:** Compiled Python executes those artifacts deterministically (<1ms per message)
- **Slow-path:** Claude AI handles the 5% of messages that don't match any rule (~500ms)
- **Operations:** Claude AI for diagnostics, self-healing, anomaly detection

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
      hl7/          # HL7v2 parser, ACK generator, segment handling
      fhir/         # FHIR R4 client and server
      routing/      # Deterministic routing engine + rules
      transform/    # Transformation engine (compiled transforms)
    agents/         # Claude AI agents (router, transformer, healer, monitor, ops)
    adapters/       # Protocol adapters (MLLP, SOAP, REST, FHIR)
    api/            # FastAPI REST API (management, configuration)
    models/         # SQLAlchemy models (config, audit, tenants)
  tests/            # pytest tests
frontend/           # Next.js dashboard, visual trace, config UI
docs/               # Architecture, standards reference, research
infra/              # Terraform / Docker
scripts/            # Utility scripts, test message senders
test_data/          # Sample HL7 messages, FHIR resources
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
- v2→FHIR mapping using HL7 v2-to-FHIR Implementation Guide
- RESTful API: CRUD + Search + $operations
- Subscriptions (R5 topic-based) for pub/sub

### Key Message Types
- ADT (A01/A02/A03/A04/A08/A28/A31/A40): Demographics, movements
- ORM/OML (O01/O21): Orders (lab, radiology, procedures)
- ORU/OUL (R01/R22): Results
- SIU (S12/S13/S14/S15): Scheduling
- DFT (P03): Financial transactions/charges
- MDM (T02): Clinical documents

## Testing
- `pytest` for backend tests
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
```
