"""Health check endpoint con status de servicios."""

from fastapi import APIRouter, Request

from ..schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(request: Request):
    app = request.app
    agents = []
    if hasattr(app.state, "agent_manager") and app.state.agent_manager:
        agents = app.state.agent_manager.available_agents

    return HealthResponse(
        status="ok",
        version=getattr(app.state, "settings", None) and app.state.settings.app_version or "0.1.0",
        nats=bool(getattr(app.state, "nats_client", None) and app.state.nats_client.is_connected),
        redis=bool(getattr(app.state, "redis_client", None) and app.state.redis_client.is_connected),
        database=getattr(app.state, "db_engine", None) is not None,
        agents=agents,
    )
