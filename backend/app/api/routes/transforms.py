"""Endpoints para transformaciones — CRUD + AI design + test."""

from fastapi import APIRouter, HTTPException, Request

from ..schemas import (
    TransformCreate,
    TransformDesignRequest,
    TransformDesignResponse,
    TransformTestRequest,
    TransformResponse,
)
from ...core.hl7.parser import HL7Message
from ...core.transform.sandbox import CompilationError

router = APIRouter(prefix="/transforms", tags=["transforms"])


@router.get("", response_model=list[dict])
async def list_transforms(request: Request):
    """Listar transforms registradas en memoria."""
    registry = getattr(request.app.state, "transform_registry", None)
    if not registry:
        return []
    return [
        {"name": name, "version": registry.get(name).version}
        for name in registry.list_names()
    ]


@router.post("", status_code=201)
async def create_transform(body: TransformCreate, request: Request):
    """Registrar transform manualmente."""
    registry = getattr(request.app.state, "transform_registry", None)
    if not registry:
        raise HTTPException(503, "Transform registry not available")

    try:
        ct = registry.register(body.name, body.source_code)
    except CompilationError as e:
        raise HTTPException(400, f"Compilation error: {e}")

    return {"status": "created", "name": ct.name, "version": ct.version}


@router.post("/design", response_model=TransformDesignResponse)
async def design_transform(body: TransformDesignRequest, request: Request):
    """Generar transform via TransformDesigner agent (Claude Opus)."""
    agent_manager = getattr(request.app.state, "agent_manager", None)
    if not agent_manager or not agent_manager.transform_designer:
        raise HTTPException(503, "TransformDesigner agent not available — check AWS credentials")

    result = await agent_manager.transform_designer.design_transform(
        spec=body.spec,
        sample_messages=body.sample_messages,
    )

    return TransformDesignResponse(**result)


@router.post("/{transform_name}/test")
async def test_transform(transform_name: str, body: TransformTestRequest, request: Request):
    """Testear una transform registrada contra un mensaje HL7."""
    registry = getattr(request.app.state, "transform_registry", None)
    if not registry:
        raise HTTPException(503, "Transform registry not available")

    ct = registry.get(transform_name)
    if not ct:
        raise HTTPException(404, f"Transform not found: {transform_name}")

    try:
        msg = HL7Message.parse(body.message)
    except Exception as e:
        raise HTTPException(400, f"Invalid HL7 message: {e}")

    try:
        result = ct.execute(msg)
        return {
            "status": "success",
            "input_type": msg.message_type,
            "output_type": result.message_type,
            "output_segments": len(result.segments),
            "output_er7": result.to_er7(),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.delete("/{transform_name}")
async def delete_transform(transform_name: str, request: Request):
    """Desregistrar transform."""
    registry = getattr(request.app.state, "transform_registry", None)
    if not registry:
        raise HTTPException(503, "Transform registry not available")
    if not registry.unregister(transform_name):
        raise HTTPException(404, f"Transform not found: {transform_name}")
    return {"status": "deleted", "name": transform_name}
