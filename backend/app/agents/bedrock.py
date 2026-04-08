"""
AWS Bedrock client wrapper para Claude.

Todas las interacciones con Claude pasan por este client.
Usa la Converse API de Bedrock para mensajes, system prompts y tool use.
boto3 es sincrónico — se wrappea con run_in_executor para no bloquear asyncio.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

import boto3
import structlog

from ..config import Settings

logger = structlog.get_logger()


class BedrockClient:
    """Client centralizado para Claude vía AWS Bedrock."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = boto3.client(
            "bedrock-runtime",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
        self.model_sonnet = settings.bedrock_model_sonnet
        self.model_opus = settings.bedrock_model_opus

    def _sync_converse(
        self,
        model_id: str,
        system: str,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> dict:
        """Llamada sincrónica a Bedrock Converse API."""
        kwargs: dict[str, Any] = {
            "modelId": model_id,
            "messages": messages,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
        }

        if system:
            kwargs["system"] = [{"text": system}]

        if tools:
            kwargs["toolConfig"] = {
                "tools": [
                    {
                        "toolSpec": {
                            "name": tool["name"],
                            "description": tool.get("description", ""),
                            "inputSchema": {
                                "json": tool.get("input_schema", {"type": "object", "properties": {}})
                            },
                        }
                    }
                    for tool in tools
                ]
            }

        response = self._client.converse(**kwargs)
        return response

    async def invoke(
        self,
        model_id: str,
        system: str,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> dict:
        """Invoke Claude on Bedrock (async wrapper)."""
        loop = asyncio.get_running_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self._sync_converse(
                model_id, system, messages, tools, max_tokens, temperature
            ),
        )

        logger.debug(
            "bedrock_invoked",
            model=model_id,
            input_tokens=response.get("usage", {}).get("inputTokens", 0),
            output_tokens=response.get("usage", {}).get("outputTokens", 0),
            stop_reason=response.get("stopReason", "unknown"),
        )

        return response

    async def invoke_sonnet(
        self, system: str, messages: list[dict], **kwargs
    ) -> dict:
        """Shortcut para Sonnet (routing, ops, healing)."""
        return await self.invoke(self.model_sonnet, system, messages, **kwargs)

    async def invoke_opus(
        self, system: str, messages: list[dict], **kwargs
    ) -> dict:
        """Shortcut para Opus (transform design, complex analysis)."""
        return await self.invoke(self.model_opus, system, messages, **kwargs)

    @staticmethod
    def extract_text(response: dict) -> str:
        """Extraer texto de la respuesta de Bedrock."""
        output = response.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [])
        texts = [block["text"] for block in content if "text" in block]
        return "\n".join(texts)

    @staticmethod
    def extract_tool_uses(response: dict) -> list[dict]:
        """Extraer tool_use blocks de la respuesta."""
        output = response.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [])
        return [
            {
                "id": block["toolUse"]["toolUseId"],
                "name": block["toolUse"]["name"],
                "input": block["toolUse"]["input"],
            }
            for block in content
            if "toolUse" in block
        ]

    @staticmethod
    def format_user_message(text: str) -> dict:
        """Formatear mensaje de usuario para Bedrock."""
        return {"role": "user", "content": [{"text": text}]}

    @staticmethod
    def format_assistant_message(text: str) -> dict:
        """Formatear mensaje de asistente."""
        return {"role": "assistant", "content": [{"text": text}]}

    @staticmethod
    def format_tool_result(tool_use_id: str, result: str) -> dict:
        """Formatear resultado de tool para Bedrock."""
        return {
            "role": "user",
            "content": [
                {
                    "toolResult": {
                        "toolUseId": tool_use_id,
                        "content": [{"text": result}],
                    }
                }
            ],
        }
