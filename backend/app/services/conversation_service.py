# app/services/conversation_service.py
"""
CRUD operations for Conversations and Messages.
Owned by Member 3 (Backend Lead).
Blueprint reference: implementation_plan_part1.md §1 services/conversation_service.py
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from typing import List, Optional

from app.models.orm import Conversation, Message
from fastapi import HTTPException


class ConversationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, project_id: UUID, user_id: UUID, title: str = "New Conversation") -> Conversation:
        """Create a new conversation in a project."""
        conversation = Conversation(
            project_id=project_id,
            user_id=user_id,
            title=title
        )
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation

    async def get_by_id(self, conversation_id: UUID, user_id: UUID) -> Conversation:
        """Fetch a conversation or raise 404. Validates user ownership."""
        stmt = (
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .options(selectinload(Conversation.messages))
        )
        result = await self.db.execute(stmt)
        conv = result.scalar_one_or_none()
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        if conv.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to access this conversation")
        return conv

    async def list_by_project(self, project_id: UUID, user_id: UUID) -> List[Conversation]:
        """List all conversations for a project, filtered to the current user."""
        stmt = (
            select(Conversation)
            .where(
                Conversation.project_id == project_id,
                Conversation.user_id == user_id
            )
            .order_by(Conversation.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def update_title(self, conversation_id: UUID, user_id: UUID, title: str) -> Conversation:
        """Update conversation title (e.g., auto-title from first message)."""
        conv = await self.get_by_id(conversation_id, user_id)
        conv.title = title
        await self.db.commit()
        await self.db.refresh(conv)
        return conv

    async def delete(self, conversation_id: UUID, user_id: UUID) -> None:
        """Delete a conversation and its messages."""
        conv = await self.get_by_id(conversation_id, user_id)
        await self.db.delete(conv)
        await self.db.commit()

    async def get_recent_messages(self, conversation_id: UUID, limit: int = 6) -> List[dict]:
        """
        Fetch the N most recent messages for QueryRewriter context.
        Returns chronological order (oldest first).
        """
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        messages = result.scalars().all()
        return [{"role": m.role, "content": m.content} for m in reversed(messages)]

    async def persist_exchange(
        self,
        conversation_id: UUID,
        user_content: str,
        assistant_content: str,
        citations: list = None,
        retrieved_chunks: list = None,
        pal_execution: Optional[dict] = None,
        ui_components: list = None,
        refusal_info: Optional[dict] = None,
        token_usage: Optional[dict] = None,
        latency_ms: Optional[int] = None
    ) -> tuple[Message, Message]:
        """Persist a full user+assistant exchange in a single transaction."""
        user_msg = Message(
            conversation_id=conversation_id,
            role="user",
            content=user_content
        )
        asst_msg = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=assistant_content,
            citations=citations or [],
            retrieved_chunks=retrieved_chunks or [],
            pal_execution=pal_execution,
            ui_components=ui_components or [],
            refusal_info=refusal_info,
            token_usage=token_usage,
            latency_ms=latency_ms
        )
        self.db.add_all([user_msg, asst_msg])
        await self.db.commit()
        return user_msg, asst_msg
