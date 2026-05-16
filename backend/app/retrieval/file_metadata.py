from __future__ import annotations

import json
from typing import Any

from app.config import get_settings


class FileMetadataCache:
    def __init__(self, redis_client: Any | None = None) -> None:
        self.redis = redis_client

    async def _redis(self) -> Any:
        if self.redis is None:
            import redis.asyncio as aioredis

            settings = get_settings()
            self.redis = aioredis.Redis(host=settings.redis_host, port=settings.redis_port)
        return self.redis

    async def get_file_metadata(self, file_id: str) -> dict[str, Any]:
        raw = await (await self._redis()).get(f"file_meta:{file_id}")
        if not raw:
            return {}
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    async def get_file_period(self, file_id: str) -> str:
        return str((await self.get_file_metadata(file_id)).get("period", ""))

    async def get_file_name(self, file_id: str) -> str:
        return str((await self.get_file_metadata(file_id)).get("file_name", ""))

    async def set_file_metadata(self, file_id: str, metadata: dict[str, Any], ttl_seconds: int = 3600) -> None:
        await (await self._redis()).setex(f"file_meta:{file_id}", ttl_seconds, json.dumps(metadata))
