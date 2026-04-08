"""
Sandbox de ejecución restringida para transformaciones.

Las transformaciones son código Python generado por AI o escrito manualmente.
Se ejecutan en un namespace restringido para evitar acceso al filesystem,
red, o módulos peligrosos.

Namespace permitido:
  - HL7Message, HL7Segment (manipulación de mensajes)
  - lookup() función (backed by Redis)
  - datetime, re (stdlib segura)
  - Builtins seguros (len, str, int, list, dict, range, etc.)
"""

from __future__ import annotations

import signal
import datetime
import re
from typing import Any, Callable, Optional

from ..hl7.parser import HL7Message, HL7Segment

# Builtins permitidos en el sandbox
SAFE_BUILTINS = {
    "len": len,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "range": range,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "sorted": sorted,
    "reversed": reversed,
    "min": min,
    "max": max,
    "sum": sum,
    "abs": abs,
    "round": round,
    "any": any,
    "all": all,
    "isinstance": isinstance,
    "type": type,
    "None": None,
    "True": True,
    "False": False,
    "ValueError": ValueError,
    "KeyError": KeyError,
    "TypeError": TypeError,
    "IndexError": IndexError,
}

# Timeout para ejecución de transforms (segundos)
DEFAULT_TIMEOUT = 5


class SandboxError(Exception):
    """Error durante ejecución en sandbox."""
    pass


class CompilationError(SandboxError):
    """Error al compilar código de transformación."""
    pass


class ExecutionError(SandboxError):
    """Error al ejecutar transformación."""
    pass


class TimeoutError(SandboxError):
    """Transform excedió el timeout."""
    pass


def compile_transform(source_code: str) -> Callable:
    """Compilar código de transformación en un namespace restringido.

    El source_code debe definir una función:
        def transform(msg: HL7Message, lookup) -> HL7Message

    Args:
        source_code: Código Python de la transformación.

    Returns:
        Función transform compilada.

    Raises:
        CompilationError: Si el código no compila o no define transform().
    """
    # Bloquear imports y accesos peligrosos
    _validate_source(source_code)

    # Crear namespace restringido
    namespace = _create_namespace()

    try:
        compiled = compile(source_code, "<transform>", "exec")
        exec(compiled, namespace)
    except SyntaxError as e:
        raise CompilationError(f"Syntax error in transform: {e}") from e
    except Exception as e:
        raise CompilationError(f"Compilation error: {e}") from e

    if "transform" not in namespace:
        raise CompilationError(
            "Transform code must define a function: def transform(msg, lookup) -> HL7Message"
        )

    fn = namespace["transform"]
    if not callable(fn):
        raise CompilationError("'transform' must be a callable function")

    return fn


def execute_transform(
    fn: Callable,
    message: HL7Message,
    lookup: Optional[Callable] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> HL7Message:
    """Ejecutar una transformación compilada con timeout.

    Args:
        fn: Función transform compilada.
        message: Mensaje HL7 a transformar.
        lookup: Función de lookup tables (sync).
        timeout: Timeout en segundos.

    Returns:
        Mensaje HL7 transformado.
    """
    if lookup is None:
        lookup = _noop_lookup

    def _timeout_handler(signum, frame):
        raise TimeoutError(f"Transform exceeded {timeout}s timeout")

    # Set alarm for timeout (only on Unix)
    old_handler = None
    try:
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(timeout)
    except (ValueError, OSError):
        # signal.alarm not available (e.g., not main thread)
        pass

    try:
        result = fn(message, lookup)
    except TimeoutError:
        raise
    except Exception as e:
        raise ExecutionError(f"Transform execution error: {e}") from e
    finally:
        # Cancel alarm
        try:
            signal.alarm(0)
            if old_handler is not None:
                signal.signal(signal.SIGALRM, old_handler)
        except (ValueError, OSError):
            pass

    if not isinstance(result, HL7Message):
        raise ExecutionError(
            f"Transform must return HL7Message, got {type(result).__name__}"
        )

    return result


def _validate_source(source_code: str) -> None:
    """Validar que el código no contenga operaciones peligrosas."""
    import re as _re

    # Patterns that are checked as literal substrings
    literal_patterns = [
        "__import__",
        "__builtins__",
        "__globals__",
        "__subclasses__",
    ]
    # Patterns that need word-boundary matching to avoid false positives
    # (e.g., "os." matching inside "destinos.")
    regex_patterns = [
        (r'\bimport\s', "import statement"),
        (r'\bfrom\s', "from import"),
        (r'\beval\s*\(', "eval()"),
        (r'\bexec\s*\(', "exec()"),
        (r'\bcompile\s*\(', "compile()"),
        (r'\bopen\s*\(', "open()"),
        (r'\bos\b\.', "os module"),
        (r'\bsys\b\.', "sys module"),
        (r'\bsubprocess\b', "subprocess module"),
        (r'\bshutil\b', "shutil module"),
        (r'\bpathlib\b', "pathlib module"),
        (r'\bsocket\b', "socket module"),
        (r'\brequests\b', "requests module"),
        (r'\burllib\b', "urllib module"),
        (r'\bhttp\b\.', "http module"),
    ]

    for pattern in literal_patterns:
        if pattern in source_code:
            raise CompilationError(
                f"Forbidden pattern in transform code: '{pattern}'"
            )

    for regex, description in regex_patterns:
        if _re.search(regex, source_code):
            raise CompilationError(
                f"Forbidden pattern in transform code: {description}"
            )


def _create_namespace() -> dict[str, Any]:
    """Crear namespace restringido para ejecución."""
    return {
        "__builtins__": SAFE_BUILTINS,
        # HL7 classes
        "HL7Message": HL7Message,
        "HL7Segment": HL7Segment,
        # Safe stdlib
        "datetime": datetime,
        "re": re,
    }


def _noop_lookup(table_name: str, key: str) -> str:
    """Lookup que retorna vacío (usado cuando no hay Redis)."""
    return ""
