"""
REST Adapter — webhook receiver (inbound) + HTTP client (outbound).

Común en hospitales modernos:
  - Recibir notificaciones de sistemas cloud (Epic FHIR, Azure Health)
  - Enviar mensajes a APIs REST (EHR APIs, portales de pacientes)
  - Webhook callbacks para FHIR Subscriptions

Soporta:
  - RESTReceiver: FastAPI sub-router que recibe webhooks
  - RESTSender: httpx async client con auth configurable
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable, Optional

import httpx
import structlog

logger = structlog.get_logger()

WebhookHandler = Callable[[dict, dict], Awaitable[Optional[dict]]]
"""Callback: async def handler(body: dict, headers: dict) -> Optional[dict]"""


class AuthType(str, Enum):
    none = "none"
    basic = "basic"
    bearer = "bearer"
    api_key = "api_key"
    oauth2_client_credentials = "oauth2_cc"


@dataclass
class RESTSenderConfig:
    """Configuración de un REST sender (outbound)."""
    base_url: str
    name: str = ""
    auth_type: AuthType = AuthType.none
    auth_username: Optional[str] = None
    auth_password: Optional[str] = None
    auth_token: Optional[str] = None
    api_key_header: str = "X-API-Key"
    api_key_value: Optional[str] = None
    oauth2_token_url: Optional[str] = None
    oauth2_client_id: Optional[str] = None
    oauth2_client_secret: Optional[str] = None
    timeout: int = 30
    retry_count: int = 3
    retry_interval: int = 5
    default_headers: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.name:
            self.name = f"REST_{self.base_url[:30]}"


class RESTSender:
    """Cliente REST async para enviar mensajes a APIs externas.

    Equivalente a EnsLib.HTTP.OutboundAdapter en IRIS.
    """

    def __init__(self, config: RESTSenderConfig):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None
        self._oauth2_token: Optional[str] = None

    async def connect(self) -> None:
        """Crear HTTP client."""
        headers = {**self.config.default_headers}

        auth = None
        if self.config.auth_type == AuthType.basic:
            auth = httpx.BasicAuth(
                self.config.auth_username or "",
                self.config.auth_password or "",
            )
        elif self.config.auth_type == AuthType.bearer:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"
        elif self.config.auth_type == AuthType.api_key:
            headers[self.config.api_key_header] = self.config.api_key_value or ""

        self._client = httpx.AsyncClient(
            base_url=self.config.base_url,
            headers=headers,
            auth=auth,
            timeout=self.config.timeout,
        )

        # OAuth2 client credentials flow
        if self.config.auth_type == AuthType.oauth2_client_credentials:
            await self._refresh_oauth2_token()

        logger.info("rest_sender_connected", name=self.config.name, url=self.config.base_url)

    async def disconnect(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def send(self, message: str) -> Optional[str]:
        """Enviar mensaje como POST request. Returns response body."""
        return await self.post("/", content=message, content_type="text/plain")

    async def post(
        self, path: str, json: dict = None, content: str = None,
        content_type: str = "application/json",
    ) -> Optional[str]:
        """POST request con retry."""
        if not self._client:
            await self.connect()

        last_error = None
        for attempt in range(1, self.config.retry_count + 1):
            try:
                kwargs: dict[str, Any] = {}
                if json is not None:
                    kwargs["json"] = json
                elif content is not None:
                    kwargs["content"] = content.encode("utf-8")
                    kwargs["headers"] = {"Content-Type": content_type}

                response = await self._client.post(path, **kwargs)

                if response.status_code == 401 and self.config.auth_type == AuthType.oauth2_client_credentials:
                    await self._refresh_oauth2_token()
                    response = await self._client.post(path, **kwargs)

                response.raise_for_status()

                logger.info("rest_request_sent", name=self.config.name, status=response.status_code)
                return response.text

            except httpx.HTTPStatusError as e:
                last_error = e
                logger.warning("rest_request_failed", name=self.config.name, status=e.response.status_code, attempt=attempt)
            except Exception as e:
                last_error = e
                logger.warning("rest_request_error", name=self.config.name, error=str(e), attempt=attempt)

            if attempt < self.config.retry_count:
                await asyncio.sleep(self.config.retry_interval)

        raise ConnectionError(f"REST request failed after {self.config.retry_count} attempts: {last_error}")

    async def get(self, path: str, params: dict = None) -> str:
        """GET request."""
        if not self._client:
            await self.connect()
        response = await self._client.get(path, params=params)
        response.raise_for_status()
        return response.text

    async def put(self, path: str, json: dict = None) -> str:
        """PUT request."""
        if not self._client:
            await self.connect()
        response = await self._client.put(path, json=json)
        response.raise_for_status()
        return response.text

    async def _refresh_oauth2_token(self) -> None:
        """Obtener token OAuth2 via client credentials flow."""
        if not self.config.oauth2_token_url:
            return

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.config.oauth2_token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.config.oauth2_client_id or "",
                    "client_secret": self.config.oauth2_client_secret or "",
                },
            )
            response.raise_for_status()
            token_data = response.json()
            self._oauth2_token = token_data.get("access_token", "")

            if self._client:
                self._client.headers["Authorization"] = f"Bearer {self._oauth2_token}"

            logger.info("rest_oauth2_token_refreshed", name=self.config.name)
