# HealthFlow Engine

**Motor de integración healthcare AI-native que reemplaza InterSystems IRIS.**

## El Problema

InterSystems IRIS/Ensemble es el estándar de facto para integraciones hospitalarias, pero:
- **Caro:** Licencias $200K-$1M+/año, implementación $500K-$5M+
- **Vendor lock-in:** ObjectScript (lenguaje propietario), globals (storage propietario), BPL/DTL (formatos propietarios)
- **Talento escaso:** Pool de desarrolladores ObjectScript ~1/1000 del de Python
- **Deploy arcaico:** Sin CI/CD nativo, sin containers, importación manual de XML

## La Solución

HealthFlow Engine es un motor de integración **híbrido**: adaptadores de protocolo tradicionales + bus de mensajes + IA (Claude) para diseño, operaciones y auto-reparación.

### Arquitectura Híbrida

```
┌────────────────────────────────────────────────────────────────┐
│                    HEALTHFLOW ENGINE                            │
│                                                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │   MLLP   │  │   SOAP   │  │   REST   │  │   FHIR   │     │
│  │ Adapter  │  │ Adapter  │  │ Adapter  │  │ Server   │     │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘     │
│       └──────────────┼───────────────┼──────────────┘          │
│                      ▼                                         │
│  ┌─────────────────────────────────────────────────────┐      │
│  │           MESSAGE BUS (NATS JetStream)              │      │
│  │        Guaranteed delivery, ordering, replay        │      │
│  └───────────────────┬─────────────────────────────────┘      │
│                      ▼                                         │
│  ┌─────────────────────────────────────────────────────┐      │
│  │         DETERMINISTIC ROUTING (<1ms, 95%)           │      │
│  │              ┌──────────────────┐                   │      │
│  │    miss ───> │ AI ROUTING AGENT │ (~500ms, 5%)      │      │
│  │              └──────────────────┘                   │      │
│  └───────────────────┬─────────────────────────────────┘      │
│                      ▼                                         │
│  ┌─────────────────────────────────────────────────────┐      │
│  │         TRANSFORMATION ENGINE                       │      │
│  │  ┌──────────────┐    ┌─────────────────────┐       │      │
│  │  │  Compiled     │    │ AI Transform        │       │      │
│  │  │  Transforms   │◄───│ Designer (Claude)   │       │      │
│  │  │  (runtime)    │    │ (design-time)       │       │      │
│  │  └──────────────┘    └─────────────────────┘       │      │
│  └───────────────────┬─────────────────────────────────┘      │
│                      ▼                                         │
│  ┌─────────────────────────────────────────────────────┐      │
│  │    OUTBOUND ADAPTERS (MLLP, SOAP, REST, sFTP)      │      │
│  └─────────────────────────────────────────────────────┘      │
│                                                                │
│  ┌─────────────────────────────────────────────────────┐      │
│  │              AI OPERATIONS LAYER                    │      │
│  │  • Self-healing: auto-fix broken transforms         │      │
│  │  • Anomaly detection: drift alerts                  │      │
│  │  • ChatOps: "why did message 12345 fail?"          │      │
│  │  • Auto-onboarding: new interface via NL            │      │
│  └─────────────────────────────────────────────────────┘      │
│                                                                │
│  ┌─────────────────────────────────────────────────────┐      │
│  │         OBSERVABILITY (OpenTelemetry)               │      │
│  │    Traces + Metrics + Logs → Visual Trace UI        │      │
│  └─────────────────────────────────────────────────────┘      │
└────────────────────────────────────────────────────────────────┘
```

### Principio Clave: IA en Design-Time, Código Compilado en Runtime

- **Claude genera** transformaciones y reglas de routing
- **Código Python compilado ejecuta** esas transformaciones en producción (<1ms)
- **Claude interviene** solo en excepciones (5% slow-path) y operaciones

### Costo: 78-89% menos que IRIS

| Concepto | IRIS Enterprise | HealthFlow Engine |
|----------|----------------|-------------------|
| Licencia/Infra | $200K-$1M/año | ~$24K/año (cloud) |
| Claude API (5% msgs) | N/A | ~$9K/año |
| Talento | ObjectScript (escaso, caro) | Python/TypeScript (abundante) |
| **Total** | **$200K-$1M+** | **~$33K/año** |

## Stack Técnico

- **Backend:** Python 3.12 + FastAPI + asyncio
- **Protocol Adapters:** asyncio TCP (MLLP), aiohttp (SOAP/REST)
- **Message Bus:** NATS JetStream
- **AI:** Claude API (Anthropic) — Sonnet para routing/transform, Opus para diseño complejo
- **Frontend:** Next.js 14 (dashboard, visual trace, configuration)
- **Database:** PostgreSQL (config, audit) + TimescaleDB (metrics)
- **Observability:** OpenTelemetry → Grafana
- **Deploy:** Docker + Kubernetes / ECS Fargate

## Estándares Soportados

- **HL7 v2.x** (2.3 - 2.8): Parser ER7, MLLP listener/sender, ACK automático
- **HL7 FHIR R4/R5**: Server RESTful, Subscriptions, Bulk Data
- **SOAP/WSDL**: Cliente genérico con pre-emptive auth
- **IHE**: PIXm/PDQm, MHD, ATNA audit trail
- **DICOM**: DICOMweb proxy (WADO-RS, QIDO-RS)

## Origen

Nacido de 6+ meses migrando 30+ flujos HL7 (LIS/RIS) para UC CHRISTUS (Chile), desde Mirth Connect/Oracle SOA hacia InterSystems IRIS. Cada decisión arquitectónica está validada contra problemas reales de integración hospitalaria.

## Quick Start

```bash
# Clonar
git clone https://github.com/lrodriolivera/healthflow-engine.git
cd healthflow-engine

# Levantar con Docker
docker-compose up -d

# Dashboard
open http://localhost:3000

# Enviar mensaje HL7 de prueba
python scripts/send_test_hl7.py --port 2575 --message test_data/adt_a01.hl7
```

## Roadmap

- **Fase 1 (actual):** Core engine — HL7v2 parser, MLLP adapter, routing determinista, Visual Trace
- **Fase 2:** AI layer — Claude para diseño de transformaciones, self-healing, ChatOps
- **Fase 3:** FHIR server + v2↔FHIR bridge
- **Fase 4:** Multi-tenant SaaS + marketplace de conectores

## Licencia

MIT
