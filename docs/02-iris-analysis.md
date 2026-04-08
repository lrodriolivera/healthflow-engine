# Análisis Técnico: InterSystems IRIS/HealthShare/TrakCare

## 1. IRIS como Motor de Integración

### Production (unidad fundamental)
- Contenedor XML declarativo que orquesta flujos de mensajes
- Clase ObjectScript que extiende `Ens.Production` con `XData ProductionDefinition`
- 3 tipos de componentes: Business Services (BS), Business Processes (BP), Business Operations (BO)

### Business Services (Puntos de entrada)
- Escuchan en puerto o consultan fuente de datos
- Adapter inbound maneja protocolo (TCP/MLLP, HTTP, File, SQL)
- Generan mensajes internos de Ensemble

### Business Processes (Lógica de orquestación)
- **BPL (visual):** Flujos XML con `<call>`, `<if>`, `<while>`, `<assign>`, `<transform>`
- **ObjectScript puro:** Método `OnRequest()`, mayor control pero más complejo
- En UCCHRISTUS usamos ObjectScript puro por limitaciones de BPL con HL7 complejo

### Business Operations (Puntos de salida)
- Adapters outbound: MLLP sender, SOAP client, HTTP client, SMTP, File writer

### Adaptadores nativos
| Protocolo | Inbound | Outbound |
|-----------|---------|----------|
| HL7 MLLP | `EnsLib.HL7.Adapter.TCPInboundAdapter` | `EnsLib.HL7.Adapter.TCPOutboundAdapter` |
| HTTP/REST | `EnsLib.HTTP.InboundAdapter` | `EnsLib.HTTP.OutboundAdapter` |
| SOAP | `EnsLib.SOAP.InboundAdapter` | `EnsLib.SOAP.OutboundAdapter` |
| TCP | `EnsLib.TCP.InboundAdapter` | `EnsLib.TCP.OutboundAdapter` |
| File | `EnsLib.File.InboundAdapter` | `EnsLib.File.OutboundAdapter` |
| FTP | `EnsLib.FTP.InboundAdapter` | `EnsLib.FTP.OutboundAdapter` |
| SQL | `EnsLib.SQL.InboundAdapter` | `EnsLib.SQL.OutboundAdapter` |
| Email | `EnsLib.EMail.InboundAdapter` | `EnsLib.EMail.OutboundAdapter` |
| FHIR | `HS.FHIRServer.*` | via REST adapter |

### HL7 v2.x en IRIS
- Parsing automático a `EnsLib.HL7.Message` con `GetValueAt("PID:3.1")`
- Schemas para HL7 2.1-2.8
- ACK automático configurable (Immediate, Application, Never)
- Routing Rules visual basadas en campos HL7

### DTL (Data Transformation Language)
- Mapeo visual campo-a-campo entre mensajes
- Funciones: lookup, substring, concatenación
- Condiciones, iteración sobre segmentos repetidos
- **Limitaciones encontradas:** SetValueAt falla post-reimport, GetValueAt falla sin EVN

### Visual Trace
- Recorrido completo del mensaje (BS→BP→BO)
- Contenido en cada etapa, tiempos, errores, logs
- La herramienta más valorada por soporte
- **Limitación:** Propietario, no exportable, no integrable con herramientas estándar

### Otros componentes
- **Record Maps:** Estructura de archivos planos → objetos
- **Lookup Tables:** Clave-valor en globals (`^Ens.LookupTable`)
- **Credentials:** Almacén encriptado reutilizable
- **Alerting:** Email/SMS configurable por error patterns

## 2. IRIS como Repositorio Clínico (HealthShare)

### SDA (Summary Document Architecture)
- Modelo canónico XML/JSON para datos clínicos normalizados
- Categorías: Patient, Encounter, Diagnosis, Medication, LabOrder, LabResult, RadOrder, Allergy, Procedure
- DTLs estándar para transformar HL7/CDA/FHIR → SDA
- Almacenamiento en UCR (Unified Clinical Record)

### Clinical Viewer
- Visor web de historia clínica unificada
- Timeline, consolidación multi-sistema, documentos, gráficas

