from __future__ import annotations

import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.embedding_client import embed_query
from backend.retrieval import last_debug_trace, query_pipeline
from backend.shared.types import RefusalEvent

try:
    from backend.auth import get_current_user
except Exception:
    async def get_current_user() -> dict[str, str]:
        return {"id": "debug-local"}


router = APIRouter(prefix="/api/retrieval", tags=["retrieval"])
debug_router = router
_last_debug: dict[str, dict[str, Any]] = {}


def store_debug(session_id: str, debug: dict[str, Any]) -> None:
    _last_debug[session_id] = {**debug, "stored_at": time.time()}


@router.get("/debug")
async def retrieval_debug(
    project_id: Annotated[str | None, Query()] = None,
    query: Annotated[str | None, Query()] = None,
    session_id: Annotated[str | None, Query()] = None,
    user_id: Annotated[str, Query()] = "default",
    user=Depends(get_current_user),
) -> dict:
    if query:
        if not project_id:
            raise HTTPException(status_code=422, detail="project_id is required with query")

        result = await query_pipeline(query, await embed_query(query), project_id, user_id=user_id)
        if isinstance(result, RefusalEvent):
            return {"refusal": result.dict(), "debug": result.debug}
        return {
            "query": query,
            "project_id": project_id,
            **result.debug,
            "latency_ms": result.retrieval_ms,
            "gate1_score": result.gate1_score,
            "gate2_score": result.gate2_score,
        }

    if session_id and session_id in _last_debug:
        return _last_debug[session_id]

    trace = last_debug_trace.get(user_id)
    if trace is not None:
        return trace

    raise HTTPException(status_code=404, detail="No retrieval debug trace available")
