"""
OpenTelemetry setup — traces, métricas y logging.

Reemplaza el Visual Trace de IRIS con un estándar abierto.
Cada mensaje tiene un trace con spans por etapa:
  healthflow.inbound → healthflow.route → healthflow.transform → healthflow.outbound
"""

from __future__ import annotations

from typing import Optional

from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

import structlog

from .config import Settings

logger = structlog.get_logger()

# Module-level tracer and meter
_tracer: Optional[trace.Tracer] = None
_meter: Optional[metrics.Meter] = None

# Metrics instruments
_messages_received = None
_messages_routed = None
_messages_errors = None
_processing_duration = None
_mllp_connections = None


def init_telemetry(settings: Settings, app=None) -> None:
    """Inicializar OpenTelemetry con OTLP exporter."""
    global _tracer, _meter
    global _messages_received, _messages_routed, _messages_errors
    global _processing_duration, _mllp_connections

    if not settings.otel_enabled:
        logger.info("otel_disabled")
        return

    resource = Resource.create({
        "service.name": settings.otel_service_name,
        "service.version": settings.app_version,
    })

    # Traces
    tracer_provider = TracerProvider(resource=resource)
    try:
        span_exporter = OTLPSpanExporter(endpoint=settings.otel_endpoint, insecure=True)
        tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
    except Exception as e:
        logger.warning("otel_trace_exporter_failed", error=str(e))
    trace.set_tracer_provider(tracer_provider)
    _tracer = trace.get_tracer("healthflow")

    # Metrics
    try:
        metric_exporter = OTLPMetricExporter(endpoint=settings.otel_endpoint, insecure=True)
        metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=10000)
        meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    except Exception:
        meter_provider = MeterProvider(resource=resource)
    metrics.set_meter_provider(meter_provider)
    _meter = metrics.get_meter("healthflow")

    # Create instruments
    _messages_received = _meter.create_counter(
        "healthflow.messages.received",
        description="Total HL7 messages received",
        unit="messages",
    )
    _messages_routed = _meter.create_counter(
        "healthflow.messages.routed",
        description="Total messages successfully routed",
        unit="messages",
    )
    _messages_errors = _meter.create_counter(
        "healthflow.messages.errors",
        description="Total message processing errors",
        unit="errors",
    )
    _processing_duration = _meter.create_histogram(
        "healthflow.processing.duration",
        description="Message processing duration",
        unit="ms",
    )
    _mllp_connections = _meter.create_up_down_counter(
        "healthflow.mllp.connections",
        description="Active MLLP connections",
        unit="connections",
    )

    # Note: FastAPI instrumentation must be done before app startup.
    # Call init_telemetry() without app parameter, or instrument manually.

    logger.info("otel_initialized", endpoint=settings.otel_endpoint)


def get_tracer() -> trace.Tracer:
    """Obtener tracer. Returns NoOp si no está inicializado."""
    return _tracer or trace.get_tracer("healthflow")


def get_meter() -> metrics.Meter:
    """Obtener meter."""
    return _meter or metrics.get_meter("healthflow")


# --- Convenience functions for metrics ---

def record_message_received(message_type: str, flow_id: str) -> None:
    if _messages_received:
        _messages_received.add(1, {"message_type": message_type, "flow_id": flow_id})


def record_message_routed(message_type: str, destination: str) -> None:
    if _messages_routed:
        _messages_routed.add(1, {"message_type": message_type, "destination": destination})


def record_message_error(error_type: str, flow_id: str) -> None:
    if _messages_errors:
        _messages_errors.add(1, {"error_type": error_type, "flow_id": flow_id})


def record_processing_duration(duration_ms: float, stage: str) -> None:
    if _processing_duration:
        _processing_duration.record(duration_ms, {"stage": stage})


def record_mllp_connection(delta: int, port: str) -> None:
    if _mllp_connections:
        _mllp_connections.add(delta, {"port": port})
