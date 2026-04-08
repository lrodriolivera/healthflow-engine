"""Endpoints para lookup tables — conectado a PostgreSQL + Redis cache."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas import (
    LookupTableCreate, LookupTableResponse,
    LookupEntryCreate, LookupEntryResponse,
)
from ...db import get_db
from ...models.lookup import LookupTable, LookupEntry

router = APIRouter(prefix="/lookups", tags=["lookups"])


@router.get("", response_model=list[LookupTableResponse])
async def list_tables(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(LookupTable).order_by(LookupTable.name))
    tables = result.scalars().all()
    return [
        LookupTableResponse(
            id=t.id, tenant_id=t.tenant_id, name=t.name,
            description=t.description, is_active=t.is_active,
        )
        for t in tables
    ]


@router.post("", response_model=LookupTableResponse, status_code=201)
async def create_table(body: LookupTableCreate, db: AsyncSession = Depends(get_db)):
    table = LookupTable(
        id=uuid.uuid4(),
        tenant_id=body.tenant_id,
        name=body.name,
        description=body.description,
    )
    db.add(table)
    await db.flush()
    return LookupTableResponse(
        id=table.id, tenant_id=table.tenant_id, name=table.name,
        description=table.description, is_active=table.is_active,
    )


@router.get("/{table_id}/entries", response_model=list[LookupEntryResponse])
async def list_entries(table_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    table = await db.get(LookupTable, table_id)
    if not table:
        raise HTTPException(404, "Lookup table not found")
    result = await db.execute(
        select(LookupEntry).where(LookupEntry.table_id == table_id).order_by(LookupEntry.key)
    )
    entries = result.scalars().all()
    return [
        LookupEntryResponse(id=e.id, key=e.key, value=e.value, is_active=e.is_active)
        for e in entries
    ]


@router.post("/{table_id}/entries", response_model=LookupEntryResponse, status_code=201)
async def create_entry(
    table_id: uuid.UUID, body: LookupEntryCreate,
    request: Request, db: AsyncSession = Depends(get_db),
):
    table = await db.get(LookupTable, table_id)
    if not table:
        raise HTTPException(404, "Lookup table not found")
    entry = LookupEntry(
        id=uuid.uuid4(),
        table_id=table_id,
        key=body.key,
        value=body.value,
    )
    db.add(entry)
    await db.flush()

    # Sync to Redis cache if available
    redis = getattr(request.app.state, "redis_client", None)
    if redis and redis.is_connected:
        await redis.set_lookup(table.name, body.key, body.value)

    return LookupEntryResponse(id=entry.id, key=entry.key, value=entry.value, is_active=entry.is_active)


@router.delete("/{table_id}", status_code=204)
async def delete_table(table_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    table = await db.get(LookupTable, table_id)
    if not table:
        raise HTTPException(404, "Lookup table not found")
    await db.delete(table)
