# app/main.py
"""
FastAPI application entrypoint.
Blueprint reference: implementation_plan_part1.md §1 — main.py
"""
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api import health, projects, files, chat, voice, evaluate, auth
from app.models.database import init_db
from app.config import settings
from app.core.logging import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and graceful shutdown lifecycle."""
    logger.info({"message": "FinSight AI starting up", "version": settings.app_version})
    await init_db()
    logger.info({"message": "Database initialized successfully"})
    yield
    logger.info({"message": "FinSight AI shutting down"})


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Production-grade Financial Document RAG System",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(health.router, prefix="/api", tags=["Health"])
app.include_router(projects.router, prefix="/api", tags=["Projects"])
app.include_router(files.router, prefix="/api", tags=["Files"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(evaluate.router, prefix="/api", tags=["Evaluate"])
app.include_router(voice.router, tags=["Voice"])


@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "FinSight AI API is running",
        "version": settings.app_version,
        "docs": "/docs"
    }
