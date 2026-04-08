"""
LookupService — lookup tables backed by PostgreSQL + Redis cache.

Las transformaciones usan lookup(table, key) para traducir códigos,
mapear valores, etc. Los datos viven en PostgreSQL y se cachean en Redis
para acceso <0.1ms durante runtime.
"""

from __future__ import annotations

from typing import Optional, Callable

import structlog

from ...cache.redis_client import RedisClient

logger = structlog.get_logger()


class LookupService:
    """Servicio de lookup tables con cache Redis."""

    def __init__(self, redis_client: Optional[RedisClient] = None):
        self._redis = redis_client

    def create_lookup_fn(self) -> Callable[[str, str], str]:
        """Crear función de lookup sincrónica para usar en transforms.

        Como las transforms se ejecutan sincrónicamente, esta función
        usa un cache local en memoria como fallback si Redis no está disponible.
        """
        local_cache: dict[str, dict[str, str]] = {}

        def lookup(table_name: str, key: str) -> str:
            # Check local cache first
            if table_name in local_cache and key in local_cache[table_name]:
                return local_cache[table_name][key]
            return ""

        return lookup

    async def preload_table(self, table_name: str, entries: dict[str, str]) -> None:
        """Pre-cargar tabla en Redis desde DB."""
        if self._redis and self._redis.is_connected:
            await self._redis.load_lookup_table(table_name, entries)
            logger.info("lookup_table_preloaded", table=table_name, count=len(entries))

    async def get(self, table_name: str, key: str) -> str:
        """Obtener valor async (para uso fuera de transforms)."""
        if self._redis and self._redis.is_connected:
            result = await self._redis.get_lookup(table_name, key)
            return result or ""
        return ""

    async def set(self, table_name: str, key: str, value: str) -> None:
        """Setear valor async."""
        if self._redis and self._redis.is_connected:
            await self._redis.set_lookup(table_name, key, value)

    async def load_all_tables(self, tables: dict[str, dict[str, str]]) -> None:
        """Cargar múltiples tablas de una vez."""
        for table_name, entries in tables.items():
            await self.preload_table(table_name, entries)
