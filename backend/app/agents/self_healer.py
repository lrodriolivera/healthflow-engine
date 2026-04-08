"""
SelfHealer Agent — diagnostica y corrige errores automáticamente.

Monitorea la error queue y:
  1. Analiza el patrón del error
  2. Diagnostica la causa raíz
  3. Genera un fix candidato
  4. Ejecuta en sandbox para validar
  5. Propone la corrección

Usa Claude Sonnet (balance velocidad/costo, llamado solo en errores).
"""

from __future__ import annotations

import json

import structlog

from .base import BaseAgent
from .bedrock import BedrockClient
from ..config import Settings

logger = structlog.get_logger()

SYSTEM_PROMPT = """You are a healthcare integration self-healing agent. You diagnose and fix errors in HL7 message processing.

When given an error from the message pipeline, you must:
1. Analyze the error type and details
2. Identify the root cause
3. Suggest a fix
4. If the error is in a transform, provide corrected code

Respond with JSON:
```json
{
    "diagnosis": "Root cause description",
    "severity": "critical|high|medium|low",
    "category": "parse_error|routing_error|transform_error|connection_error|data_error",
    "fix": {
        "type": "transform_update|routing_rule|config_change|manual",
        "description": "What to fix",
        "code": "corrected code if applicable",
        "auto_apply": true/false
    },
    "prevention": "How to prevent this in the future"
}
```

Rules:
1. Be conservative with auto_apply — only true for safe, reversible changes
2. For transform errors, always provide corrected code
3. For connection errors, suggest retry strategy
4. For data errors, suggest validation rules
5. Always explain reasoning clearly"""

TOOLS = [
    {
        "name": "read_error_details",
        "description": "Read full error details including the raw HL7 message and stack trace",
        "input_schema": {
            "type": "object",
            "properties": {
                "error_id": {"type": "string"},
            },
            "required": ["error_id"],
        },
    },
    {
        "name": "test_fix",
        "description": "Test a proposed fix against the failed message",
        "input_schema": {
            "type": "object",
            "properties": {
                "fix_code": {"type": "string"},
                "raw_message": {"type": "string"},
            },
            "required": ["fix_code", "raw_message"],
        },
    },
]


class SelfHealerAgent(BaseAgent):
    """Diagnostica y corrige errores del pipeline."""

    name = "self_healer"
    description = "Diagnoses and fixes errors in the message processing pipeline"
    model = "sonnet"
    system_prompt = SYSTEM_PROMPT
    tools = TOOLS
    max_tokens = 4096

    def __init__(self, bedrock_client: BedrockClient, settings: Settings):
        super().__init__(bedrock_client, settings)
        self._error_store = {}  # error_id → error details
        self.register_tool_handler("read_error_details", self._handle_read_error)
        self.register_tool_handler("test_fix", self._handle_test_fix)

    async def diagnose(self, error: dict) -> dict:
        """Diagnosticar un error de la error queue.

        Args:
            error: {
                "id": str,
                "error_type": str,
                "error_detail": str,
                "raw_message": str,
                "flow_id": str,
                "retry_count": int,
            }

        Returns:
            Diagnosis dict con fix propuesto.
        """
        error_id = str(error.get("id", "unknown"))
        self._error_store[error_id] = error

        prompt = f"""## Error to diagnose:

**Error ID:** {error_id}
**Type:** {error.get('error_type', 'unknown')}
**Detail:** {error.get('error_detail', 'No details')}
**Flow:** {error.get('flow_id', 'unknown')}
**Retry Count:** {error.get('retry_count', 0)}
**Raw Message Preview:** {error.get('raw_message', '')[:500]}

Diagnose this error and propose a fix. Use tools if needed."""

        messages = [BedrockClient.format_user_message(prompt)]
        response = await self._agentic_loop(messages)
        text = BedrockClient.extract_text(response)

        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            result = {
                "diagnosis": text,
                "severity": "medium",
                "category": "unknown",
                "fix": {"type": "manual", "description": text, "auto_apply": False},
                "prevention": "",
            }

        logger.info(
            "self_healer_diagnosis",
            error_id=error_id,
            category=result.get("category"),
            severity=result.get("severity"),
            auto_apply=result.get("fix", {}).get("auto_apply", False),
        )

        return result

    async def _handle_read_error(self, tool_input: dict) -> str:
        """Handler para read_error_details tool."""
        error_id = tool_input.get("error_id", "")
        error = self._error_store.get(error_id, {})
        return json.dumps(error, default=str)

    async def _handle_test_fix(self, tool_input: dict) -> str:
        """Handler para test_fix tool."""
        from ..core.hl7.parser import HL7Message
        from ..core.transform.sandbox import compile_transform, execute_transform

        fix_code = tool_input.get("fix_code", "")
        raw_message = tool_input.get("raw_message", "")

        try:
            fn = compile_transform(fix_code)
            msg = HL7Message.parse(raw_message)
            result = execute_transform(fn, msg)
            return json.dumps({
                "status": "success",
                "output_type": result.message_type,
                "output_segments": len(result.segments),
            })
        except Exception as e:
            return json.dumps({"status": "error", "error": str(e)})

    async def run(self, input_data: dict) -> dict:
        return await self.diagnose(input_data)
