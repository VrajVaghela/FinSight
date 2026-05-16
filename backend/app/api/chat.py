# app/api/chat.py
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from app.models.schemas import ChatRequest
from app.models.orm import Conversation, Message
from app.models.database import get_db
from app.services.chat_service import ChatService
from app.dependencies import get_chat_service, get_current_user

router = APIRouter()


@router.post("/chat")
async def chat_endpoint(
    req: ChatRequest,
    user_id: UUID = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service)
):
    async def event_generator():
        async for event in service.process_chat(
            project_id=req.project_id,
            conversation_id=req.conversation_id,
            message=req.message,
            user_id=user_id,
            language=req.language,
            voice=req.voice,
            debug=req.debug
        ):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/chat/conversations")
async def list_conversations(
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.created_at.desc())
    )
    result = await db.execute(stmt)
    conversations = result.scalars().all()

    return [
        {
            "id": str(c.id),
            "project_id": str(c.project_id),
            "title": c.title,
            "created_at": c.created_at.isoformat(),
        }
        for c in conversations
    ]


@router.get("/chat/history/{conversation_id}")
async def get_conversation_history(
    conversation_id: UUID,
    user_id: UUID = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify ownership
    conv = await db.get(Conversation, conversation_id)
    if not conv or conv.user_id != user_id:
        raise HTTPException(status_code=404, detail="Conversation not found")

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()

    return [
        {
            "id": str(m.id),
            "role": m.role,
            "content": m.content,
            "citations": m.citations or [],
            "ui_components": m.ui_components or [],
            "created_at": m.created_at.isoformat(),
        }
        for m in messages
    ]
