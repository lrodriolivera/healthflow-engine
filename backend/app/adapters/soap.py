"""
SOAP Adapter — cliente genérico para web services SOAP.

Común en hospitales: SAP ISH, TrackCare, sistemas de farmacia, RIS.
Soporta:
  - HTTP POST con SOAP envelope
  - Basic Auth preemptive
  - SSL/TLS configurable
  - Timeout + retry
  - MTOM (via aiohttp)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional
from xml.etree import ElementTree as ET

import aiohttp
import structlog

logger = structlog.get_logger()

SOAP_ENVELOPE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
  <soapenv:Header/>
  <soapenv:Body>
    {body}
  </soapenv:Body>
</soapenv:Envelope>"""


@dataclass
class SOAPConfig:
    """Configuración de un cliente SOAP."""
    url: str
    name: str = ""
    action: str = ""  # SOAPAction header
    username: Optional[str] = None
    password: Optional[str] = None
    timeout: int = 30
    retry_count: int = 3
    retry_interval: int = 5
    ssl_verify: bool = True
    content_type: str = "text/xml; charset=utf-8"

    def __post_init__(self):
        if not self.name:
            self.name = f"SOAP_{self.url[:30]}"


class SOAPClient:
    """Cliente SOAP async para enviar mensajes a web services.

    Equivalente a EnsLib.SOAP.OutboundAdapter en IRIS.
    """

    def __init__(self, config: SOAPConfig):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None

    async def connect(self) -> None:
        """Crear session HTTP."""
        auth = None
        if self.config.username:
            auth = aiohttp.BasicAuth(self.config.username, self.config.password or "")

        timeout = aiohttp.ClientTimeout(total=self.config.timeout)
        connector = aiohttp.TCPConnector(ssl=self.config.ssl_verify)

        self._session = aiohttp.ClientSession(
            auth=auth,
            timeout=timeout,
            connector=connector,
        )
        logger.info("soap_client_connected", name=self.config.name, url=self.config.url)

    async def disconnect(self) -> None:
        """Cerrar session."""
        if self._session:
            await self._session.close()
            self._session = None

    async def send(self, message: str) -> Optional[str]:
        """Enviar mensaje como SOAP request.

        Si el message es XML raw, lo wrappea en SOAP envelope.
        Si ya es un SOAP envelope, lo envía tal cual.

        Returns:
            Response body como string, o None en caso de éxito sin body.
        """
        if not self._session:
            await self.connect()

        # Wrap in SOAP envelope if not already wrapped
        if "<soapenv:Envelope" not in message and "<soap:Envelope" not in message:
            payload = SOAP_ENVELOPE_TEMPLATE.format(body=message)
        else:
            payload = message

        headers = {
            "Content-Type": self.config.content_type,
        }
        if self.config.action:
            headers["SOAPAction"] = self.config.action

        last_error = None
        for attempt in range(1, self.config.retry_count + 1):
            try:
                async with self._session.post(
                    self.config.url,
                    data=payload.encode("utf-8"),
                    headers=headers,
                ) as response:
                    body = await response.text()

                    if response.status >= 400:
                        fault = _extract_soap_fault(body)
                        raise SOAPError(
                            f"SOAP error {response.status}: {fault or body[:200]}"
                        )

                    logger.info(
                        "soap_request_sent",
                        name=self.config.name,
                        status=response.status,
                        attempt=attempt,
                    )
                    return body

            except SOAPError:
                raise
            except Exception as e:
                last_error = e
                logger.warning(
                    "soap_request_failed",
                    name=self.config.name,
                    attempt=attempt,
                    error=str(e),
                )
                if attempt < self.config.retry_count:
                    await asyncio.sleep(self.config.retry_interval)

        raise ConnectionError(
            f"SOAP request failed after {self.config.retry_count} attempts: {last_error}"
        )

    async def send_and_parse(self, message: str) -> Optional[ET.Element]:
        """Enviar y parsear respuesta XML."""
        response = await self.send(message)
        if response:
            return ET.fromstring(response)
        return None


class SOAPError(Exception):
    """Error en comunicación SOAP."""
    pass


def _extract_soap_fault(body: str) -> Optional[str]:
    """Extraer fault string de una respuesta SOAP."""
    try:
        root = ET.fromstring(body)
        # Search for faultstring in any namespace
        for elem in root.iter():
            if "faultstring" in elem.tag.lower():
                return elem.text
    except ET.ParseError:
        pass
    return None


def build_soap_body(namespace: str, method: str, params: dict) -> str:
    """Helper para construir un SOAP body desde parámetros."""
    param_xml = "\n".join(
        f"    <{k}>{v}</{k}>" for k, v in params.items()
    )
    return f"""<ns:{method} xmlns:ns="{namespace}">
{param_xml}
</ns:{method}>"""
