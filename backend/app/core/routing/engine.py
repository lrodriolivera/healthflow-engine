"""
Motor de routing determinista.

Evalúa reglas compiladas en <1ms para decidir a qué destinos enviar cada mensaje.
Si ninguna regla matchea, delega al AI Router (slow-path, ~500ms).

Reglas se definen en YAML y se compilan a funciones Python.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

import structlog

from ..hl7.parser import HL7Message

logger = structlog.get_logger()


@dataclass
class RoutingDestination:
    """Un destino de routing."""
    name: str
    adapter_name: str              # Nombre del adapter outbound
    transform: Optional[str] = None  # Nombre de la transformación a aplicar (None = passthrough)
    enabled: bool = True


@dataclass
class RoutingRule:
    """Una regla de routing.

    Ejemplo YAML:
        - name: "ADT to LIS"
          conditions:
            - field: "MSH-9.1"
              operator: "equals"
              value: "ADT"
          destinations:
            - name: "LIS"
              adapter_name: "MLLP_OUT_LIS"
              transform: "adt_to_lis"
    """
    name: str
    conditions: list[RoutingCondition]
    destinations: list[RoutingDestination]
    priority: int = 100   # Lower = higher priority
    enabled: bool = True
    stop_on_match: bool = False  # If True, don't evaluate further rules after match


@dataclass
class RoutingCondition:
    """Una condición de routing."""
    field: str           # HL7 path: "MSH-9.1", "PID-3", etc.
    operator: str        # "equals", "not_equals", "contains", "starts_with", "matches", "in"
    value: str           # Valor a comparar
    case_sensitive: bool = True

    def evaluate(self, message: HL7Message) -> bool:
        """Evaluar condición contra un mensaje HL7."""
        actual = message.get(self.field)

        if not self.case_sensitive:
            actual = actual.lower()
            compare_value = self.value.lower()
        else:
            compare_value = self.value

        if self.operator == "equals":
            return actual == compare_value
        elif self.operator == "not_equals":
            return actual != compare_value
        elif self.operator == "contains":
            return compare_value in actual
        elif self.operator == "not_contains":
            return compare_value not in actual
        elif self.operator == "starts_with":
            return actual.startswith(compare_value)
        elif self.operator == "ends_with":
            return actual.endswith(compare_value)
        elif self.operator == "matches":
            return bool(re.match(compare_value, actual))
        elif self.operator == "in":
            values = [v.strip() for v in compare_value.split(",")]
            return actual in values
        elif self.operator == "not_empty":
            return bool(actual)
        elif self.operator == "empty":
            return not actual
        else:
            logger.warning("unknown_routing_operator", operator=self.operator)
            return False


class RoutingEngine:
    """Motor de routing determinista.

    Equivalente al routing de una Production IRIS, pero con reglas compiladas en Python.
    """

    def __init__(self):
        self._rules: list[RoutingRule] = []

    def add_rule(self, rule: RoutingRule) -> None:
        """Agregar regla y re-ordenar por prioridad."""
        self._rules.append(rule)
        self._rules.sort(key=lambda r: r.priority)

    def remove_rule(self, name: str) -> bool:
        """Eliminar regla por nombre."""
        initial_count = len(self._rules)
        self._rules = [r for r in self._rules if r.name != name]
        return len(self._rules) < initial_count

    def evaluate(self, message: HL7Message) -> list[RoutingDestination]:
        """Evaluar todas las reglas y retornar destinos.

        Returns:
            Lista de destinos (puede ser vacía si ninguna regla matchea).
            Lista vacía → candidato para AI Router (slow-path).
        """
        matched_destinations: list[RoutingDestination] = []

        for rule in self._rules:
            if not rule.enabled:
                continue

            # All conditions must match (AND logic)
            all_match = all(cond.evaluate(message) for cond in rule.conditions)

            if all_match:
                logger.debug(
                    "routing_rule_matched",
                    rule=rule.name,
                    message_type=message.message_type,
                    message_id=message.message_control_id,
                    destinations=[d.name for d in rule.destinations if d.enabled],
                )
                matched_destinations.extend(
                    d for d in rule.destinations if d.enabled
                )
                if rule.stop_on_match:
                    break

        if not matched_destinations:
            logger.info(
                "routing_no_match",
                message_type=message.message_type,
                message_id=message.message_control_id,
            )

        return matched_destinations

    @property
    def rule_count(self) -> int:
        return len(self._rules)

    def get_rules(self) -> list[RoutingRule]:
        return list(self._rules)
