from __future__ import annotations

from fastapi import APIRouter

from backend.api.health import get_retrieval_health


router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health() -> dict:
    retrieval = get_retrieval_health()
    ok = (
        retrieval["qdrant"] == "ok"
        and retrieval["bm25"] == "ok"
        and retrieval["reranker"] == "ok"
    )
    return {"ok": ok, "retrieval": retrieval}
