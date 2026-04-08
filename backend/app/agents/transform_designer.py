"""
TransformDesigner Agent — genera transformaciones Python desde especificaciones NL.

Usa Claude Opus para máxima calidad en code generation.
Llamado en design-time (no en hot path).

Flow:
  1. Recibe spec en lenguaje natural + mensajes de ejemplo
  2. Claude Opus genera código Python
  3. Valida ejecutando en sandbox contra mensajes de ejemplo
  4. Si falla, envía error al modelo para corrección
  5. Retorna código validado
"""

from __future__ import annotations

import json
from typing import Optional

import structlog

from .base import BaseAgent
from .bedrock import BedrockClient
from ..config import Settings
from ..core.hl7.parser import HL7Message
from ..core.transform.sandbox import compile_transform, execute_transform, SandboxError

logger = structlog.get_logger()

SYSTEM_PROMPT = """You are an expert healthcare integration engineer specializing in HL7 v2.x message transformations.

You generate Python transformation functions for HL7 v2.x messages. Every function you generate MUST follow this exact signature:

```python
def transform(msg, lookup):
    msg = msg.clone()
    # ... your transformation logic ...
    return msg
```

## Available API:

### Message access:
- `msg.get("SEG-N")` → field value (e.g., `msg.get("PID-3")`)
- `msg.get("SEG-N.C")` → component (e.g., `msg.get("PID-3.1")`)
- `msg.get("SEG-N.C.S")` → subcomponent
- `msg.get("SEG-N", segment_index=1)` → second occurrence of segment

### Message modification:
- `msg.set("SEG-N", value)` → set field value
- `msg.clone()` → deep copy (ALWAYS clone before mutating)

### Segment access:
- `msg.get_segment(name, index)` → get segment by name
- `msg.get_all_segments(name)` → all segments of a type
- `msg.count_segments(name)` → count segments
- `msg.add_segment(segment, after="SEG")` → add segment after named segment
- `msg.remove_segment(name, index)` → remove segment

### Segment field access:
- `segment.get_field(index)` → 1-based field access
- `segment.get_component(field_idx, comp_idx)` → component
- `segment.set_field(index, value)` → set field
- `segment.get_repetition(field_idx, rep_idx)` → repetition

### Creating segments:
- `HL7Segment(name="ZHF", fields=["field1", "field2", ...])`

### Lookup tables:
- `lookup(table_name, key)` → returns value string or empty string

### Available builtins:
- `len`, `str`, `int`, `float`, `bool`, `list`, `dict`, `range`, `sorted`, `min`, `max`
- `datetime` module, `re` module

## Rules:
1. ALWAYS clone the message first: `msg = msg.clone()`
2. NEVER use import statements
3. Handle missing segments/fields gracefully (they return "")
4. Preserve Z-segments unless explicitly asked to remove them
5. Return the transformed HL7Message
6. Keep code simple and readable
7. Use lookup() for any value mapping/translation

Respond with ONLY the Python code, no markdown fences, no explanations."""

VALIDATION_TOOL = {
    "name": "validate_transform",
    "description": "Validate the generated transform code by executing it against sample HL7 messages in a sandbox",
    "input_schema": {
        "type": "object",
        "properties": {
            "source_code": {
                "type": "string",
                "description": "The Python transform function code to validate",
            },
        },
        "required": ["source_code"],
    },
}


