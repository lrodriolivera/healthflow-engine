"""
Base agent class para todos los agentes AI de HealthFlow.

Cada agente tiene:
  - Un system prompt especializado
  - Tools opcionales (Bedrock tool_use)
  - Un modelo preferido (sonnet para ops, opus para design)
  - Lógica de tool dispatch
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

import structlog

from .bedrock import BedrockClient
from ..config import Settings

logger = structlog.get_logger()


class BaseAgent(ABC):
    """Clase base para agentes AI."""

    name: str = "base_agent"
    description: str = ""
    model: str = "sonnet"  # "sonnet" or "opus"
    system_prompt: str = ""
    tools: list[dict] = []
    max_tokens: int = 4096
    temperature: float = 0.0

    def __init__(self, bedrock_client: BedrockClient, settings: Settings):
        self._bedrock = bedrock_client
        self._settings = settings
        self._tool_handlers: dict[str, Any] = {}

    def register_tool_handler(self, tool_name: str, handler) -> None:
        """Registrar handler para un tool."""
        self._tool_handlers[tool_name] = handler

    async def _call_model(self, messages: list[dict], **kwargs) -> dict:
        """Llamar al modelo apropiado según self.model."""
        call_kwargs = {
            "system": self.system_prompt,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", self.max_tokens),
            "temperature": kwargs.get("temperature", self.temperature),
        }
        if self.tools:
            call_kwargs["tools"] = self.tools

        if self.model == "opus":
            return await self._bedrock.invoke_opus(**call_kwargs)
        return await self._bedrock.invoke_sonnet(**call_kwargs)

    async def _agentic_loop(
        self, messages: list[dict], max_iterations: int = 10
    ) -> dict:
        """Ejecutar loop agéntico con tool_use hasta end_turn.

        El modelo puede usar tools múltiples veces antes de dar una respuesta final.
        """
        for iteration in range(max_iterations):
            response = await self._call_model(messages)
            stop_reason = response.get("stopReason", "end_turn")

            if stop_reason != "tool_use":
                return response

            # Handle tool uses
            tool_uses = BedrockClient.extract_tool_uses(response)
            if not tool_uses:
                return response

            # Add assistant response to messages
            messages.append(response["output"]["message"])

            # Execute tools and add results
            for tool_use in tool_uses:
                tool_name = tool_use["name"]
                tool_input = tool_use["input"]
                tool_id = tool_use["id"]

                logger.info(
                    "agent_tool_use",
                    agent=self.name,
                    tool=tool_name,
                    iteration=iteration,
                )

                handler = self._tool_handlers.get(tool_name)
                if handler:
                    try:
                        result = await handler(tool_input)
                        result_str = str(result) if not isinstance(result, str) else result
                    except Exception as e:
                        result_str = f"Error executing tool {tool_name}: {e}"
                        logger.error(
                            "agent_tool_error",
                            agent=self.name,
                            tool=tool_name,
                            error=str(e),
                        )
                else:
                    result_str = f"Unknown tool: {tool_name}"

                messages.append(
                    BedrockClient.format_tool_result(tool_id, result_str)
                )

        logger.warning("agent_max_iterations", agent=self.name, max=max_iterations)
        return response

    @abstractmethod
    async def run(self, input_data: dict) -> dict:
        """Ejecutar la tarea principal del agente. Override en subclases."""
        ...
