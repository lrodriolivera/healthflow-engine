"""
HealthFlow Engine — AI-native healthcare integration engine.

Punto de entrada principal. Levanta:
1. API REST (FastAPI) para management/config
2. MLLP listeners según configuración
3. Message bus (NATS) consumers
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .core.hl7 import HL7Message


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: iniciar adapters, bus, routing engine
    # TODO: cargar config de DB, iniciar MLLP listeners, conectar NATS
    yield
    # Shutdown: detener adapters, cerrar conexiones
    # TODO: graceful shutdown


app = FastAPI(
    title="HealthFlow Engine",
    description="AI-native healthcare integration engine",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health():
    return {"status": "ok", "engine": "healthflow", "version": "0.1.0"}


@app.get("/api/v1/flows")
async def list_flows():
    """Listar flujos configurados (equivalente a Production items en IRIS)."""
    # TODO: cargar de DB
    return {"flows": []}


@app.post("/api/v1/messages/parse")
async def parse_message(body: dict):
    """Parsear un mensaje HL7 para inspección."""
    raw = body.get("message", "")
    try:
        msg = HL7Message.parse(raw)
        return {
            "message_type": msg.message_type,
            "trigger_event": msg.trigger_event,
            "message_id": msg.message_control_id,
            "sending_app": msg.sending_application,
            "sending_facility": msg.sending_facility,
            "version": msg.version,
            "segment_count": len(msg.segments),
            "segments": [
                {"name": seg.name, "fields": seg.field_count}
                for seg in msg.segments
            ],
        }
    except Exception as e:
        return {"error": str(e)}
