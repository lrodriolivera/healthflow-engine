"""
Transform engine — registro y ejecución de transformaciones compiladas.

Las transformaciones son funciones Python que siguen el contrato:
    def transform(msg: HL7Message, lookup: Callable[[str, str], str]) -> HL7Message

Se compilan una vez y se ejecutan a <1ms por mensaje.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import structlog

from ..hl7.parser import HL7Message
from .sandbox import (
    compile_transform,
    execute_transform,
    CompilationError,
    ExecutionError,
    SandboxError,
)

logger = structlog.get_logger()


@dataclass
class CompiledTransform:
    """Una transformación compilada lista para ejecutar."""

    name: str
    version: int
    source_code: str
    _fn: Callable

    def execute(self, message: HL7Message, lookup: Optional[Callable] = None) -> HL7Message:
        """Ejecutar transformación."""
        return execute_transform(self._fn, message, lookup)


class TransformRegistry:
    """Registry de transformaciones compiladas.

    Se cargan desde DB al iniciar y se mantienen en memoria.
    """

    def __init__(self):
        self._transforms: dict[str, CompiledTransform] = {}

    def register(self, name: str, source_code: str, version: int = 1) -> CompiledTransform:
        """Compilar y registrar una transformación.

        Args:
            name: Nombre único de la transformación.
            source_code: Código Python con def transform(msg, lookup).
            version: Versión de la transformación.

        Returns:
            CompiledTransform registrada.

        Raises:
            CompilationError: Si el código no compila.
        """
        fn = compile_transform(source_code)
        ct = CompiledTransform(
            name=name,
            version=version,
            source_code=source_code,
            _fn=fn,
        )
        self._transforms[name] = ct
        logger.info("transform_registered", name=name, version=version)
        return ct

    def unregister(self, name: str) -> bool:
        """Desregistrar transformación."""
        if name in self._transforms:
            del self._transforms[name]
            return True
        return False

    def get(self, name: str) -> Optional[CompiledTransform]:
        """Obtener transformación por nombre."""
        return self._transforms.get(name)

    def execute(self, name: str, message: HL7Message, lookup: Optional[Callable] = None) -> HL7Message:
        """Ejecutar transformación por nombre.

        Args:
            name: Nombre de la transformación registrada.
            message: Mensaje HL7 a transformar.
            lookup: Función de lookup tables.

        Returns:
            Mensaje transformado.

        Raises:
            ValueError: Si la transformación no existe.
            ExecutionError: Si falla la ejecución.
        """
        ct = self._transforms.get(name)
        if ct is None:
            raise ValueError(f"Transform not found: {name}")
        return ct.execute(message, lookup)

    def list_names(self) -> list[str]:
        """Listar nombres de transformaciones."""
        return list(self._transforms.keys())

    @property
    def count(self) -> int:
        return len(self._transforms)
