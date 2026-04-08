"""CRUD endpoints para flows."""

import uuid

from fastapi import APIRouter, HTTPException, Request

from ..schemas import FlowCreate, FlowUpdate, FlowResponse

router = APIRouter(prefix="/flows", tags=["flows"])

# In-memory store until DB integration (M6 connects to real DB)
_flows: dict[str, dict] = {}


@router.get("", response_model=list[FlowResponse])
async def list_flows():
    return list(_flows.values())


@router.post("", response_model=FlowResponse, status_code=201)
async def create_flow(body: FlowCreate):
    flow_id = uuid.uuid4()
    flow = FlowResponse(
        id=flow_id,
        tenant_id=body.tenant_id,
        name=body.name,
        description=body.description,
        config=body.config,
    )
    _flows[str(flow_id)] = flow.model_dump()
    return flow


@router.get("/{flow_id}", response_model=FlowResponse)
async def get_flow(flow_id: uuid.UUID):
    flow = _flows.get(str(flow_id))
    if not flow:
        raise HTTPException(404, "Flow not found")
    return flow


@router.put("/{flow_id}", response_model=FlowResponse)
async def update_flow(flow_id: uuid.UUID, body: FlowUpdate):
    flow = _flows.get(str(flow_id))
    if not flow:
        raise HTTPException(404, "Flow not found")
    update_data = body.model_dump(exclude_unset=True)
    flow.update(update_data)
    _flows[str(flow_id)] = flow
    return flow


@router.delete("/{flow_id}", status_code=204)
async def delete_flow(flow_id: uuid.UUID):
    if str(flow_id) not in _flows:
        raise HTTPException(404, "Flow not found")
    del _flows[str(flow_id)]
