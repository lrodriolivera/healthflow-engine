"""
Adapter registry — registro centralizado de adapters outbound.

El pipeline usa este registry para buscar el adapter correcto
al enviar mensajes a destinos.
"""

from __future__ import annotations

from typing import Any, Optional, Protocol

import structlog

logger = structlog.get_logger()


class OutboundAdapter(Protocol):
    """Protocolo que debe cumplir cualquier adapter outbound."""

    async def send(self, message: str) -> Optional[str]:
        """Enviar mensaje y retornar respuesta (ACK) o None."""
        ...


class AdapterRegistry:
    """Registry de adapters outbound por nombre."""

    def __init__(self):
        self._adapters: dict[str, Any] = {}

    def register(self, name: str, adapter: OutboundAdapter) -> None:
        """Registrar un adapter outbound."""
        self._adapters[name] = adapter
        logger.info("adapter_registered", name=name, type=type(adapter).__name__)

    def unregister(self, name: str) -> bool:
        """Desregistrar adapter."""
        if name in self._adapters:
            del self._adapters[name]
            return True
        return False

    def get(self, name: str) -> Optional[OutboundAdapter]:
        """Obtener adapter por nombre."""
        return self._adapters.get(name)

    def list_names(self) -> list[str]:
        """Listar nombres de adapters registrados."""
        return list(self._adapters.keys())

    def list_destinations(self) -> list[dict]:
        """Listar destinos disponibles (para AI Router)."""
        return [
            {"name": name, "adapter_name": name, "type": type(adapter).__name__}
            for name, adapter in self._adapters.items()
        ]

    async def start_all(self) -> None:
        """Conectar todos los adapters que lo requieran."""
        for name, adapter in self._adapters.items():
            if hasattr(adapter, "connect"):
                try:
                    await adapter.connect()
                    logger.info("adapter_started", name=name)
                except Exception as e:
                    logger.error("adapter_start_failed", name=name, error=str(e))

    async def stop_all(self) -> None:
        """Desconectar todos los adapters."""
        for name, adapter in self._adapters.items():
            if hasattr(adapter, "disconnect"):
                try:
                    await adapter.disconnect()
                    logger.info("adapter_stopped", name=name)
                except Exception as e:
                    logger.error("adapter_stop_failed", name=name, error=str(e))

    @property
    def count(self) -> int:
        return len(self._adapters)
