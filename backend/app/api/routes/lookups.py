"""Endpoints para lookup tables."""

import uuid

from fastapi import APIRouter, HTTPException, Request

from ..schemas import (
    LookupTableCreate,
    LookupTableResponse,
    LookupEntryCreate,
    LookupEntryResponse,
)

router = APIRouter(prefix="/lookups", tags=["lookups"])

# In-memory store until DB integration
_tables: dict[str, dict] = {}
_entries: dict[str, dict[str, dict]] = {}  # table_id -> {key -> entry}


@router.get("", response_model=list[LookupTableResponse])
async def list_tables():
    return list(_tables.values())


@router.post("", response_model=LookupTableResponse, status_code=201)
async def create_table(body: LookupTableCreate):
    table_id = uuid.uuid4()
    table = LookupTableResponse(
        id=table_id,
        tenant_id=body.tenant_id,
        name=body.name,
        description=body.description,
        is_active=True,
    )
    _tables[str(table_id)] = table.model_dump()
    _entries[str(table_id)] = {}
    return table


@router.get("/{table_id}/entries", response_model=list[LookupEntryResponse])
async def list_entries(table_id: uuid.UUID):
    if str(table_id) not in _tables:
        raise HTTPException(404, "Lookup table not found")
    entries = _entries.get(str(table_id), {})
    return list(entries.values())


@router.post("/{table_id}/entries", response_model=LookupEntryResponse, status_code=201)
async def create_entry(table_id: uuid.UUID, body: LookupEntryCreate):
    if str(table_id) not in _tables:
        raise HTTPException(404, "Lookup table not found")
    entry_id = uuid.uuid4()
    entry = LookupEntryResponse(
        id=entry_id,
        key=body.key,
        value=body.value,
        is_active=True,
    )
    _entries.setdefault(str(table_id), {})[body.key] = entry.model_dump()
    return entry


@router.delete("/{table_id}", status_code=204)
async def delete_table(table_id: uuid.UUID):
    if str(table_id) not in _tables:
        raise HTTPException(404, "Lookup table not found")
    del _tables[str(table_id)]
    _entries.pop(str(table_id), None)
