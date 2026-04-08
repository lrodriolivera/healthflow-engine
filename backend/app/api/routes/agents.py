"""Endpoints para agentes AI — ChatOps, heal, status."""

from fastapi import APIRouter, HTTPException, Request

from ..schemas import ChatRequest, ChatResponse, HealRequest, HealResponse

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/status")
async def agent_status(request: Request):
    """Estado de los agentes."""
    manager = getattr(request.app.state, "agent_manager", None)
    if not manager:
        return {"agents": [], "bedrock": False}
    return {
        "agents": manager.available_agents,
        "bedrock": manager.has_bedrock,
        "anomaly_stats": manager.anomaly_detector.get_stats(),
    }


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request):
    """ChatOps — interactuar con el OpsAgent en lenguaje natural."""
    manager = getattr(request.app.state, "agent_manager", None)
    if not manager or not manager.ops_agent:
        raise HTTPException(503, "OpsAgent not available — check AWS credentials")

    response = await manager.ops_agent.chat(
        user_message=body.message,
        context=body.context,
    )
    return ChatResponse(response=response)


@router.post("/heal", response_model=HealResponse)
async def heal(body: HealRequest, request: Request):
    """Invocar SelfHealer para diagnosticar un error."""
    manager = getattr(request.app.state, "agent_manager", None)
    if not manager or not manager.self_healer:
        raise HTTPException(503, "SelfHealer not available — check AWS credentials")

    # TODO: Load error from DB by error_id
    error = {
        "id": body.error_id,
        "error_type": "unknown",
        "error_detail": "Error details would come from DB",
        "raw_message": "",
        "flow_id": "",
        "retry_count": 0,
    }

    result = await manager.self_healer.diagnose(error)
    return HealResponse(
        diagnosis=result.get("diagnosis", ""),
        severity=result.get("severity", "unknown"),
        category=result.get("category", "unknown"),
        fix=result.get("fix", {}),
    )


@router.get("/anomalies")
async def get_anomalies(request: Request, limit: int = 50):
    """Obtener anomalías recientes del AnomalyDetector."""
    manager = getattr(request.app.state, "agent_manager", None)
    if not manager:
        return {"anomalies": []}

    anomalies = manager.anomaly_detector.get_recent_anomalies(limit)
    return {
        "anomalies": [
            {
                "metric": a.metric,
                "severity": a.severity,
                "deviation": round(a.deviation, 2),
                "description": a.description,
                "timestamp": a.timestamp,
            }
            for a in anomalies
        ]
    }
