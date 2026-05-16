# app/core/prompt_cache.py
import hashlib
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.orm import CacheEntry

class ProviderPromptCache:
    """Local prompt-prefix cache for reused project context.

    Caches the project system prompt + core document context as a prefix.
    Provider-specific APIs may or may not support remote prompt caching; this
    local cache only tracks repeated prefixes and cache-hit metadata.
    """

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    def compute_prefix_hash(self, system_prompt: str, core_context: str) -> str:
        content = f"{system_prompt}||{core_context}"
        return hashlib.sha256(content.encode()).hexdigest()

    async def get_or_create_cache(self, project_id: str, system_prompt: str, core_context: str) -> dict:
        prefix_hash = self.compute_prefix_hash(system_prompt, core_context)

        stmt = select(CacheEntry).where(CacheEntry.prefix_hash == prefix_hash)
        result = await self.db.execute(stmt)
        entry = result.scalar_one_or_none()

        if entry and entry.expiry > datetime.utcnow():
            entry.hit_count += 1
            entry.expiry = datetime.utcnow() + timedelta(minutes=5)  # Extend TTL
            await self.db.commit()
            return {"cached": True, "cache_control": {"type": "ephemeral"}}

        # Create new cache entry if not found or expired
        if entry:
            entry.expiry = datetime.utcnow() + timedelta(minutes=5)
            entry.hit_count = 0
            entry.cached_at = datetime.utcnow()
        else:
            new_entry = CacheEntry(
                prefix_hash=prefix_hash,
                project_id=project_id,
                expiry=datetime.utcnow() + timedelta(minutes=5)
            )
            self.db.add(new_entry)
        
        await self.db.commit()
        return {"cached": False, "cache_control": {"type": "ephemeral"}}

    def build_cached_messages(self, system_prompt: str, core_context: str, cache_info: dict) -> list[dict]:
        """Build a provider-neutral cached-message marker structure."""
        return [
            {
                "role": "system",
                "content": [
                    {"type": "text", "text": system_prompt},
                    {"type": "text", "text": f"Context:\n{core_context}", "cache_control": cache_info["cache_control"]}
                ]
            }
        ]
