"""
Factory de handlers que conectan MLLP Listener → NATS bus.

Cada listener MLLP recibe un handler que publica el mensaje
al subject flow.{flow_id}.inbound para que el pipeline lo procese.
"""

from __future__ import annotations

import uuid
from typing import Optional

import structlog

from ..bus.nats_client import NATSClient, NATSMessage
from ..core.hl7.parser import HL7Message

logger = structlog.get_logger()


def create_nats_handler(nats_client: NATSClient, flow_id: str):
    """Crear handler MLLP que publica mensajes a NATS.

    Args:
        nats_client: Cliente NATS conectado.
        flow_id: ID del flow al que pertenece este listener.

    Returns:
        Async callback compatible con MLLPListener.
    """

    async def handler(message: HL7Message, port_name: str) -> Optional[str]:
        trace_id = uuid.uuid4().hex[:32]

        nats_msg = NATSMessage(
            subject=f"flow.{flow_id}.inbound",
            raw=message.to_er7(),
            flow_id=flow_id,
            trace_id=trace_id,
            metadata={
                "source_adapter": port_name,
                "message_type": message.message_type,
                "trigger_event": message.trigger_event,
                "message_control_id": message.message_control_id,
                "sending_app": message.sending_application,
                "sending_facility": message.sending_facility,
            },
        )

        await nats_client.publish(nats_msg.subject, nats_msg)

        logger.debug(
            "mllp_to_nats_published",
            flow_id=flow_id,
            port=port_name,
            trace_id=trace_id,
            message_type=message.message_type,
        )

        return None  # ACK handled by MLLPListener config

    return handler
