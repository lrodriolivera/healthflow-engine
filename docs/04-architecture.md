# Arquitectura Técnica: HealthFlow Engine

## Principio Fundamental

**IA en design-time, código compilado en runtime.**

- Claude AI **genera** transformaciones, reglas de routing, y configuración
- Código Python **ejecuta** esas transformaciones en producción (<1ms por mensaje)
- Claude AI **interviene** solo en excepciones (5% slow-path) y operaciones
- Healthcare exige **determinismo**: mismo input → mismo output, siempre

## Componentes

### 1. Protocol Adapters (No-IA, deterministas)

```
MLLPListener (asyncio TCP server)
├── Multi-puerto (1 puerto = 1 flujo, como en IRIS)
├── MLLP framing (VT/FS/CR)
├── TLS opcional (MLLP+S)
├── ACK automático configurable
└── Thread pool por puerto

SOAPAdapter (aiohttp)
├── WSDL parsing automático
├── Pre-emptive Basic Auth
├── SSL/TLS configurable
└── Timeout + retry

RESTAdapter (FastAPI)
├── Webhook receiver
├── FHIR R4 server
└── API management

OutboundAdapters
├── MLLPSender (TCP client con retry)
├── SOAPClient (aiohttp con MTOM)
├── RESTClient (httpx async)
└── SMTPSender (aiosmtplib)
```

### 2. Message Bus (NATS JetStream)

```
Tópicos:
  flow.{port}.inbound     — mensaje recibido por adapter
  flow.{port}.routed      — mensaje ruteado a destino(s)
  flow.{port}.transformed — mensaje transformado
  flow.{port}.outbound    — mensaje listo para enviar
  flow.{port}.ack         — ACK recibido del destino
  flow.{port}.error       — mensaje con error
  flow.{port}.dlq         — dead letter queue (después de N retries)

Garantías:
  - At-least-once delivery
  - Ordering por flujo (por puerto)
  - Replay desde cualquier punto (audit)
  - Persistencia en disco (JetStream)
```

### 3. HL7 Parser (Core, no-IA)

```python
class HL7Message:
    """Parser ER7 puro — sin dependencia de schemas."""
    
    raw: str                          # Mensaje original
    segments: list[HL7Segment]        # Segmentos parseados
    msh: MSHSegment                   # Header parseado
    
    def get(self, path: str) -> str:
        """Acceso tipo IRIS: get("PID-3.1") o get("PID:3.1")"""
    
    def get_segment(self, name: str, index: int = 0) -> HL7Segment:
        """Obtener segmento por nombre (soporta múltiples OBR, OBX, etc.)"""
    
    def count_segments(self, name: str) -> int:
        """Contar segmentos de un tipo (multi-OBR, multi-FT1)"""
    
    def set(self, path: str, value: str) -> None:
        """Modificar campo (crea clon interno)"""
    
    def to_er7(self) -> str:
        """Serializar de vuelta a ER7"""
    
    def to_fhir(self, mapping: str = "default") -> dict:
        """Convertir a FHIR Bundle usando mapping configurado"""
    
    @staticmethod
    def generate_ack(original: 'HL7Message', code: str = "AA") -> str:
        """Generar ACK/NAK para el mensaje"""
```

### 4. Routing Engine (Determinista + AI slow-path)

```
Capa 1: Reglas compiladas (Python dict/match, <1ms)
├── Por MSH.9 (tipo de mensaje)
├── Por MSH.3/MSH.5 (sistemas origen/destino)
├── Por PV1.3 (ubicación/servicio)
├── Por OBR.4 (tipo de estudio)
├── Por contenido de cualquier campo
└── Fan-out a múltiples destinos

Capa 2: AI Router (Claude API, ~500ms, solo si Capa 1 no matchea)
├── Clasificación del mensaje
├── Determinación de destinos
├── Logging de la decisión
└── Generación automática de regla para Capa 1
    (la próxima vez, el mismo patrón usa Capa 1)
```

### 5. Transformation Engine

```
Design-time (Claude AI):
├── Input: especificación en lenguaje natural
│   "Transformar ADT^A08 de SAP a FHIR Patient update"
├── Output: código Python de transformación
├── Validación: ejecutar con mensajes de prueba
└── Deploy: compilar y registrar en runtime

Runtime (Python compilado):
├── Ejecutar transformación (<1ms)
├── Lookup tables en Redis (< 0.1ms)
├── Logging de input/output para audit
└── Métricas de transformación (OpenTelemetry)
```

### 6. AI Agents Layer

```
TransformDesigner (Claude Opus)
├── Genera código de transformación desde especificación NL
├── Valida contra mensajes de prueba
└── Versiona y registra transformaciones

SelfHealer (Claude Sonnet)
├── Detecta errores en logs
├── Analiza patrón del error
├── Genera fix candidato
├── Ejecuta en sandbox
└── Propone PR para revisión humana

AnomalyDetector (ML local, no LLM)
├── Baseline estadístico (volumen, distribución, tiempos)
├── Detección de drift en estructura de mensajes
├── Alertas predictivas
└── Dashboard de anomalías

OpsAgent (Claude Sonnet + tool-use)
├── ChatOps: "¿por qué falló el mensaje 12345?"
├── Tools: leer logs, consultar DB, ver trazas
├── Ejecutar acciones: restart adapter, deshabilitar flujo
└── Natural language management interface
```

