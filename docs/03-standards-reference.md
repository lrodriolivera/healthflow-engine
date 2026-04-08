# Referencia de Estándares Healthcare

## 1. HL7 v2.x — El Estándar Dominante (80%+ del tráfico hospitalario)

### Por qué sigue dominando
Toda la infraestructura instalada (HIS, LIS, RIS, PACS, EHR, farmacia) lleva 20-30 años
intercambiando mensajes v2.x. Reemplazar requiere migración simultánea de todos los endpoints.

### Tipos de mensaje críticos

| Tipo | Trigger Events | Uso |
|------|---------------|-----|
| **ADT** | A01(ingreso), A02(transfer), A03(alta), A04(registro), A08(update), A28/A31(MPI), A40(merge) | Demografía, movimientos. **Backbone** de toda integración. |
| **ORM** | O01(nueva orden), O02(respuesta) | Solicitudes lab/imagen/procedimientos |
| **ORU** | R01(resultado) | Resultados lab/patología. Mensaje más voluminoso. |
| **OML** | O21(orden lab con specimen), O33(múltiples specimens) | Reemplazo moderno de ORM para lab |
| **OUL** | R22(resultado no solicitado), R24(respuesta) | Reemplazo moderno de ORU para lab |
| **SIU** | S12(nueva cita), S13(re-agenda), S14(mod), S15(cancel), S26(no-show) | Agendamiento |
| **DFT** | P03(cargo), P11(cargo post) | Captura de cargos financieros |
| **MDM** | T02(documento), T06(addendum), T11(cancel) | Documentos clínicos |
| **RDE** | O11(prescripción) | Farmacia |
| **RDS** | O13(dispensación) | Farmacia |

### Codificación ER7 (pipe-delimited)
```
MSH|^~\&|ORIGEN|FAC_OR|DESTINO|FAC_DE|20260408120000||ADT^A08^ADT_A01|MSG001|P|2.5|||AL|NE
EVN|A08|20260408120000
PID|1||PAC123^^^MPI^MR||APELLIDO^NOMBRE||19800115|M|||CALLE 123^^SANTIAGO^^8320000^CL
PV1|1|I|SALA301^CAMA1^1^^^HOSP1||||MED001^DR.LOPEZ^JUAN
```

