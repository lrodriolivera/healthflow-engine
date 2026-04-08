"""CRUD endpoints para flows — conectado a PostgreSQL."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas import FlowCreate, FlowUpdate, FlowResponse
from ...db import get_db
from ...models.flow import Flow, Adapter, AdapterType

router = APIRouter(prefix="/flows", tags=["flows"])


@router.get("", response_model=list[FlowResponse])
async def list_flows(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Flow).order_by(Flow.created_at.desc()))
    flows = result.scalars().all()
    return [
        FlowResponse(
            id=f.id, tenant_id=f.tenant_id, name=f.name,
            description=f.description, is_active=f.is_active,
            config=f.config, created_at=f.created_at, updated_at=f.updated_at,
        )
        for f in flows
    ]


@router.post("", response_model=FlowResponse, status_code=201)
async def create_flow(body: FlowCreate, db: AsyncSession = Depends(get_db)):
    flow = Flow(
        id=uuid.uuid4(),
        tenant_id=body.tenant_id,
        name=body.name,
        description=body.description,
        config=body.config,
    )
    db.add(flow)
    await db.flush()
    return FlowResponse(
        id=flow.id, tenant_id=flow.tenant_id, name=flow.name,
        description=flow.description, is_active=flow.is_active,
        config=flow.config, created_at=flow.created_at, updated_at=flow.updated_at,
    )


@router.get("/{flow_id}", response_model=FlowResponse)
async def get_flow(flow_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    flow = await db.get(Flow, flow_id)
    if not flow:
        raise HTTPException(404, "Flow not found")
    return FlowResponse(
        id=flow.id, tenant_id=flow.tenant_id, name=flow.name,
        description=flow.description, is_active=flow.is_active,
        config=flow.config, created_at=flow.created_at, updated_at=flow.updated_at,
    )


@router.put("/{flow_id}", response_model=FlowResponse)
async def update_flow(flow_id: uuid.UUID, body: FlowUpdate, db: AsyncSession = Depends(get_db)):
    flow = await db.get(Flow, flow_id)
    if not flow:
        raise HTTPException(404, "Flow not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(flow, key, value)
    await db.flush()
    return FlowResponse(
        id=flow.id, tenant_id=flow.tenant_id, name=flow.name,
        description=flow.description, is_active=flow.is_active,
        config=flow.config, created_at=flow.created_at, updated_at=flow.updated_at,
    )


@router.delete("/{flow_id}", status_code=204)
async def delete_flow(flow_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    flow = await db.get(Flow, flow_id)
    if not flow:
        raise HTTPException(404, "Flow not found")
    await db.delete(flow)


# --- Adapters sub-resource ---

@router.get("/{flow_id}/adapters")
async def list_adapters(flow_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Adapter).where(Adapter.flow_id == flow_id))
    adapters = result.scalars().all()
    return [
        {
            "id": str(a.id), "flow_id": str(a.flow_id), "name": a.name,
            "adapter_type": a.adapter_type.value, "is_active": a.is_active,
            "config": a.config, "port": a.port, "host": a.host,
        }
        for a in adapters
    ]


@router.post("/{flow_id}/adapters", status_code=201)
async def create_adapter(flow_id: uuid.UUID, body: dict, db: AsyncSession = Depends(get_db)):
    flow = await db.get(Flow, flow_id)
    if not flow:
        raise HTTPException(404, "Flow not found")
    adapter = Adapter(
        id=uuid.uuid4(),
        flow_id=flow_id,
        name=body["name"],
        adapter_type=AdapterType(body["adapter_type"]),
        config=body.get("config"),
        port=body.get("port"),
        host=body.get("host"),
    )
    db.add(adapter)
    await db.flush()
    return {"id": str(adapter.id), "name": adapter.name, "status": "created"}
