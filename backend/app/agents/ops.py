"""
OpsAgent — interfaz ChatOps en lenguaje natural.

Permite hacer preguntas y ejecutar acciones vía natural language:
  - "¿Por qué falló el mensaje MSG001?"
  - "Muestra los últimos errores del flow ADT"
  - "Reinicia el adapter MLLP_LIS"
  - "¿Cuántos mensajes procesamos hoy?"

Usa Claude Sonnet + tool_use para ejecutar acciones reales.
"""

from __future__ import annotations

import json
from typing import Any

import structlog

from .base import BaseAgent
from .bedrock import BedrockClient
from ..config import Settings

logger = structlog.get_logger()

SYSTEM_PROMPT = """You are the operations agent for HealthFlow Engine, a healthcare integration platform that processes HL7 v2.x messages.

You help operators manage and monitor the system via natural language. You can:
1. Query message logs and traces
2. List and investigate errors
3. Check flow health and status
4. Manage adapters and flows
5. Run diagnostic tests

Always respond in the same language as the user's message (Spanish or English).
Be concise and actionable. Use tables for structured data.
When showing HL7 data, highlight the relevant fields.

IMPORTANT: Before taking any destructive action (disable flow, restart adapter), confirm with the user first by describing what you'll do."""

TOOLS = [
    {
        "name": "query_messages",
        "description": "Search message logs with filters",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_type": {"type": "string", "description": "HL7 message type filter (e.g., ADT, ORM)"},
                "status": {"type": "string", "description": "Status filter (received, routed, error, etc.)"},
                "flow_id": {"type": "string", "description": "Flow ID filter"},
                "limit": {"type": "integer", "description": "Max results (default 10)"},
            },
        },
    },
    {
        "name": "get_trace",
        "description": "Get full processing trace for a specific message",
        "input_schema": {
            "type": "object",
            "properties": {
                "message_id": {"type": "string", "description": "Message control ID or trace ID"},
            },
            "required": ["message_id"],
        },
    },
    {
        "name": "list_errors",
        "description": "List recent errors from the error queue",
        "input_schema": {
            "type": "object",
            "properties": {
                "flow_id": {"type": "string"},
                "limit": {"type": "integer"},
            },
        },
    },
    {
        "name": "get_flow_status",
        "description": "Get health and metrics for a flow or all flows",
        "input_schema": {
            "type": "object",
            "properties": {
                "flow_id": {"type": "string", "description": "Optional flow ID, omit for all flows"},
            },
        },
    },
    {
        "name": "restart_adapter",
        "description": "Restart a specific adapter (requires confirmation)",
        "input_schema": {
            "type": "object",
            "properties": {
                "adapter_name": {"type": "string"},
                "confirmed": {"type": "boolean"},
            },
            "required": ["adapter_name"],
        },
    },
]


class OpsAgent(BaseAgent):
    """Agente ChatOps para operaciones en lenguaje natural."""

    name = "ops_agent"
    description = "Natural language operations management interface"
    model = "sonnet"
    system_prompt = SYSTEM_PROMPT
    tools = TOOLS
    max_tokens = 4096

    def __init__(self, bedrock_client: BedrockClient, settings: Settings):
        super().__init__(bedrock_client, settings)
        self._context_providers: dict[str, Any] = {}

    def set_context_provider(self, tool_name: str, provider) -> None:
        """Registrar un provider de contexto para un tool.

        Los providers son funciones async que ejecutan la acción real
        (consultar DB, obtener métricas, etc.).
        """
        self._context_providers[tool_name] = provider
        self.register_tool_handler(tool_name, provider)

    async def chat(self, user_message: str, context: dict | None = None) -> str:
        """Procesar un mensaje ChatOps.

        Args:
            user_message: Pregunta o comando del operador.
            context: Contexto adicional (usuario, flow actual, etc.).

        Returns:
            Respuesta en lenguaje natural.
        """
        prompt = user_message
        if context:
            prompt = f"Context: {json.dumps(context)}\n\nUser: {user_message}"

        messages = [BedrockClient.format_user_message(prompt)]
        response = await self._agentic_loop(messages)
        text = BedrockClient.extract_text(response)

        logger.info(
            "ops_agent_chat",
            user_message=user_message[:100],
            response_length=len(text),
        )

        return text

    async def run(self, input_data: dict) -> dict:
        response = await self.chat(
            user_message=input_data["message"],
            context=input_data.get("context"),
        )
        return {"response": response}
