from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.api.analytics_endpoint import router as analytics_router
from backend.api.dashboard_endpoint import router as dashboard_router
from backend.api.debug_endpoint import router as debug_router
from backend.api.health_endpoint import router as health_router
from backend.api.scope_debug_endpoint import router as scope_router
from backend.retrieval import startup


@asynccontextmanager
async def lifespan(app: FastAPI):
    await startup()
    yield


app = FastAPI(title="FinSight AI Backend", lifespan=lifespan)
app.include_router(health_router)
app.include_router(debug_router)
app.include_router(analytics_router)
app.include_router(dashboard_router)
app.include_router(scope_router)
