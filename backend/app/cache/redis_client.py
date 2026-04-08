"""
Redis client wrapper for lookup tables and caching.

Lookup tables se persisten en PostgreSQL y se cachean en Redis
para acceso <0.1ms durante transformaciones.
"""

from __future__ import annotations

from typing import Optional

import redis.asyncio as aioredis
import structlog

from ..config import Settings

logger = structlog.get_logger()

LOOKUP_PREFIX = "lookup:"


class RedisClient:
    """Wrapper async sobre redis-py."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client: Optional[aioredis.Redis] = None

    @property
    def is_connected(self) -> bool:
        return self._client is not None

    async def connect(self) -> None:
        """Conectar a Redis."""
        self._client = aioredis.from_url(
            self._settings.redis_url,
            db=self._settings.redis_lookup_db,
            decode_responses=True,
        )
        # Verify connection
        await self._client.ping()
        logger.info("redis_connected", url=self._settings.redis_url)

    async def close(self) -> None:
        """Cerrar conexión."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("redis_closed")

    # --- Lookup table operations ---

    def _lookup_key(self, table_name: str, key: str) -> str:
        return f"{LOOKUP_PREFIX}{table_name}:{key}"

    def _table_key(self, table_name: str) -> str:
        return f"{LOOKUP_PREFIX}{table_name}"

    async def get_lookup(self, table_name: str, key: str) -> Optional[str]:
        """Obtener valor de lookup table. <0.1ms."""
        if not self._client:
            raise RuntimeError("Redis not connected")
        return await self._client.hget(self._table_key(table_name), key)

    async def set_lookup(self, table_name: str, key: str, value: str) -> None:
        """Setear un valor en lookup table."""
        if not self._client:
            raise RuntimeError("Redis not connected")
        await self._client.hset(self._table_key(table_name), key, value)

    async def delete_lookup(self, table_name: str, key: str) -> None:
        """Eliminar un valor de lookup table."""
        if not self._client:
            raise RuntimeError("Redis not connected")
        await self._client.hdel(self._table_key(table_name), key)

    async def load_lookup_table(self, table_name: str, entries: dict[str, str]) -> None:
        """Cargar tabla completa desde DB a Redis (bulk load)."""
        if not self._client:
            raise RuntimeError("Redis not connected")

        redis_key = self._table_key(table_name)
        # Clear existing and load new
        pipe = self._client.pipeline()
        pipe.delete(redis_key)
        if entries:
            pipe.hset(redis_key, mapping=entries)
        await pipe.execute()

        logger.info(
            "redis_lookup_loaded",
            table=table_name,
            entries=len(entries),
        )

    async def get_all_lookup_entries(self, table_name: str) -> dict[str, str]:
        """Obtener todos los entries de una tabla."""
        if not self._client:
            raise RuntimeError("Redis not connected")
        return await self._client.hgetall(self._table_key(table_name))

    # --- Generic cache operations ---

    async def get(self, key: str) -> Optional[str]:
        """Get genérico."""
        if not self._client:
            raise RuntimeError("Redis not connected")
        return await self._client.get(key)

    async def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        """Set genérico con TTL opcional (en segundos)."""
        if not self._client:
            raise RuntimeError("Redis not connected")
        if ttl:
            await self._client.setex(key, ttl, value)
        else:
            await self._client.set(key, value)

    async def delete(self, key: str) -> None:
        """Delete genérico."""
        if not self._client:
            raise RuntimeError("Redis not connected")
        await self._client.delete(key)
