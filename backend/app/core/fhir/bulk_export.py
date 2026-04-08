"""
FHIR Bulk Data Export ($export).

Implementa el async pattern de FHIR Bulk Data:
  1. POST /$export → 202 Accepted + Content-Location
  2. GET /export-status/{job_id} → 200 (in-progress) o 200 (complete + URLs)
  3. GET /export-data/{job_id}/{file} → NDJSON output

Soporta:
  - System-level export: GET /fhir/$export
  - Patient-level export: GET /fhir/Patient/$export
  - Type filter: _type=Patient,Encounter
  - Since filter: _since=2026-01-01
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse
import structlog

logger = structlog.get_logger()

router = APIRouter(prefix="/fhir", tags=["fhir-bulk"])


class ExportStatus(str, Enum):
    accepted = "accepted"
    in_progress = "in-progress"
    complete = "complete"
    error = "error"


@dataclass
class ExportJob:
    """Un job de bulk export."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: ExportStatus = ExportStatus.accepted
    created_at: datetime = field(default_factory=datetime.now)
    resource_types: list[str] = field(default_factory=list)
    since: Optional[str] = None
    output_files: dict[str, list[dict]] = field(default_factory=dict)  # type -> [resources]
    error: Optional[str] = None
    request_url: str = ""


# In-memory job store
_jobs: dict[str, ExportJob] = {}
# Reference to FHIR resource store (set by server.py)
_resource_store: Optional[dict] = None


def set_resource_store(store: dict) -> None:
    global _resource_store
    _resource_store = store


@router.get("/$export", status_code=202)
@router.get("/Patient/$export", status_code=202)
async def start_export(
    request: Request,
    _type: Optional[str] = None,
    _since: Optional[str] = None,
):
    """Iniciar bulk export."""
    job = ExportJob(
        resource_types=_type.split(",") if _type else [],
        since=_since,
        request_url=str(request.url),
    )

    # Execute export synchronously for MVP (async with background tasks in production)
    _execute_export(job)

    _jobs[job.id] = job

    return PlainTextResponse(
        content="",
        status_code=202,
        headers={
            "Content-Location": f"/fhir/export-status/{job.id}",
        },
    )


@router.get("/export-status/{job_id}")
async def export_status(job_id: str):
    """Check export job status."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Export job not found")

    if job.status == ExportStatus.error:
        raise HTTPException(500, job.error or "Export failed")

    if job.status != ExportStatus.complete:
        return PlainTextResponse(content="", status_code=202, headers={"X-Progress": job.status.value})

    # Complete — return output manifest
    output = []
    for resource_type, resources in job.output_files.items():
        output.append({
            "type": resource_type,
            "url": f"/fhir/export-data/{job.id}/{resource_type}.ndjson",
            "count": len(resources),
        })

    return {
        "transactionTime": job.created_at.isoformat(),
        "request": job.request_url,
        "requiresAccessToken": False,
        "output": output,
    }


@router.get("/export-data/{job_id}/{filename}")
async def export_data(job_id: str, filename: str):
    """Download export data as NDJSON."""
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Export job not found")

    # Extract resource type from filename (e.g., "Patient.ndjson" -> "Patient")
    resource_type = filename.replace(".ndjson", "")
    resources = job.output_files.get(resource_type, [])

    if not resources:
        raise HTTPException(404, f"No data for {resource_type}")

    # Output as NDJSON (one JSON object per line)
    ndjson = "\n".join(json.dumps(r) for r in resources) + "\n"

    return PlainTextResponse(
        content=ndjson,
        media_type="application/ndjson",
    )


@router.delete("/export-status/{job_id}", status_code=204)
async def cancel_export(job_id: str):
    """Cancel/delete export job."""
    if job_id not in _jobs:
        raise HTTPException(404, "Export job not found")
    del _jobs[job_id]


def _execute_export(job: ExportJob) -> None:
    """Execute the export (sync for MVP)."""
    try:
        if _resource_store is None:
            job.status = ExportStatus.complete
            return

        target_types = job.resource_types or list(_resource_store.keys())

        for resource_type in target_types:
            resources = _resource_store.get(resource_type, {})
            if resources:
                resource_list = list(resources.values())

                # Apply _since filter
                if job.since:
                    # Simple string comparison on lastUpdated (if present)
                    resource_list = [
                        r for r in resource_list
                        if r.get("meta", {}).get("lastUpdated", "9999") >= job.since
                    ]

                if resource_list:
                    job.output_files[resource_type] = resource_list

        job.status = ExportStatus.complete
        logger.info(
            "bulk_export_complete",
            job_id=job.id,
            types=list(job.output_files.keys()),
            total=sum(len(v) for v in job.output_files.values()),
        )

    except Exception as e:
        job.status = ExportStatus.error
        job.error = str(e)
        logger.error("bulk_export_failed", job_id=job.id, error=str(e))
