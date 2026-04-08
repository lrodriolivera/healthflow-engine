"""
MLLP (Minimum Lower Layer Protocol) Adapter — asyncio TCP.

Implementa:
- MLLPListener: servidor TCP multi-puerto que recibe mensajes HL7
- MLLPSender: cliente TCP que envía mensajes HL7 con retry

Protocolo MLLP:
  Frame: <VT> + HL7_MESSAGE + <FS><CR>
  VT = 0x0B (Start Block)
  FS = 0x1C (End Block)
  CR = 0x0D (Carriage Return)

Lecciones de UC CHRISTUS incorporadas:
- StayConnected=-1 (persistent connection) como default
- AckMode configurable (Immediate vs Application)
- Timeout configurable por puerto
- Normalización de line endings (LF→CR)
- Logging estructurado con structlog
"""

from __future__ import annotations

import asyncio
import ssl
from dataclasses import dataclass, field
from typing import Callable, Optional, Awaitable

import structlog

from ..core.hl7.parser import HL7Message
from ..core.hl7.ack import generate_ack, generate_simple_ack

logger = structlog.get_logger()

# MLLP framing characters
VT = b"\x0b"   # Start Block
FS = b"\x1c"   # End Block
CR = b"\x0d"   # Carriage Return
MLLP_FOOTER = FS + CR


MessageHandler = Callable[[HL7Message, str], Awaitable[Optional[str]]]
"""Callback signature: async def handler(message, port_name) -> Optional[ack_override]"""


@dataclass
class MLLPListenerConfig:
    """Configuración de un listener MLLP (equivale a un Business Service en IRIS)."""
    port: int
    name: str = ""
    host: str = "0.0.0.0"
    ack_mode: str = "immediate"   # "immediate" | "application" | "never"
    read_timeout: int = 30        # seconds
    stay_connected: bool = True   # persistent connection (-1 en IRIS)
    ssl_context: Optional[ssl.SSLContext] = None
    max_connections: int = 100
    application_name: str = "HEALTHFLOW"
    facility_name: str = "HF"

    def __post_init__(self):
        if not self.name:
            self.name = f"MLLP_{self.port}"