Delimitadores (MSH.2 = `^~\&`):
- `|` campo, `^` componente, `~` repetición, `\` escape, `&` subcomponente

### Transporte MLLP
```
Frame: <VT> + HL7_MESSAGE + <FS><CR>
VT = 0x0B (Start Block)
FS = 0x1C (End Block)
CR = 0x0D (Carriage Return)
```

Características:
- Sin TLS nativo (requiere stunnel/HAProxy o soporte nativo)
- Síncrono: envía → espera ACK → siguiente mensaje
- Persistent connection
- Sin routing headers — routing por **puerto TCP** (1 puerto = 1 flujo)

### ACK/NAK
```
MSH|^~\&|DEST|FAC|ORIG|FAC|20260408||ACK^A08|ACK001|P|2.5
MSA|AA|MSG001
```
- `AA` Application Accept | `AE` Application Error | `AR` Application Reject
- MSA.2 = MSH.10 del mensaje original

### Z-Segments
Extensiones custom (ZPD, ZFT, ZDS). Parser NO debe rechazar segmentos desconocidos.

## 2. HL7 FHIR R4/R5

### Resources principales
| Resource | Equiv. HL7v2 | Uso |
|----------|-------------|-----|
| Patient | PID | Demografía, identificadores |
| Encounter | PV1/PV2 | Visita/episodio |
| Observation | OBX | Resultado individual |
| DiagnosticReport | ORU wrapper | Agrupa Observations |
| ServiceRequest | ORC/OBR | Solicitud de servicio |
| MedicationRequest | RXO/RXE | Prescripción |
| Condition | DG1 | Diagnósticos |
| Procedure | PR1 | Procedimientos |
| AllergyIntolerance | AL1 | Alergias |
| Appointment/Schedule | SIU | Agendamiento |
| Claim | DFT | Facturación |

### API RESTful
```
GET    /Patient/123                    # Read
POST   /Patient                        # Create
PUT    /Patient/123                    # Update
DELETE /Patient/123                    # Delete
GET    /Patient?family=Lopez           # Search
POST   /Patient/$match                 # MPI matching
GET    /$export                        # Bulk Data
```

### SMART on FHIR (auth)
OAuth 2.0 + scopes: `patient/Observation.read`, `user/Patient.write`
EHR Launch / Standalone Launch / Backend Services (client credentials)

### CDS Hooks
Inyectar alertas en workflow clínico:
- Hooks: patient-view, order-select, order-sign, encounter-start
- Response: cards[] con sugerencias, alertas, links

### Subscriptions (R5)
Pub/sub topic-based con canales: rest-hook, websocket, email, FHIR messaging

### Perfiles
- **US Core:** Obligatorio en EEUU, must-support elements
- **IPS:** International Patient Summary, portable entre países
- **HL7 Chile:** Perfiles nacionales con RUN, Organization, Immunization
- **FHIR Shorthand (FSH):** Lenguaje declarativo para definir perfiles

## 3. IHE Profiles

### PIX/PDQ (Patient Identity)
- **PIX:** Cross-reference de IDs entre dominios. ADT→MPI→Query Q23.
- **PDQ:** Búsqueda demográfica. QBP^Q22 / GET /Patient?family=X
- Versiones mobile: PIXm, PDQm (FHIR-based)

### XDS/MHD (Document Sharing)
- **XDS.b:** Registry + Repository + Source + Consumer. SOAP/MTOM.
- **MHD:** Versión FHIR de XDS. DocumentReference + Bundle.

### ATNA (Audit Trail)
- TLS mutuo entre nodos
- Logging RFC 3881 / DICOM Audit Message → syslog over TLS
- **Requisito legal en muchas jurisdicciones**

### Perfiles de Laboratorio (LAB-1 a LAB-7)
- LAB-1 (LTW): Order Placer → Order Filler → Result (OML/ORL/OUL)
- LAB-2 (LDA): Analizador → Middleware → LIS (ASTM/HL7)

### Perfiles de Radiología
- **SWF:** Order → Scheduled → MWL → Acquisition → Storage → MPPS
- **RWF:** Study Available → Report → Verification → Distribution

## 4. DICOM

### Servicios DIMSE
- C-STORE: Enviar imagen a PACS
- C-FIND: Buscar estudios (Modality Worklist)
- C-MOVE: Solicitar envío de imágenes
- N-CREATE/N-SET: MPPS

### DICOMweb (RESTful)
- WADO-RS: `GET /studies/{uid}` (retrieve)
- STOW-RS: `POST /studies` (store)
- QIDO-RS: `GET /studies?PatientName=X` (query)

## 5. CDA / C-CDA

### CDA R2
Documento XML: Header (identificación) + Body (secciones con entries codificadas)

### C-CDA Templates
- CCD (Continuity of Care), Discharge Summary, Progress Note, Referral Note
- Requerido por regulaciones, FHIR lo reemplaza gradualmente
- Conversión bidireccional C-CDA ↔ FHIR Document Bundle

## 6. Regulación

### HIPAA (EEUU)
- BAA obligatorio para procesar PHI con IA (Anthropic ofrece BAA Enterprise)
- Mínimo necesario: solo campos necesarios al LLM
- Audit trail de cada invocación
- Encriptación en tránsito (TLS 1.2+)

### ONC / 21st Century Cures Act
- Information Blocking Rule: multas $1M por bloquear acceso a datos
- USCDI: dataset mínimo obligatorio
- EHR deben soportar FHIR R4 + Bulk Data + SMART on FHIR

### TEFCA
- Redes QHIN certificadas: eHealth Exchange, CommonWell, Carequality, Epic Nexus
- Exchange purposes: Treatment, Payment, Operations, Public Health

### Unión Europea (EHDS)
- Intercambio obligatorio entre países miembros
- Formatos: Patient Summary, ePrescription, Lab Results, Images, Discharge

### Latinoamérica
- **Chile (MINSAL):** HL7 FHIR IG Nacional (hl7chile.cl). Perfiles con RUN.
- **Brasil (RNDS):** FHIR R4 obligatoria para vacunación, COVID, resumen.
- **Argentina:** IG FHIR + SISA (bus de interoperabilidad).
- **Colombia:** RIPS migrando hacia FHIR.

## 7. Patrones de Integración Hospitalaria

### ADT (Mayor volumen: 5K-20K/día en hospital grande)
```
HIS → ADT^A01 → [Motor] → fan-out → LIS, RIS, Farmacia, Nutrición...
```
- Fan-out a N sistemas, orden importa (A01 antes que A02 antes que A03)
- Merge (A40) = caso más complejo

### Order-Result (Lab)
```
HIS → OML^O21 → [Motor] → LIS
LIS → OUL^R22 → [Motor] → HIS (parcial/final/corregido)
```
- Multi-OBR, estados (F/P/C/X), reflexiones, specimens compartidos

### Order-Result (Radiology)
```
HIS → ORM^O01 → [Motor] → RIS → DICOM MWL → Modalidad
Modalidad → DICOM C-STORE → PACS
RIS → ORU^R01 → [Motor] → HIS
```

### DFT (Cargos)
```
HIS/RIS/LIS → DFT^P03 → [Motor] → ERP/SAP
```
- FT1 (transacción), PR1 (procedimiento), DG1 (diagnóstico), IN1/IN2 (seguro)
- Mapeo FONASA / códigos internos / ISAPRE

### Scheduling
```
Agenda → SIU^S12 → [Motor] → HIS, Portal Paciente, Recordatorios
```
- SCH, AIS, AIG, AIL, AIP segments
