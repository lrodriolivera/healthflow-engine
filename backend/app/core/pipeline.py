"""
Pipeline orchestrator — el corazón del message flow.

Flujo completo:
  1. MLLP Listener recibe → publica flow.{id}.inbound
  2. Pipeline consume inbound → routing → publica flow.{id}.routed.{dest}
  3. Pipeline consume routed → transform → publica flow.{id}.transformed.{dest}
  4. Pipeline consume transformed → outbound adapter → publica flow.{id}.ack.{dest}
  5. Si error → flow.{id}.error → retry/DLQ → SelfHealer

Diseño:
  - Cada etapa es un consumer NATS independiente
  - Desacoplamiento total entre etapas
  - Retry automático via NATS nak()
  - Audit en cada etapa
"""

from __future__ import annotations

import time
import uuid
from typing import Optional, TYPE_CHECKING

import structlog

from ..bus.nats_client import NATSClient, NATSMessage
from ..core.hl7.parser import HL7Message
from ..core.routing.engine import RoutingEngine, RoutingDestination
from ..telemetry import (
    get_tracer, record_message_received, record_message_routed,
    record_message_error, record_processing_duration,
)

if TYPE_CHECKING:
    from ..adapters.registry import AdapterRegistry

logger = structlog.get_logger()


class MessagePipeline:
    """Orquestador central del flujo de mensajes."""

    def __init__(
        self,
        nats_client: NATSClient,
        routing_engine: RoutingEngine,
        adapter_registry: "AdapterRegistry",
        ai_router=None,  # Se inyecta en M5 cuando exista
    ):
        self._nats = nats_client
        self._routing = routing_engine
        self._adapters = adapter_registry
        self._ai_router = ai_router
        self._transform_registry = None  # Se inyecta en M4

    def set_transform_registry(self, registry) -> None:
        """Inyectar transform registry (M4)."""
        self._transform_registry = registry

    def set_ai_router(self, router) -> None:
        """Inyectar AI router agent (M5)."""
        self._ai_router = router

    async def start(self) -> None:
        """Suscribirse a todos los subjects del pipeline."""
        await self._nats.subscribe(
            "flow.*.inbound",
            self._on_inbound,
            durable_name="pipeline-inbound",
            queue_group="pipeline",
        )
        await self._nats.subscribe(
            "flow.*.routed.*",
            self._on_routed,
            durable_name="pipeline-routed",
            queue_group="pipeline",
        )
        await self._nats.subscribe(
            "flow.*.transformed.*",
            self._on_transformed,
            durable_name="pipeline-transformed",
            queue_group="pipeline",
        )
        logger.info("pipeline_started")

    async def _on_inbound(self, msg: NATSMessage) -> None:
        """Procesar mensaje entrante: parsear → routing → publicar a destinos."""
        start_time = time.monotonic()
        log = logger.bind(flow_id=msg.flow_id, trace_id=msg.trace_id)

        try:
            # Parse HL7
            hl7_msg = HL7Message.parse(msg.raw)
            record_message_received(hl7_msg.message_type_code, msg.flow_id)
            log = log.bind(
                message_type=hl7_msg.message_type,
                message_id=hl7_msg.message_control_id,
            )
            log.info("pipeline_inbound_received")

            # Routing
            destinations = self._routing.evaluate(hl7_msg)

            # Si no matchea ninguna regla → slow-path AI Router
            if not destinations and self._ai_router:
                log.info("pipeline_ai_router_invoked")
                try:
                    result = await self._ai_router.route(
                        hl7_msg,
                        self._adapters.list_destinations(),
                        self._routing.get_rules(),
                    )
                    if result.get("destinations"):
                        destinations = [
                            RoutingDestination(
                                name=d["name"],
                                adapter_name=d["adapter_name"],
                                transform=d.get("transform"),
                            )
                            for d in result["destinations"]
                        ]
                        # Auto-learn: si confidence alta, agregar regla
                        if result.get("confidence", 0) > 0.8 and result.get("suggested_rule"):
                            log.info("pipeline_ai_rule_learned", rule=result["suggested_rule"])
                            # TODO: persistir regla en DB y cargar en engine
                except Exception as e:
                    log.error("pipeline_ai_router_error", error=str(e))

            if not destinations:
                log.warning("pipeline_no_destinations")
                await self._publish_error(
                    msg, "no_route", "No routing rule matched and AI router could not determine destination"
                )
                return

            # Publicar a cada destino
            for dest in destinations:
                routed_msg = NATSMessage(
                    subject=f"flow.{msg.flow_id}.routed.{dest.name}",
                    raw=msg.raw,
                    flow_id=msg.flow_id,
                    trace_id=msg.trace_id,
                    metadata={
                        **msg.metadata,
                        "destination": dest.name,
                        "adapter_name": dest.adapter_name,
                        "transform": dest.transform or "",
                    },
                )
                await self._nats.publish(routed_msg.subject, routed_msg)

            elapsed_ms = (time.monotonic() - start_time) * 1000
            record_processing_duration(elapsed_ms, "inbound")
            for dest in destinations:
                record_message_routed(hl7_msg.message_type_code, dest.name)
            log.info(
                "pipeline_inbound_processed",
                destinations=[d.name for d in destinations],
                elapsed_ms=round(elapsed_ms, 2),
            )

        except Exception as e:
            record_message_error("inbound", msg.flow_id)
            log.error("pipeline_inbound_error", error=str(e))
            await self._publish_error(msg, "parse_or_route_error", str(e))

    async def _on_routed(self, msg: NATSMessage) -> None:
        """Aplicar transformación al mensaje ruteado."""
        log = logger.bind(
            flow_id=msg.flow_id,
            trace_id=msg.trace_id,
            destination=msg.metadata.get("destination", ""),
        )

        try:
            transform_name = msg.metadata.get("transform", "")
            dest_name = msg.metadata.get("destination", "unknown")

            if transform_name and self._transform_registry:
                # Aplicar transformación
                log.info("pipeline_transform_applying", transform=transform_name)
                hl7_msg = HL7Message.parse(msg.raw)
                transformed = self._transform_registry.execute(transform_name, hl7_msg)
                output_raw = transformed.to_er7()
            else:
                # Passthrough
                output_raw = msg.raw

            # Publicar mensaje transformado
            transformed_msg = NATSMessage(
                subject=f"flow.{msg.flow_id}.transformed.{dest_name}",
                raw=output_raw,
                flow_id=msg.flow_id,
                trace_id=msg.trace_id,
                metadata=msg.metadata,
            )
            await self._nats.publish(transformed_msg.subject, transformed_msg)
            log.info("pipeline_transform_done")

        except Exception as e:
            log.error("pipeline_transform_error", error=str(e))
            await self._publish_error(msg, "transform_error", str(e))

    async def _on_transformed(self, msg: NATSMessage) -> None:
        """Enviar mensaje via outbound adapter."""
        dest_name = msg.metadata.get("destination", "unknown")
        adapter_name = msg.metadata.get("adapter_name", "")
        log = logger.bind(
            flow_id=msg.flow_id,
            trace_id=msg.trace_id,
            destination=dest_name,
            adapter=adapter_name,
        )

        try:
            adapter = self._adapters.get(adapter_name)
            if not adapter:
                raise ValueError(f"Adapter not found: {adapter_name}")

            # Enviar
            log.info("pipeline_outbound_sending")
            ack_response = await adapter.send(msg.raw)

            # Publicar ACK
            ack_msg = NATSMessage(
                subject=f"flow.{msg.flow_id}.ack.{dest_name}",
                raw=ack_response or "",
                flow_id=msg.flow_id,
                trace_id=msg.trace_id,
                metadata={
                    **msg.metadata,
                    "ack_code": _extract_ack_code(ack_response) if ack_response else "sent",
                },
            )
            await self._nats.publish(ack_msg.subject, ack_msg)
            log.info("pipeline_outbound_acked")

        except Exception as e:
            log.error("pipeline_outbound_error", error=str(e))
            await self._publish_error(msg, "outbound_error", str(e))

    async def _publish_error(
        self, original_msg: NATSMessage, error_type: str, error_detail: str
    ) -> None:
        """Publicar error al subject de errores."""
        error_msg = NATSMessage(
            subject=f"flow.{original_msg.flow_id}.error",
            raw=original_msg.raw,
            flow_id=original_msg.flow_id,
            trace_id=original_msg.trace_id,
            metadata={
                **original_msg.metadata,
                "error_type": error_type,
                "error_detail": error_detail,
            },
        )
        try:
            await self._nats.publish(error_msg.subject, error_msg)
        except Exception as e:
            logger.error("pipeline_error_publish_failed", error=str(e))


def _extract_ack_code(ack_raw: str) -> str:
    """Extraer código ACK (AA/AE/AR) de una respuesta HL7."""
    try:
        ack_msg = HL7Message.parse(ack_raw)
        return ack_msg.get("MSA-1")
    except Exception:
        return "unknown"