### MPI (Master Patient Index)
- MPIID único por paciente
- Matching determinístico + probabilístico
- Múltiples identificadores por paciente
- Detección y resolución de duplicados
- Integración nativa con flujo ADT

### Consent Management
- Gestión de consentimientos para compartir datos
- Cumplimiento HIPAA, GDPR, normativas locales

## 3. TrakCare (EHR/HIS)

### Qué es
Sistema de información hospitalaria completo construido sobre IRIS:
- ADT: Registro de pacientes, episodios, camas, transferencias
- CPOE: Órdenes médicas, laboratorio, imágenes, farmacia
- Farmacia: Prescripción, dispensación, interacciones
- Laboratorio: Solicitudes, resultados, validación
- Radiología: Órdenes, informes, integración PACS
- Urgencias: Triage, flujo
- Quirófano: Programación, protocolos
- Facturación: Cargos, prestaciones, integración ERP/SAP
- Agenda: Citas, recursos
- Documentación: Notas, formularios

### Integración con IRIS
- Construido sobre la misma plataforma
- HL7v2 nativo (ADT, ORM, ORU, SIU, DFT)
- API REST/FHIR en versiones recientes
- Acceso directo a globals (no recomendado)

### Presencia global
- 26+ países, 450+ sitios
- Fuerte en Asia-Pacífico, Medio Oriente, LATAM (Chile, Brasil)

## 4. Pricing

| Concepto | Rango estimado |
|----------|---------------|
| Licencia IRIS (hospital mediano) | $200K-$500K+ (perpetua) |
| TrakCare licencia completa | $1M-$10M+ |
| Mantenimiento anual | $50K-$200K+ (18-22% de licencia) |
| Implementación | $500K-$5M+ |
| **Total 5 años** | **$1.5M-$15M+** |

Modelo: por cores de procesador + conexiones concurrentes + módulos adicionales.

## 5. Limitaciones (validadas en producción UCCHRISTUS)

### ObjectScript
- Sintaxis no estándar (`_` = concat, `$PIECE`, `$EXTRACT`)
- Pool de talento ~1/1000 de Python
- IDE limitado (VS Code extension básica)
- Sin debugger step-by-step confiable para producciones remotas
- Trampas: `Quit "value"` en Try → ERROR #1043, `New $NAMESPACE` no restaura

### Vendor Lock-in
- Datos en globals (no SQL estándar nativo)
- BPL/DTL en XML propietario
- SDA propietario (no FHIR nativo)
- API Atelier propietaria para deploy
- Migración de salida = reconstruir todo

### Deploy
- Sin CI/CD nativo
- API Atelier o importación XML manual
- Compilación con dependencias transitivas frágiles
- Sin rollback automático

### Comunidad
- ~15K miembros vs millones en ecosistemas mainstream
- Documentación extensa pero difícil de navegar
- ~2,500 preguntas en StackOverflow vs 1.8M de Python

## 6. Competidores

| Criterio | IRIS | Mirth | Rhapsody | Azure Health | HAPI FHIR |
|----------|------|-------|----------|-------------|-----------|
| Licencia | Propietaria | Open Source | Propietaria | Pay-as-you-go | Open Source |
| Costo/año | $200K-$1M+ | $0-$75K | $50K-$200K | $24K-$240K | $0-$150K* |
| HL7 v2.x | Excelente | Excelente | Excelente | Bueno | No nativo |
| FHIR | Bueno | Bueno | Bueno | Excelente | Excelente |
| EHR | Sí (TrakCare) | No | No | No | No |
| MPI | Sí | No | No | No | No (Smile sí) |
| On-premise | Sí | Sí | Sí | No | Sí |
| Talento | Muy escaso | Abundante | Escaso | Moderado | Abundante |
| Lock-in | Alto | Bajo | Moderado | Moderado | Bajo |

**Combinación recomendable open-source:** HAPI FHIR + Mirth Connect = alternativa a IRIS.
**Nuestra propuesta:** HealthFlow Engine = Mirth + HAPI + IA + Visual Trace + Self-healing.
