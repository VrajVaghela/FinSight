# app/dependencies.py
"""
FastAPI dependency injection providers.
Uses get_llm_client() which auto-selects Gemini or OpenAI based on AI_PROVIDER env var.
"""
from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as redis
from typing import AsyncGenerator, Any

from app.models.database import get_db
from app.services.chat_service import ChatService
from app.services.project_service import ProjectService
from app.services.conversation_service import ConversationService
from app.middleware.auth import verify_token
from app.config import settings
from app.core.llm_client import get_llm_client


def get_ai_client() -> Any:
    """Provide a configured LLM client (Gemini or OpenAI, based on AI_PROVIDER)."""
    return get_llm_client()


async def get_redis_client() -> AsyncGenerator[redis.Redis, None]:
    """Provide an async Redis client from the connection pool."""
    client = redis.from_url(settings.redis_url, decode_responses=False)
    try:
        yield client
    finally:
        await client.aclose()


async def get_chat_service(
    db: AsyncSession = Depends(get_db),
    llm_client: Any = Depends(get_ai_client),
    redis_client: redis.Redis = Depends(get_redis_client)
) -> ChatService:
    return ChatService(db, llm_client=llm_client, redis_client=redis_client)


def get_project_service(db: AsyncSession = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


def get_conversation_service(db: AsyncSession = Depends(get_db)) -> ConversationService:
    return ConversationService(db)


from uuid import UUID

async def get_current_user(authorization: str = Header(None)) -> UUID:
    """Decode JWT from Authorization: Bearer <token> header."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid Authorization header format. Use 'Bearer <token>'")
    user_id_str = await verify_token(parts[1])
    try:
        return UUID(user_id_str)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token subject format")


async def verify_ws_token(token: str) -> str | None:
    """Verify JWT for WebSocket connections (passed as query param)."""
    try:
        return await verify_token(token)
    except HTTPException:
        return None