class TransformDesignerAgent(BaseAgent):
    """Genera transformaciones Python desde especificaciones en lenguaje natural."""

    name = "transform_designer"
    description = "Generates HL7 transformation code from natural language specifications"
    model = "opus"
    system_prompt = SYSTEM_PROMPT
    tools = [VALIDATION_TOOL]
    max_tokens = 8192

    def __init__(self, bedrock_client: BedrockClient, settings: Settings):
        super().__init__(bedrock_client, settings)
        self._test_messages: list[str] = []
        self._test_lookup = lambda table, key: ""
        self.register_tool_handler("validate_transform", self._handle_validate)

    async def design_transform(
        self,
        spec: str,
        sample_messages: list[str],
        lookup_fn=None,
        max_retries: int = 3,
    ) -> dict:
        """Generar una transformación desde especificación NL.

        Args:
            spec: Especificación en lenguaje natural.
            sample_messages: Mensajes HL7 de ejemplo para validar.
            lookup_fn: Función de lookup tables para validación.
            max_retries: Intentos máximos de corrección.

        Returns:
            {
                "source_code": str,
                "validated": bool,
                "test_results": list[dict],
                "iterations": int,
            }
        """
        self._test_messages = sample_messages
        if lookup_fn:
            self._test_lookup = lookup_fn

        # Build prompt with sample messages
        samples_text = "\n\n".join(
            f"### Sample message {i+1}:\n```\n{msg}\n```"
            for i, msg in enumerate(sample_messages)
        )

        user_prompt = f"""## Transformation specification:
{spec}

## Sample HL7 messages to transform:
{samples_text}

Generate the Python transform function. Then use the validate_transform tool to verify it works correctly against the sample messages."""

        messages = [BedrockClient.format_user_message(user_prompt)]

        # Run agentic loop — model generates code, validates, fixes if needed
        response = await self._agentic_loop(messages, max_iterations=max_retries * 2)

        # Extract the final code
        text = BedrockClient.extract_text(response)
        source_code = self._extract_code(text)

        # Final validation
        validated, test_results = self._validate_code(source_code)

        logger.info(
            "transform_designed",
            spec_length=len(spec),
            validated=validated,
            code_length=len(source_code),
        )

        return {
            "source_code": source_code,
            "validated": validated,
            "test_results": test_results,
        }

    async def _handle_validate(self, tool_input: dict) -> str:
        """Handler para el tool validate_transform."""
        source_code = tool_input.get("source_code", "")
        validated, results = self._validate_code(source_code)

        if validated:
            return json.dumps({
                "status": "success",
                "message": f"Transform validated successfully against {len(results)} messages",
                "results": results,
            })
        else:
            return json.dumps({
                "status": "error",
                "message": "Validation failed",
                "results": results,
            })

    def _validate_code(self, source_code: str) -> tuple[bool, list[dict]]:
        """Validar código contra mensajes de ejemplo."""
        if not source_code.strip():
            return False, [{"error": "Empty source code"}]

        # Compile
        try:
            fn = compile_transform(source_code)
        except SandboxError as e:
            return False, [{"error": f"Compilation failed: {e}"}]

        # Execute against each sample message
        results = []
        all_passed = True
        for i, raw_msg in enumerate(self._test_messages):
            try:
                msg = HL7Message.parse(raw_msg)
                result = execute_transform(fn, msg, lookup=self._test_lookup)
                results.append({
                    "message_index": i,
                    "status": "success",
                    "input_type": msg.message_type,
                    "output_type": result.message_type,
                    "output_segments": len(result.segments),
                })
            except Exception as e:
                all_passed = False
                results.append({
                    "message_index": i,
                    "status": "error",
                    "error": str(e),
                })

        return all_passed, results

    @staticmethod
    def _extract_code(text: str) -> str:
        """Extraer código Python de la respuesta del modelo."""
        # If wrapped in markdown code fences, extract
        if "```python" in text:
            start = text.index("```python") + len("```python")
            end = text.index("```", start)
            return text[start:end].strip()
        if "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            return text[start:end].strip()
        # If starts with def, use as-is
        if "def transform" in text:
            # Find the start of the function
            idx = text.index("def transform")
            return text[idx:].strip()
        return text.strip()

    async def run(self, input_data: dict) -> dict:
        """Interface estándar de BaseAgent."""
        return await self.design_transform(
            spec=input_data["spec"],
            sample_messages=input_data.get("sample_messages", []),
        )
