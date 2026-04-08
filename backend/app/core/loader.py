"""
Startup loader — carga configuración de DB y crea componentes runtime.

Se ejecuta durante el lifespan de FastAPI para:
1. Cargar flows, adapters, routing rules, transforms de PostgreSQL
2. Crear MLLP listeners por cada adapter inbound
3. Registrar MLLP senders por cada adapter outbound
4. Cargar routing rules en el engine en-memoria
5. Compilar y registrar transforms
6. Pre-cargar lookup tables en Redis
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from .routing.engine import RoutingEngine, RoutingRule, RoutingCondition, RoutingDestination
from .transform import TransformRegistry
from ..models.flow import Flow, Adapter, AdapterType
from ..models.routing import RoutingRuleModel
from ..models.transform import Transform
from ..models.lookup import LookupTable, LookupEntry
from ..adapters.mllp import MLLPListener, MLLPListenerConfig, MLLPSender, MLLPSenderConfig
from ..adapters.registry import AdapterRegistry
from ..adapters.handler import create_nats_handler

if TYPE_CHECKING:
    from ..bus.nats_client import NATSClient
    from ..cache.redis_client import RedisClient

logger = structlog.get_logger()


async def load_routing_rules(
    session: AsyncSession, routing_engine: RoutingEngine
) -> int:
    """Cargar routing rules de DB al engine en memoria."""
    result = await session.execute(
        select(RoutingRuleModel).where(RoutingRuleModel.is_active == True)
    )
    rules = result.scalars().all()
    count = 0

    for rule_model in rules:
        try:
            conditions = [
                RoutingCondition(
                    field=c["field"],
                    operator=c["operator"],
                    value=c["value"],
                    case_sensitive=c.get("case_sensitive", True),
                )
                for c in rule_model.conditions
            ]
            destinations = [
                RoutingDestination(
                    name=d["name"],
                    adapter_name=d["adapter_name"],
                    transform=d.get("transform"),
                )
                for d in rule_model.destinations
            ]
            rule = RoutingRule(
                name=rule_model.name,
                conditions=conditions,
                destinations=destinations,
                priority=rule_model.priority,
                stop_on_match=rule_model.stop_on_match,
            )
            routing_engine.add_rule(rule)
            count += 1
        except Exception as e:
            logger.error("load_rule_failed", rule=rule_model.name, error=str(e))

    logger.info("routing_rules_loaded", count=count)
    return count


async def load_transforms(
    session: AsyncSession, transform_registry: TransformRegistry
) -> int:
    """Compilar y registrar transforms de DB."""
    result = await session.execute(
        select(Transform).where(Transform.is_active == True)
    )
    transforms = result.scalars().all()
    count = 0

    for t in transforms:
        try:
            transform_registry.register(t.name, t.source_code, t.version)
            count += 1
        except Exception as e:
            logger.error("load_transform_failed", name=t.name, error=str(e))

    logger.info("transforms_loaded", count=count)
    return count


async def load_lookup_tables(
    session: AsyncSession, redis_client: "RedisClient"
) -> int:
    """Pre-cargar lookup tables de DB a Redis."""
    result = await session.execute(
        select(LookupTable).where(LookupTable.is_active == True)
    )
    tables = result.scalars().all()
    count = 0

    for table in tables:
        entries_result = await session.execute(
            select(LookupEntry).where(
                LookupEntry.table_id == table.id,
                LookupEntry.is_active == True,
            )
        )
        entries = entries_result.scalars().all()
        entries_dict = {e.key: e.value for e in entries}

        if entries_dict:
            await redis_client.load_lookup_table(table.name, entries_dict)
            count += 1

    logger.info("lookup_tables_loaded", count=count)
    return count


async def create_adapters(
    session: AsyncSession,
    adapter_registry: AdapterRegistry,
    nats_client: "NATSClient",
    mllp_listeners: list,
) -> int:
    """Crear adapters inbound/outbound desde config en DB."""
    result = await session.execute(
        select(Adapter).where(Adapter.is_active == True)
    )
    adapters = result.scalars().all()
    count = 0

    for adapter in adapters:
        try:
            if adapter.adapter_type == AdapterType.mllp_in:
                # Create MLLP listener
                config = MLLPListenerConfig(
                    port=adapter.port or 2575,
                    name=adapter.name,
                    host=adapter.host or "0.0.0.0",
                    ack_mode=(adapter.config or {}).get("ack_mode", "immediate"),
                )
                handler = create_nats_handler(nats_client, str(adapter.flow_id))
                listener = MLLPListener(config, handler)
                await listener.start()
                mllp_listeners.append(listener)
                count += 1

            elif adapter.adapter_type == AdapterType.mllp_out:
                # Create MLLP sender
                sender_config = MLLPSenderConfig(
                    host=adapter.host or "localhost",
                    port=adapter.port or 2575,
                    name=adapter.name,
                )
                sender = MLLPSender(sender_config)
                adapter_registry.register(adapter.name, sender)
                count += 1

            # TODO: SOAP, REST, FHIR adapters

        except Exception as e:
            logger.error("create_adapter_failed", name=adapter.name, error=str(e))

    logger.info("adapters_created", count=count)
    return count


async def load_all(
    session: AsyncSession,
    routing_engine: RoutingEngine,
    transform_registry: TransformRegistry,
    adapter_registry: AdapterRegistry,
    nats_client: "NATSClient" = None,
    redis_client: "RedisClient" = None,
    mllp_listeners: list = None,
) -> dict:
    """Cargar toda la configuración de DB."""
    if mllp_listeners is None:
        mllp_listeners = []

    stats = {}
    stats["rules"] = await load_routing_rules(session, routing_engine)
    stats["transforms"] = await load_transforms(session, transform_registry)

    if redis_client and redis_client.is_connected:
        stats["lookups"] = await load_lookup_tables(session, redis_client)

    if nats_client and nats_client.is_connected:
        stats["adapters"] = await create_adapters(
            session, adapter_registry, nats_client, mllp_listeners
        )

    logger.info("config_loaded_from_db", **stats)
    return stats
