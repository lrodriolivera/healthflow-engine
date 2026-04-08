"""
HealthFlow Engine — AI-native healthcare integration engine.

Punto de entrada principal. Levanta:
1. API REST (FastAPI) para management/config
2. MLLP listeners según configuración de DB
3. NATS JetStream pipeline consumers
4. AI agents via AWS Bedrock
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI

from .config import get_settings
from .db import create_engine, create_session_factory
from .bus.nats_client import NATSClient
from .cache.redis_client import RedisClient
from .core.routing.engine import RoutingEngine
from .core.pipeline import MessagePipeline
from .core.transform import TransformRegistry
from .core.loader import load_all
from .adapters.registry import AdapterRegistry
from .agents.manager import AgentManager
from .telemetry import init_telemetry
from .api.routes import health, flows, routing, transforms, messages, agents, lookups
from .core.fhir import fhir_router
from .middleware.tenant import TenantMiddleware

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    logger.info("healthflow_starting", version=settings.app_version)

    # Database
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory

    # NATS JetStream
    nats_client = NATSClient(settings)
    try:
        await nats_client.connect()
    except Exception as e:
        logger.warning("nats_connect_failed", error=str(e))
        nats_client = None
    app.state.nats_client = nats_client

    # Redis
    redis_client = RedisClient(settings)
    try:
        await redis_client.connect()
    except Exception as e:
        logger.warning("redis_connect_failed", error=str(e))
        redis_client = None
    app.state.redis_client = redis_client

    # Core components
    routing_engine = RoutingEngine()
    transform_registry = TransformRegistry()
    adapter_registry = AdapterRegistry()
    mllp_listeners = []

    app.state.routing_engine = routing_engine
    app.state.transform_registry = transform_registry
    app.state.adapter_registry = adapter_registry
    app.state.mllp_listeners = mllp_listeners

    # Load config from DB
    try:
        async with session_factory() as session:
            await load_all(
                session=session,
                routing_engine=routing_engine,
                transform_registry=transform_registry,
                adapter_registry=adapter_registry,
                nats_client=nats_client,
                redis_client=redis_client,
                mllp_listeners=mllp_listeners,
            )
            await session.commit()
    except Exception as e:
        logger.warning("db_load_failed", error=str(e))

    # AI Agents
    agent_manager = AgentManager(settings)
    agent_manager.initialize()
    app.state.agent_manager = agent_manager

    # Pipeline
    pipeline = None
    if nats_client and nats_client.is_connected:
        pipeline = MessagePipeline(
            nats_client=nats_client,
            routing_engine=routing_engine,
            adapter_registry=adapter_registry,
        )
        pipeline.set_transform_registry(transform_registry)
        if agent_manager.ai_router:
            pipeline.set_ai_router(agent_manager.ai_router)
        await pipeline.start()
    app.state.pipeline = pipeline

    # OpenTelemetry
    init_telemetry(settings, app)

    logger.info(
        "healthflow_started",
        agents=agent_manager.available_agents,
        rules=routing_engine.rule_count,
        transforms=transform_registry.count,
        adapters=adapter_registry.count,
        listeners=len(mllp_listeners),
    )
    yield

    # Shutdown
    logger.info("healthflow_stopping")
    for listener in mllp_listeners:
        await listener.stop()
    if nats_client:
        await nats_client.close()
    if redis_client:
        await redis_client.close()
    await adapter_registry.stop_all()
    await engine.dispose()
    logger.info("healthflow_stopped")


app = FastAPI(
    title="HealthFlow Engine",
    description="AI-native healthcare integration engine",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(TenantMiddleware)

# Mount API routes
app.include_router(health.router, tags=["health"])
app.include_router(flows.router, prefix="/api/v1", tags=["flows"])
app.include_router(routing.router, prefix="/api/v1", tags=["routing"])
app.include_router(transforms.router, prefix="/api/v1", tags=["transforms"])
app.include_router(messages.router, prefix="/api/v1", tags=["messages"])
app.include_router(agents.router, prefix="/api/v1", tags=["agents"])
app.include_router(lookups.router, prefix="/api/v1", tags=["lookups"])
app.include_router(fhir_router, tags=["fhir"])
