from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.retrieval.session_scoper import SessionScoper

try:
    from backend.auth import get_current_user
except Exception:
    async def get_current_user() -> dict[str, str]:
        return {"id": "scope-local"}


router = APIRouter(prefix="/api/retrieval", tags=["retrieval-scope"])


@router.get("/scope")
async def retrieval_scope(
    conversation_id: str = Query(...),
    user=Depends(get_current_user),
) -> dict:
    if not conversation_id:
        raise HTTPException(status_code=422, detail="conversation_id is required")
    return await SessionScoper().debug_scope(conversation_id)


@router.post("/scope/clear")
async def clear_retrieval_scope(
    conversation_id: str = Query(...),
    user=Depends(get_current_user),
) -> dict:
    await SessionScoper().clear(conversation_id)
    return {"conversation_id": conversation_id, "cleared": True}
