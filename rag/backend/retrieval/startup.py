from __future__ import annotations

import asyncio
import time
from typing import Any

from backend.config import get_settings
from backend.retrieval.neural_reranker import _get_model
from backend.retrieval.vector_searcher import COLLECTION_NAME, create_collection_if_not_exists, get_client


async def startup(max_attempts: int = 12, sleep_seconds: float = 5.0) -> dict[str, Any]:
    settings = get_settings()
    import redis

    started_at = time.time()
    last_error: Exception | None = None
    checks: dict[str, Any] = {}

    for _ in range(max_attempts):
        try:
            client = get_client()
            if settings.create_collection_on_startup:
                create_collection_if_not_exists()
            if not client.collection_exists(COLLECTION_NAME):
                raise RuntimeError(f"Qdrant collection {COLLECTION_NAME!r} is not ready")
            checks["qdrant"] = "ok"

            redis_client = redis.Redis(host=settings.redis_host, port=settings.redis_port)
            redis_client.ping()
            checks["redis"] = "ok"
            bm25_keys = redis_client.keys("bm25:*")
            checks["bm25"] = "ok" if bm25_keys else "warning:no_bm25_indexes"

            _get_model()
            checks["reranker"] = "ok"
            checks["startup_ms"] = int((time.time() - started_at) * 1000)
            print(
                "Retrieval engine ready - "
                f"collection={COLLECTION_NAME} model={settings.reranker_model}"
            )
            return checks
        except Exception as exc:
            last_error = exc
            await asyncio.sleep(sleep_seconds)

    raise RuntimeError("Retrieval dependencies are not ready") from last_error
