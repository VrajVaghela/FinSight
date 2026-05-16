from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.config import get_settings
from backend.retrieval.neural_reranker import is_model_loaded
from backend.retrieval.vector_searcher import COLLECTION_NAME, get_client


def _last_calibration() -> str | None:
    path = Path(".env")
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("GATE2_THRESHOLD="):
            value = line.split("=", 1)[1].strip()
            return None if value in {"", "0", "0.0"} else "configured"
    return None


def get_retrieval_health() -> dict[str, Any]:
    settings = get_settings()
    health: dict[str, Any] = {
        "qdrant": "unknown",
        "bm25": "unknown",
        "reranker": "unknown",
        "chunks": 0,
        "model_loaded": is_model_loaded(),
        "last_calibration": _last_calibration(),
    }

    try:
        client = get_client()
        if client.collection_exists(COLLECTION_NAME):
            health["qdrant"] = "ok"
            try:
                count = client.count(collection_name=COLLECTION_NAME, exact=False)
                health["chunks"] = int(getattr(count, "count", 0))
            except Exception as exc:
                health["chunks_error"] = str(exc)
        else:
            health["qdrant"] = f"missing_collection:{COLLECTION_NAME}"
    except Exception as exc:
        health["qdrant"] = str(exc)

    try:
        import redis

        redis_client = redis.Redis(host=settings.redis_host, port=settings.redis_port)
        redis_client.ping()
        health["bm25"] = "ok" if redis_client.keys("bm25:*") else "warning:no_bm25_indexes"
    except Exception as exc:
        health["bm25"] = str(exc)

    try:
        health["reranker"] = "ok" if is_model_loaded() else "not_loaded"
        health["model_loaded"] = is_model_loaded()
    except Exception as exc:
        health["reranker"] = str(exc)

    return json.loads(json.dumps(health, default=str))
