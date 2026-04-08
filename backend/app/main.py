"""
HealthFlow Engine — AI-native healthcare integration engine.

Punto de entrada principal. Levanta:
1. API REST (FastAPI) para management/config
2. MLLP listeners según configuración
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
from .adapters.registry import AdapterRegistry
from .agents.manager import AgentManager
from .api.routes import health, flows, routing, transforms, messages, agents, lookups

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    logger.info("healthflow_starting", version=settings.app_version, debug=settings.debug)

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

    # Routing Engine
    routing_engine = RoutingEngine()
    app.state.routing_engine = routing_engine

    # Transform Registry
    transform_registry = TransformRegistry()
    app.state.transform_registry = transform_registry

    # Adapter Registry
    adapter_registry = AdapterRegistry()
    app.state.adapter_registry = adapter_registry

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

    # TODO: Load flows/adapters/rules/transforms from DB
    # TODO: Create MLLP listeners with create_nats_handler
    # TODO: Initialize OpenTelemetry (M3)

    logger.info("healthflow_started", agents=agent_manager.available_agents)
    yield

    # Shutdown
    logger.info("healthflow_stopping")
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

# Mount API routes
app.include_router(health.router, tags=["health"])
app.include_router(flows.router, prefix="/api/v1", tags=["flows"])
app.include_router(routing.router, prefix="/api/v1", tags=["routing"])
app.include_router(transforms.router, prefix="/api/v1", tags=["transforms"])
app.include_router(messages.router, prefix="/api/v1", tags=["messages"])
app.include_router(agents.router, prefix="/api/v1", tags=["agents"])
app.include_router(lookups.router, prefix="/api/v1", tags=["lookups"])
