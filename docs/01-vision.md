# Vision: Por qué reemplazar IRIS

## El Mercado

InterSystems IRIS/HealthShare es el motor de integración dominante en hospitales de alta complejidad.
Pero tiene problemas fundamentales que abren oportunidad:

### Pain Points de IRIS (validados con experiencia real UCCHRISTUS)

1. **ObjectScript:** Lenguaje propietario de 1966 (MUMPS). Trampas como `_` = concatenación,
   `Quit "value"` en Try = crash, `New $NAMESPACE` no se restaura. Pool de talento ínfimo.

2. **Pricing opaco:** $200K-$1M+/año licencia, $500K-$5M+ implementación.
   No hay tier community funcional para producción.

3. **Deploy manual:** API Atelier propietaria o importación XML por portal web.
   No hay git push, no hay CI/CD nativo, no hay containers oficiales.

4. **Vendor lock-in total:** Globals (storage), BPL/DTL (workflows), SDA (data model).
   Migrar de IRIS requiere reconstruir todo desde cero.

5. **Debugging por Visual Trace:** Poderoso pero propietario. No exportable, no integrable
   con herramientas estándar (Grafana, Datadog, OpenTelemetry).

## Nuestra Ventaja Competitiva

Nacemos de la experiencia real:
- 6+ meses operando IRIS en producción (30+ flujos HL7 LIS/RIS)
- Conocimiento profundo de HL7v2, MLLP, SOAP, MPI en contexto hospitalario real
- 5 reglas "NEVER" de ObjectScript descubiertas en producción
- Templates y patrones probados con datos reales de pacientes
- Entendimiento del workflow de hospitales chilenos/LATAM

## Target Market

### Tier 1: Hospitales medianos sin IRIS (reemplazo de Mirth Connect)
- No pueden pagar IRIS ($200K+/año)
- Usan Mirth Connect (gratis) pero necesitan más: IA, visual trace, self-healing
- **Propuesta:** HealthFlow = Mirth + IA + Visual Trace por $2-5K/mes

### Tier 2: Hospitales con IRIS que quieren migrar
- Frustrados con costos, lock-in, escasez de talento ObjectScript
- **Propuesta:** Migración gradual flujo por flujo, coexistencia con IRIS durante transición

### Tier 3: Redes de salud / Gobiernos
- Necesitan interoperabilidad multi-hospital (TEFCA, EHDS, RNDS Chile)
- **Propuesta:** HealthFlow como bus de interoperabilidad regional FHIR-first

## Diferenciador: IA como Ventaja Operativa

La clave no es "IA reemplaza IRIS" sino **"IA hace innecesario el nivel de complejidad
que justifica la existencia de IRIS"**:

- Si un agente puede **diseñar** transformaciones automáticamente → no necesitas DTL visual
- Si un agente puede **diagnosticar** errores leyendo logs → no necesitas Visual Trace propietario
- Si un agente puede **auto-reparar** flujos rotos → no necesitas equipo 24/7 de ObjectScript
- Si un agente puede **onboardear** nuevas interfaces por lenguaje natural → no necesitas meses de desarrollo

El motor de runtime puede ser mucho más simple — y por lo tanto, mucho más barato.
