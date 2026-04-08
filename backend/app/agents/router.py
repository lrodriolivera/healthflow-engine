"""
AI Router Agent — ruta mensajes que no matchean reglas deterministas.

Usa Claude Sonnet para velocidad (~500ms budget).
Cuando confidence > 0.8, auto-genera una regla determinista para que
el mismo patrón se rutee sin AI la próxima vez.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from .base import BaseAgent
from .bedrock import BedrockClient
from ..config import Settings
from ..core.hl7.parser import HL7Message

logger = structlog.get_logger()

SYSTEM_PROMPT = """You are a healthcare message routing specialist for HL7 v2.x messages.

Given an HL7 message that didn't match any deterministic routing rule, you must determine the appropriate destination(s).

You will receive:
1. Key fields from the HL7 message
2. Available destinations with descriptions
3. Existing routing rules (so you understand the patterns)

You must respond with a JSON object:
```json
{
    "destinations": [
        {"name": "DESTINATION_NAME", "adapter_name": "ADAPTER_NAME", "transform": null}
    ],
    "confidence": 0.85,
    "reasoning": "Brief explanation of routing decision",
    "suggested_rule": {
        "name": "Auto: descriptive rule name",
        "conditions": [
            {"field": "MSH-9.1", "operator": "equals", "value": "ADT"}
        ],
        "destinations": [
            {"name": "DESTINATION_NAME", "adapter_name": "ADAPTER_NAME"}
        ],
        "priority": 50
    }
}
```

Rules:
1. Always include reasoning for your decision
2. confidence should be 0.0-1.0 (0.8+ means you're very confident)
3. suggested_rule should be a deterministic rule that would catch this pattern next time
4. If you cannot determine a destination, return empty destinations with low confidence
5. Consider message type (MSH-9), sending/receiving app (MSH-3/5), patient location (PV1-3), and any other relevant fields
6. ALWAYS respond with valid JSON only, no other text"""


class RouterAgent(BaseAgent):
    """Ruta mensajes sin match determinista via Claude Sonnet."""

    name = "ai_router"
    description = "Routes HL7 messages that don't match deterministic rules"
    model = "sonnet"
    system_prompt = SYSTEM_PROMPT
    max_tokens = 2048
    temperature = 0.0

    async def route(
        self,
        message: HL7Message,
        available_destinations: list[dict],
        existing_rules: list[Any],
    ) -> dict:
        """Rutear un mensaje que no matcheó reglas deterministas.

        Args:
            message: Mensaje HL7 parseado.
            available_destinations: Destinos disponibles con metadata.
            existing_rules: Reglas existentes para contexto.

        Returns:
            {
                "destinations": list[dict],
                "confidence": float,
                "reasoning": str,
                "suggested_rule": dict | None,
            }
        """
        # Extract key fields from message
        message_fields = {
            "MSH-9 (message_type)": message.message_type,
            "MSH-9.1 (type_code)": message.message_type_code,
            "MSH-9.2 (trigger_event)": message.trigger_event,
            "MSH-3 (sending_app)": message.sending_application,
            "MSH-4 (sending_facility)": message.sending_facility,
            "MSH-5 (receiving_app)": message.receiving_application,
            "MSH-6 (receiving_facility)": message.receiving_facility,
            "MSH-12 (version)": message.version,
        }
        # Add PV1 if present
        pv1 = message.get_segment("PV1")
        if pv1:
            message_fields["PV1-2 (patient_class)"] = pv1.get_field(2)
            message_fields["PV1-3 (location)"] = pv1.get_field(3)

        # Add OBR if present
        obr = message.get_segment("OBR")
        if obr:
            message_fields["OBR-4 (service_id)"] = obr.get_field(4)

        # Format existing rules summary
        rules_summary = []
        for rule in existing_rules[:20]:  # Limit to avoid token explosion
            if hasattr(rule, "name"):
                rules_summary.append(f"- {rule.name} (priority={rule.priority})")

        prompt = f"""## HL7 Message Fields:
{json.dumps(message_fields, indent=2)}

## Available Destinations:
{json.dumps(available_destinations, indent=2)}

## Existing Routing Rules:
{chr(10).join(rules_summary) if rules_summary else "No existing rules"}

## Segments in message:
{', '.join(seg.name for seg in message.segments)}

Route this message to the appropriate destination(s)."""

        messages = [BedrockClient.format_user_message(prompt)]

        try:
            response = await self._call_model(messages)
            text = BedrockClient.extract_text(response)
            result = json.loads(text)

            logger.info(
                "ai_router_decision",
                message_type=message.message_type,
                destinations=[d["name"] for d in result.get("destinations", [])],
                confidence=result.get("confidence", 0),
                reasoning=result.get("reasoning", ""),
            )

            return result

        except json.JSONDecodeError as e:
            logger.error("ai_router_json_error", error=str(e), raw=text[:200])
            return {
                "destinations": [],
                "confidence": 0.0,
                "reasoning": f"Failed to parse model response: {e}",
                "suggested_rule": None,
            }
        except Exception as e:
            logger.error("ai_router_error", error=str(e))
            return {
                "destinations": [],
                "confidence": 0.0,
                "reasoning": f"Router error: {e}",
                "suggested_rule": None,
            }

    async def run(self, input_data: dict) -> dict:
        """Interface estándar de BaseAgent."""
        message = HL7Message.parse(input_data["raw_message"])
        return await self.route(
            message=message,
            available_destinations=input_data.get("destinations", []),
            existing_rules=input_data.get("rules", []),
        )
