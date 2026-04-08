"""
NATS JetStream client wrapper.

Subjects:
  flow.{flow_id}.inbound          — mensaje recibido por adapter
  flow.{flow_id}.routed.{dest}    — mensaje ruteado a destino
  flow.{flow_id}.transformed.{dest} — mensaje transformado
  flow.{flow_id}.outbound.{dest}  — mensaje enviado
  flow.{flow_id}.ack.{dest}       — ACK recibido del destino
  flow.{flow_id}.error            — mensaje con error
  flow.{flow_id}.dlq              — dead letter queue
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable, Optional

import nats
from nats.aio.client import Client as NATS
from nats.js.api import StreamConfig, RetentionPolicy, StorageType
from nats.js.client import JetStreamContext

import structlog

from ..config import Settings

logger = structlog.get_logger()

MessageCallback = Callable[["NATSMessage"], Awaitable[None]]


@dataclass
class NATSMessage:
    """Mensaje que fluye por el bus."""

    subject: str
    raw: str  # HL7 ER7 message
    flow_id: str = ""
    trace_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_bytes(self) -> bytes:
        """Serializar a JSON bytes para publicar en NATS."""
        payload = {
            "raw": self.raw,
            "flow_id": self.flow_id,
            "trace_id": self.trace_id,
            "metadata": self.metadata,
        }
        return json.dumps(payload).encode("utf-8")

    @classmethod
    def from_bytes(cls, subject: str, data: bytes) -> NATSMessage:
        """Deserializar desde NATS."""
        payload = json.loads(data.decode("utf-8"))
        return cls(
            subject=subject,
            raw=payload.get("raw", ""),
            flow_id=payload.get("flow_id", ""),
            trace_id=payload.get("trace_id", ""),
            metadata=payload.get("metadata", {}),
        )


class NATSClient:
    """Wrapper sobre nats-py con JetStream."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._nc: Optional[NATS] = None
        self._js: Optional[JetStreamContext] = None
        self._subscriptions: list = []

    @property
    def is_connected(self) -> bool:
        return self._nc is not None and self._nc.is_connected

    async def connect(self) -> None:
        """Conectar a NATS y crear stream JetStream."""
        self._nc = await nats.connect(
            self._settings.nats_url,
            connect_timeout=5,
            max_reconnect_attempts=2,
            reconnected_cb=self._on_reconnect,
            disconnected_cb=self._on_disconnect,
            error_cb=self._on_error,
        )
        self._js = self._nc.jetstream()

        # Crear o actualizar stream
        await self._ensure_stream()

        logger.info(
            "nats_connected",
            url=self._settings.nats_url,
            stream=self._settings.nats_stream_name,
        )

    async def _ensure_stream(self) -> None:
        """Crear stream idempotentemente."""
        config = StreamConfig(
            name=self._settings.nats_stream_name,
            subjects=["flow.>"],
            retention=RetentionPolicy.LIMITS,
            storage=StorageType.FILE,
            max_age=7 * 24 * 60 * 60 * 1_000_000_000,  # 7 days in nanoseconds
            num_replicas=1,
        )
        try:
            await self._js.find_stream_info_by_subject("flow.>")
            await self._js.update_stream(config)
            logger.debug("nats_stream_updated", name=self._settings.nats_stream_name)
        except nats.js.errors.NotFoundError:
            await self._js.add_stream(config)
            logger.info("nats_stream_created", name=self._settings.nats_stream_name)

    async def publish(self, subject: str, message: NATSMessage) -> None:
        """Publicar mensaje en un subject."""
        if not self._js:
            raise RuntimeError("NATS not connected")

        headers = {
            "flow_id": message.flow_id,
            "trace_id": message.trace_id,
        }
        # Add metadata keys as headers
        for key, value in message.metadata.items():
            if isinstance(value, str):
                headers[key] = value

        ack = await self._js.publish(
            subject,
            message.to_bytes(),
            headers=headers,
        )
        logger.debug(
            "nats_published",
            subject=subject,
            flow_id=message.flow_id,
            seq=ack.seq,
        )

    async def subscribe(
        self,
        subject: str,
        callback: MessageCallback,
        durable_name: Optional[str] = None,
        queue_group: Optional[str] = None,
    ) -> None:
        """Suscribirse a un subject con consumer durable."""
        if not self._js:
            raise RuntimeError("NATS not connected")

        async def _handler(msg):
            try:
                nats_msg = NATSMessage.from_bytes(msg.subject, msg.data)
                await callback(nats_msg)
                await msg.ack()
            except Exception as e:
                logger.error(
                    "nats_handler_error",
                    subject=msg.subject,
                    error=str(e),
                )
                await msg.nak()

        kwargs = {}
        if durable_name:
            kwargs["durable"] = durable_name
        if queue_group:
            kwargs["queue"] = queue_group

        sub = await self._js.subscribe(subject, cb=_handler, **kwargs)
        self._subscriptions.append(sub)

        logger.info(
            "nats_subscribed",
            subject=subject,
            durable=durable_name,
        )

    async def close(self) -> None:
        """Cerrar conexión y drain subscriptions."""
        for sub in self._subscriptions:
            try:
                await sub.unsubscribe()
            except Exception:
                pass
        self._subscriptions.clear()

        if self._nc and self._nc.is_connected:
            await self._nc.drain()
            logger.info("nats_closed")

    async def _on_reconnect(self) -> None:
        logger.info("nats_reconnected")

    async def _on_disconnect(self) -> None:
        logger.warning("nats_disconnected")

    async def _on_error(self, e: Exception) -> None:
        logger.error("nats_error", error=str(e))