### 7. Visual Trace (reemplazo del Visual Trace de IRIS)

```
OpenTelemetry traces:
├── Span por cada etapa (adapter → router → transform → outbound)
├── Attributes: message_type, patient_id, session_id
├── Events: contenido del mensaje en cada etapa
├── Status: OK, ERROR con detalles
└── Links: correlación entre mensajes relacionados

UI (Next.js):
├── Timeline visual del mensaje
├── Contenido HL7 con syntax highlighting
├── Diff entre input y output de transformaciones
├── Filtros por tipo, fecha, estado, paciente
└── Drill-down a logs y métricas
```

### 8. Data Model (PostgreSQL)

```
Tablas principales:
├── tenants          — Multi-tenancy
├── flows            — Definición de flujos (equiv. a Production items)
├── adapters         — Configuración de adapters (tipo, puerto, SSL, auth)
├── routing_rules    — Reglas de routing compiladas
├── transforms       — Código de transformación versionado
├── lookup_tables    — Tablas clave-valor (equiv. a globals)
├── credentials      — Credenciales encriptadas (AES-256)
├── audit_log        — Log inmutable ATNA-compliant
├── message_log      — Resumen de mensajes procesados (TimescaleDB)
└── error_queue      — Dead letter queue con contexto para retry
```

## Stack Completo

| Capa | Tecnología | Justificación |
|------|-----------|---------------|
| Protocol (MLLP) | asyncio TCP | Nativo Python, performance suficiente |
| Protocol (HTTP) | FastAPI + uvicorn | Async, tipado, OpenAPI auto |
| Message Bus | NATS JetStream | Ligero, at-least-once, ordering, replay |
| Routing | Python dict/match | <1ms, determinista |
| Transform | Python compilado | Generado por AI, ejecutado nativo |
| AI Design | Claude API (Opus) | Mejor calidad para code generation |
| AI Ops | Claude API (Sonnet) | Balance costo/calidad para ops |
| AI Monitor | Scikit-learn / local | Sin latencia de API, sin costo |
| Database | PostgreSQL 16 | Config, audit, JSONB para schemas |
| Metrics DB | TimescaleDB | Time-series para volumen de mensajes |
| Cache | Redis | Lookup tables, session state |
| Observability | OpenTelemetry → Grafana | Estándar abierto, Visual Trace custom |
| Frontend | Next.js 14 | Dashboard, config UI, visual trace |
| Deploy | Docker + K8s / ECS | Estándar, portable |

## Flujo de un Mensaje (ejemplo ADT^A08)

```
1. MLLP Listener (puerto 31001) recibe frame MLLP
2. Extrae mensaje HL7, parsea MSH
3. Genera ACK inmediato (si configurado)
4. Publica en NATS: flow.31001.inbound
5. Routing Engine consume, evalúa reglas:
   - MSH.9 = "ADT^A08" → destinations: [LIS, RIS, Farmacia]
6. Para cada destino, publica: flow.31001.routed.{dest}
7. Transform Engine consume, aplica transformación compilada
8. Publica: flow.31001.transformed.{dest}
9. Outbound Adapter consume, envía por MLLP/SOAP/REST
10. Recibe ACK, publica: flow.31001.ack.{dest}
11. Todo el flujo traceado via OpenTelemetry
12. Si falla → retry (configurable) → DLQ → SelfHealer agent
```

## Fases de Implementación

### Fase 1: Core Engine (MVP)
- [ ] HL7v2 parser (ER7, todos los tipos)
- [ ] MLLP listener/sender (asyncio)
- [ ] Routing determinista (reglas en YAML/JSON)
- [ ] Lookup tables (PostgreSQL + Redis cache)
- [ ] ACK automático
- [ ] NATS JetStream como bus
- [ ] Visual Trace básico (OpenTelemetry + Grafana)
- [ ] API REST para management
- [ ] Docker Compose

### Fase 2: AI Layer
- [ ] Claude Transform Designer
- [ ] Claude Self-Healer
- [ ] Claude Ops Agent (ChatOps)
- [ ] Anomaly Detector (ML local)
- [ ] Dashboard frontend (Next.js)

### Fase 3: FHIR + Bridge
- [ ] FHIR R4 server
- [ ] v2→FHIR mapping engine
- [ ] FHIR Subscriptions
- [ ] Bulk Data ($export)
- [ ] SMART on FHIR auth

### Fase 4: Enterprise
- [ ] Multi-tenancy
- [ ] SOAP adapter genérico
- [ ] File/FTP/sFTP adapters
- [ ] MPI (Patient matching)
- [ ] Marketplace de conectores
- [ ] On-premise deployment guide