class MLLPListener:
    """Servidor MLLP asyncio que escucha en un puerto TCP.

    Equivalente a un EnsLib.HL7.Service.TCPService en IRIS.
    """

    def __init__(self, config: MLLPListenerConfig, handler: MessageHandler):
        self.config = config
        self.handler = handler
        self._server: Optional[asyncio.Server] = None
        self._connections: set[asyncio.Task] = set()
        self._running = False

    async def start(self) -> None:
        """Iniciar listener."""
        self._running = True
        self._server = await asyncio.start_server(
            self._handle_connection,
            self.config.host,
            self.config.port,
            ssl=self.config.ssl_context,
        )
        logger.info(
            "mllp_listener_started",
            name=self.config.name,
            port=self.config.port,
            ack_mode=self.config.ack_mode,
        )

    async def stop(self) -> None:
        """Detener listener y cerrar conexiones."""
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        for task in self._connections:
            task.cancel()
        logger.info("mllp_listener_stopped", name=self.config.name)

    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Manejar una conexión TCP entrante."""
        peer = writer.get_extra_info("peername")
        log = logger.bind(listener=self.config.name, peer=str(peer))
        log.info("mllp_connection_opened")

        task = asyncio.current_task()
        if task:
            self._connections.add(task)

        try:
            while self._running:
                try:
                    raw_frame = await asyncio.wait_for(
                        self._read_mllp_frame(reader),
                        timeout=self.config.read_timeout if not self.config.stay_connected else None,
                    )
                except asyncio.TimeoutError:
                    if not self.config.stay_connected:
                        log.debug("mllp_read_timeout")
                        break
                    continue
                except asyncio.IncompleteReadError:
                    log.debug("mllp_connection_closed_by_peer")
                    break

                if raw_frame is None:
                    break

                # Parse the HL7 message
                try:
                    message = HL7Message.parse(raw_frame)
                    log.info(
                        "mllp_message_received",
                        message_type=message.message_type,
                        message_id=message.message_control_id,
                    )
                except Exception as e:
                    log.error("mllp_parse_error", error=str(e), raw_preview=raw_frame[:100])
                    # Send AR (Application Reject) for malformed messages
                    ack = generate_simple_ack("UNKNOWN", "AR")
                    await self._send_mllp_frame(writer, ack)
                    continue

                # Immediate ACK: respond before processing
                if self.config.ack_mode == "immediate":
                    ack = generate_ack(
                        message,
                        "AA",
                        application=self.config.application_name,
                        facility=self.config.facility_name,
                    )
                    await self._send_mllp_frame(writer, ack)

                # Process message through handler
                try:
                    ack_override = await self.handler(message, self.config.name)

                    # Application ACK: respond after processing
                    if self.config.ack_mode == "application":
                        if ack_override:
                            await self._send_mllp_frame(writer, ack_override)
                        else:
                            ack = generate_ack(
                                message,
                                "AA",
                                application=self.config.application_name,
                                facility=self.config.facility_name,
                            )
                            await self._send_mllp_frame(writer, ack)

                except Exception as e:
                    log.error(
                        "mllp_handler_error",
                        message_type=message.message_type,
                        message_id=message.message_control_id,
                        error=str(e),
                    )
                    # Application ACK with error
                    if self.config.ack_mode == "application":
                        ack = generate_ack(
                            message,
                            "AE",
                            str(e),
                            application=self.config.application_name,
                            facility=self.config.facility_name,
                        )
                        await self._send_mllp_frame(writer, ack)

                if not self.config.stay_connected:
                    break

        except ConnectionResetError:
            log.debug("mllp_connection_reset")
        except Exception as e:
            log.error("mllp_connection_error", error=str(e))
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            if task:
                self._connections.discard(task)
            log.info("mllp_connection_closed")

    async def _read_mllp_frame(self, reader: asyncio.StreamReader) -> Optional[str]:
        """Leer un frame MLLP completo: <VT>message<FS><CR>."""
        # Read until we find VT (start block)
        while True:
            byte = await reader.read(1)
            if not byte:
                return None
            if byte == VT:
                break

        # Read until FS+CR (end block)
        buffer = bytearray()
        while True:
            byte = await reader.read(1)
            if not byte:
                return None
            buffer.extend(byte)
            if buffer[-2:] == MLLP_FOOTER:
                # Remove the footer
                message_bytes = bytes(buffer[:-2])
                return message_bytes.decode("utf-8", errors="replace")

    async def _send_mllp_frame(self, writer: asyncio.StreamWriter, message: str) -> None:
        """Enviar un frame MLLP: <VT>message<FS><CR>."""
        frame = VT + message.encode("utf-8") + MLLP_FOOTER
        writer.write(frame)
        await writer.drain()


@dataclass
class MLLPSenderConfig:
    """Configuración de un sender MLLP (equivale a un Business Operation en IRIS)."""
    host: str
    port: int
    name: str = ""
    connect_timeout: int = 10
    read_timeout: int = 30
    retry_count: int = 3
    retry_interval: int = 5       # seconds between retries
    stay_connected: bool = True
    ssl_context: Optional[ssl.SSLContext] = None

    def __post_init__(self):
        if not self.name:
            self.name = f"MLLP_OUT_{self.host}:{self.port}"


class MLLPSender:
    """Cliente MLLP asyncio para enviar mensajes HL7.

    Equivalente a un EnsLib.HL7.Operation.TCPOperation en IRIS.
    """

    def __init__(self, config: MLLPSenderConfig):
        self.config = config
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False

    async def connect(self) -> None:
        """Establecer conexión TCP."""
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(
                self.config.host,
                self.config.port,
                ssl=self.config.ssl_context,
            ),
            timeout=self.config.connect_timeout,
        )
        self._connected = True
        logger.info(
            "mllp_sender_connected",
            name=self.config.name,
            host=self.config.host,
            port=self.config.port,
        )

    async def disconnect(self) -> None:
        """Cerrar conexión."""
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
        self._connected = False

    async def send(self, message: str) -> str:
        """Enviar mensaje HL7 y esperar ACK. Retorna el ACK como string.

        Incluye retry automático.
        """
        last_error = None

        for attempt in range(1, self.config.retry_count + 1):
            try:
                if not self._connected:
                    await self.connect()

                # Send MLLP frame
                frame = VT + message.encode("utf-8") + MLLP_FOOTER
                self._writer.write(frame)
                await self._writer.drain()

                # Read ACK
                ack = await asyncio.wait_for(
                    self._read_mllp_frame(),
                    timeout=self.config.read_timeout,
                )

                if ack is None:
                    raise ConnectionError("Connection closed before ACK received")

                logger.info(
                    "mllp_message_sent",
                    name=self.config.name,
                    attempt=attempt,
                )

                if not self.config.stay_connected:
                    await self.disconnect()

                return ack

            except Exception as e:
                last_error = e
                logger.warning(
                    "mllp_send_failed",
                    name=self.config.name,
                    attempt=attempt,
                    max_attempts=self.config.retry_count,
                    error=str(e),
                )
                self._connected = False
                if attempt < self.config.retry_count:
                    await asyncio.sleep(self.config.retry_interval)

        raise ConnectionError(
            f"Failed to send after {self.config.retry_count} attempts: {last_error}"
        )

    async def _read_mllp_frame(self) -> Optional[str]:
        """Leer un frame MLLP de respuesta (ACK)."""
        if not self._reader:
            return None

        while True:
            byte = await self._reader.read(1)
            if not byte:
                return None
            if byte == VT:
                break

        buffer = bytearray()
        while True:
            byte = await self._reader.read(1)
            if not byte:
                return None
            buffer.extend(byte)
            if buffer[-2:] == MLLP_FOOTER:
                return bytes(buffer[:-2]).decode("utf-8", errors="replace")
