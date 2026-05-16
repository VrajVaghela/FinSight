from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query

from backend.retrieval.analytics_exporter import AnalyticsExporter

try:
    from backend.auth import get_current_user
except Exception:
    async def get_current_user() -> dict[str, str]:
        return {"id": "analytics-local"}


router = APIRouter(prefix="/api/retrieval/analytics", tags=["retrieval-analytics"])


@router.get("/summary")
async def analytics_summary(
    project_id: str | None = Query(None),
    days: int = Query(7),
    user=Depends(get_current_user),
) -> dict:
    today = datetime.now(UTC).date().isoformat()
    return AnalyticsExporter().export_daily_summary(today, project_id)


@router.get("/quality")
async def analytics_quality(
    project_id: str,
    days: int = Query(7),
    user=Depends(get_current_user),
) -> dict:
    return AnalyticsExporter().export_retrieval_quality(project_id, days)


@router.get("/dashboard")
async def analytics_dashboard(
    project_id: str | None = Query(None),
    user=Depends(get_current_user),
) -> dict:
    return AnalyticsExporter().export_for_dashboard(project_id)
