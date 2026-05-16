# app/core/memory_manager.py
import os
from typing import Any

from app.config import settings
from app.core.llm_client import create_chat_completion
from redis.asyncio import Redis

class QueryRewriter:
    """Condenses chat history + new question into standalone query."""

    REWRITE_PROMPT = """Given the conversation history and a follow-up question,
rewrite the follow-up as a standalone search query that contains all necessary
context. Do NOT answer the question — only rewrite it.

Also determine if the query is asking for a comparison across different time periods or documents (e.g., "last year", "compare Q1 and Q2").

Output ONLY a JSON object with this format:
{{"query": "the standalone query", "cross_document": true or false}}

Chat History:
{history}

Follow-up Question: {question}

JSON Output:"""

    def __init__(self, llm_client: Any, model: str = None):
        self.client = llm_client
        # Fix: The test expects this to fall back to os.getenv so we can mock it
        # If it's passed as an arg, it uses that. If not, check env, else settings
        self.model = model or os.getenv("UTILITY_MODEL", settings.utility_model)

    async def rewrite(self, chat_history: list[dict], new_message: str) -> str:
        if not chat_history:
            return new_message

        # Format last 6 messages
        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in chat_history[-6:]
        )
        prompt = self.REWRITE_PROMPT.format(
            history=history_text, question=new_message
        )
        
        response = await create_chat_completion(
            self.client,
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=200,
            response_format={"type": "json_object"}
        )
        import json
        try:
            result = json.loads(response.choices[0].message.content.strip())
            return result
        except Exception:
            return {"query": new_message, "cross_document": False}

class SessionScopeManager:
    """Manages the active section IDs for hierarchical retrieval per conversation."""
    def __init__(self, redis: Redis = None):
        self.redis = redis
        self.ttl = 3600

    def _key(self, conversation_id: str) -> str:
        return f"session_scope:{conversation_id}"

    async def get_scope(self, conversation_id: str) -> list:
        if not self.redis:
            return []
        data = await self.redis.get(self._key(conversation_id))
        import json
        return json.loads(data) if data else []

    async def update_scope(self, conversation_id: str, section_ids: list):
        if not self.redis or not section_ids:
            return
        import json
        await self.redis.setex(self._key(conversation_id), self.ttl, json.dumps(section_ids))

    async def clear_scope(self, conversation_id: str):
        if self.redis:
            await self.redis.delete(self._key(conversation_id))
class ProjectMemory:
    """Manages project-level context: system prompt + preferences."""

    def __init__(self, db_session):
        self.db = db_session

    async def get_system_prompt(self, project_id: str) -> str:
        from app.models.orm import Project
        from uuid import UUID
        project = await self.db.get(Project, UUID(project_id))
        return project.system_prompt if project else ""

    def build_system_message(self, system_prompt: str, mem1_state: str = "") -> str:
        parts = []
        parts.append("You are a strict conversational assistant grounded ONLY in the provided context.")
        parts.append("CRITICAL: Only answer from the provided document context.")
        parts.append("If the answer cannot be deduced from the context, reply EXACTLY with: 'Not found in the document.'")
        parts.append("When providing an answer, YOU MUST include citations in the format [pX:cY] at the end of relevant sentences. Example: Revenue grew 23% [p13:c2].")
        if system_prompt:
            parts.append(f"\nProject Instructions:\n{system_prompt}")
        if mem1_state:
            parts.append(f"\nSession State:\n{mem1_state}")
        return "\n".join(parts)


class MEM1Adapter:
    """Compact dynamic state management for long multi-turn sessions.

    Based on MEM1 (NeurIPS 2025): instead of passing full chat history,
    maintain a compact state summary that captures key information
    from the conversation. Updated after each turn via LLM.
    """

    STATE_UPDATE_PROMPT = """You maintain a compact session state for a financial AI.
Current state: {current_state}
Latest exchange - User: {user_msg} | Assistant: {assistant_msg}

Update the state to include any new key facts, entities, or context needed
for future questions. Keep it under 200 tokens. Output ONLY the updated state."""

    # Note: redis is made optional here so the mock tests pass
    def __init__(self, llm_client: Any, redis: Redis = None, model: str = None):
        self.redis = redis
        self.client = llm_client
        self.model = model or os.getenv("UTILITY_MODEL", settings.utility_model)
        self.ttl = 3600  # 1 hour session TTL

    def _key(self, conversation_id: str) -> str:
        return f"mem1:{conversation_id}"

    async def get_state(self, conversation_id: str) -> str:
        if not self.redis:
            return ""
        state = await self.redis.get(self._key(conversation_id))
        return state.decode() if state else ""

    async def update_state(
        self, conversation_id: str,
        user_msg: str, assistant_msg: str
    ):
        current = await self.get_state(conversation_id)
        prompt = self.STATE_UPDATE_PROMPT.format(
            current_state=current or "(empty)",
            user_msg=user_msg,
            assistant_msg=assistant_msg[:500]  # Truncate long responses
        )
        response = await create_chat_completion(
            self.client,
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=250
        )
        new_state = response.choices[0].message.content.strip()
        
        if self.redis:
            await self.redis.setex(
                self._key(conversation_id), self.ttl, new_state
            )
            
        return new_state
