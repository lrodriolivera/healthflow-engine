"""
Multi-tenancy middleware.

Extrae el tenant_id del header X-Tenant-ID o del path y lo inyecta
en request.state.tenant_id para uso en routes y queries.

Paths excluidos: /health, /docs, /openapi.json, /fhir
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

import structlog

logger = structlog.get_logger()

EXCLUDED_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}
EXCLUDED_PREFIXES = ("/fhir",)


class TenantMiddleware(BaseHTTPMiddleware):
    """Middleware que extrae y valida tenant_id."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip tenant check for excluded paths
        if path in EXCLUDED_PATHS or any(path.startswith(p) for p in EXCLUDED_PREFIXES):
            request.state.tenant_id = None
            return await call_next(request)

        # Extract tenant from header
        tenant_id = request.headers.get("X-Tenant-ID")

        # For now, tenant is optional — when multi-tenancy is fully enabled,
        # make it required for /api/v1/* paths
        request.state.tenant_id = tenant_id

        if tenant_id:
            logger.debug("tenant_resolved", tenant_id=tenant_id, path=path)

        response = await call_next(request)
        return response
