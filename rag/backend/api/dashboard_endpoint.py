from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect

from backend.retrieval.dashboard_data import DashboardData

try:
    from backend.auth import get_current_user
except Exception:
    async def get_current_user() -> dict[str, str]:
        return {"id": "dashboard-local"}


router = APIRouter(tags=["retrieval-metrics"])


@router.get("/api/retrieval/metrics/live")
async def live_metrics(user=Depends(get_current_user)) -> dict:
    return DashboardData().get_live_metrics()


@router.get("/api/retrieval/metrics/historical")
async def historical_metrics(hours: int = Query(24), user=Depends(get_current_user)) -> list[dict]:
    return DashboardData().get_historical_metrics(hours)


@router.websocket("/ws/retrieval/metrics")
async def retrieval_metrics_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    project_id = None
    try:
        while True:
            try:
                message = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
                if message.get("type") == "subscribe":
                    project_id = message.get("project_id")
            except asyncio.TimeoutError:
                pass
            await websocket.send_json(
                {
                    "type": "metrics",
                    "project_id": project_id,
                    "data": DashboardData().get_live_metrics(),
                }
            )
    except WebSocketDisconnect:
        return
