"""
FHIR R5-style Subscriptions — topic-based pub/sub.

Permite a sistemas externos suscribirse a cambios en recursos FHIR:
  - Un LIS se suscribe a Patient updates (ADT)
  - Un RIS se suscribe a ServiceRequest creates (orders)
  - Un dashboard se suscribe a todos los DiagnosticReport

Implementación:
  - Subscriptions se almacenan en memoria (y opcionalmente DB)
  - Cuando un recurso cambia, se evalúan todas las subscriptions
  - Las notificaciones se envían via webhook (REST callback)
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum

import httpx
import structlog

logger = structlog.get_logger()


class SubscriptionStatus(str, Enum):
    requested = "requested"
    active = "active"
    error = "error"
    off = "off"


class SubscriptionChannelType(str, Enum):
    rest_hook = "rest-hook"
    websocket = "websocket"
    email = "email"


@dataclass
class SubscriptionFilter:
    """Filtro de recursos para la subscription."""
    resource_type: str  # "Patient", "Encounter", etc.
    criteria: Optional[str] = None  # FHIR search-like criteria


@dataclass
class SubscriptionChannel:
    """Canal de notificación."""
    type: SubscriptionChannelType = SubscriptionChannelType.rest_hook
    endpoint: str = ""
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class Subscription:
    """Una subscription FHIR R5."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: SubscriptionStatus = SubscriptionStatus.active
    topic: str = ""  # e.g., "patient-update", "new-order"
    filter: Optional[SubscriptionFilter] = None
    channel: Optional[SubscriptionChannel] = None
    created_at: datetime = field(default_factory=datetime.now)
    error_count: int = 0
    max_errors: int = 10

    def matches(self, resource_type: str, event: str) -> bool:
        """Evaluar si un evento matchea esta subscription."""
        if self.status != SubscriptionStatus.active:
            return False
        if self.filter and self.filter.resource_type != resource_type:
            return False
        if self.topic and self.topic not in ("*", event):
            return False
        return True


class SubscriptionManager:
    """Gestiona subscriptions y envía notificaciones."""

    def __init__(self):
        self._subscriptions: dict[str, Subscription] = {}
        self._http_client: Optional[httpx.AsyncClient] = None

    async def start(self) -> None:
        self._http_client = httpx.AsyncClient(timeout=10.0)
        logger.info("subscription_manager_started")

    async def stop(self) -> None:
        if self._http_client:
            await self._http_client.aclose()

    def add(self, subscription: Subscription) -> Subscription:
        """Registrar una nueva subscription."""
        self._subscriptions[subscription.id] = subscription
        logger.info(
            "subscription_added",
            id=subscription.id,
            topic=subscription.topic,
            resource=subscription.filter.resource_type if subscription.filter else "*",
        )
        return subscription

    def remove(self, subscription_id: str) -> bool:
        if subscription_id in self._subscriptions:
            del self._subscriptions[subscription_id]
            return True
        return False

    def get(self, subscription_id: str) -> Optional[Subscription]:
        return self._subscriptions.get(subscription_id)

    def list_all(self) -> list[Subscription]:
        return list(self._subscriptions.values())

    async def notify(self, resource_type: str, event: str, resource: dict) -> int:
        """Notificar a todas las subscriptions que matchean.

        Args:
            resource_type: "Patient", "Encounter", etc.
            event: "create", "update", "delete"
            resource: FHIR resource dict

        Returns:
            Number of notifications sent.
        """
        matching = [s for s in self._subscriptions.values() if s.matches(resource_type, event)]
        if not matching:
            return 0

        notification = {
            "resourceType": "Bundle",
            "type": "history",
            "timestamp": datetime.now().isoformat(),
            "entry": [{
                "resource": resource,
                "request": {
                    "method": event.upper(),
                    "url": f"{resource_type}/{resource.get('id', '')}",
                },
            }],
        }

        sent = 0
        for sub in matching:
            if sub.channel and sub.channel.type == SubscriptionChannelType.rest_hook:
                success = await self._send_webhook(sub, notification)
                if success:
                    sent += 1

        logger.info(
            "subscriptions_notified",
            resource_type=resource_type,
            event=event,
            matching=len(matching),
            sent=sent,
        )
        return sent

    async def _send_webhook(self, subscription: Subscription, payload: dict) -> bool:
        """Enviar notificación via webhook."""
        if not self._http_client or not subscription.channel:
            return False

        try:
            response = await self._http_client.post(
                subscription.channel.endpoint,
                json=payload,
                headers=subscription.channel.headers,
            )
            if response.status_code >= 400:
                subscription.error_count += 1
                if subscription.error_count >= subscription.max_errors:
                    subscription.status = SubscriptionStatus.error
                    logger.warning("subscription_disabled", id=subscription.id, errors=subscription.error_count)
                return False
            return True
        except Exception as e:
            subscription.error_count += 1
            logger.error("subscription_webhook_failed", id=subscription.id, error=str(e))
            return False
