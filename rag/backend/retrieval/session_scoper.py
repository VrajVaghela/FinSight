from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from backend.config import get_settings
from backend.shared.types import RetrievedChunk

from .section_router import SectionMatch


class SessionScoper:
    def __init__(self, redis_client: Any | None = None) -> None:
        self.redis = redis_client

    async def _redis(self) -> Any:
        if self.redis is None:
            import redis.asyncio as aioredis

            settings = get_settings()
            self.redis = aioredis.Redis(host=settings.redis_host, port=settings.redis_port)
        return self.redis

    def _key(self, conversation_id: str) -> str:
        return f"session_scope:{conversation_id}"

    def _meta_key(self, conversation_id: str) -> str:
        return f"session_scope_meta:{conversation_id}"

    async def get_active_sections(self, conversation_id: str) -> set[str]:
        values = await (await self._redis()).smembers(self._key(conversation_id))
        return {value.decode("utf-8") if isinstance(value, bytes) else str(value) for value in values}

    async def add_active_section(self, conversation_id: str, section_id: str) -> None:
        if not section_id:
            return
        redis = await self._redis()
        settings = get_settings()
        await redis.sadd(self._key(conversation_id), section_id)
        await redis.expire(self._key(conversation_id), settings.session_scope_ttl_seconds)
        count = await redis.scard(self._key(conversation_id))
        meta = {
            "last_updated": datetime.now(UTC).isoformat(),
            "section_count": int(count),
        }
        await redis.setex(self._meta_key(conversation_id), settings.session_scope_ttl_seconds, json.dumps(meta))

    async def add_active_sections_from_chunks(
        self,
        conversation_id: str,
        chunks: list[RetrievedChunk],
    ) -> None:
        for chunk in chunks[:3]:
            if chunk.section_id:
                await self.add_active_section(conversation_id, chunk.section_id)

    async def score_with_scope_bias(
        self,
        sections: list[SectionMatch],
        conversation_id: str,
        bias_weight: float | None = None,
    ) -> list[SectionMatch]:
        active = await self.get_active_sections(conversation_id)
        if not active:
            return sections
        bias = get_settings().session_scope_bias if bias_weight is None else bias_weight
        for section in sections:
            if section.section_id in active:
                section.rrf_score += bias
        return sorted(sections, key=lambda section: section.rrf_score, reverse=True)

    async def score_chunks_with_scope_bias(
        self,
        chunks: list[RetrievedChunk],
        conversation_id: str,
        bias_weight: float | None = None,
    ) -> list[RetrievedChunk]:
        active = await self.get_active_sections(conversation_id)
        if not active:
            return chunks
        bias = get_settings().session_chunk_scope_bias if bias_weight is None else bias_weight
        for chunk in chunks:
            if chunk.section_id in active:
                chunk.reranker_score += bias
        return sorted(chunks, key=lambda chunk: chunk.reranker_score, reverse=True)

    async def clear(self, conversation_id: str) -> None:
        redis = await self._redis()
        await redis.delete(self._key(conversation_id), self._meta_key(conversation_id))

    async def debug_scope(self, conversation_id: str) -> dict[str, Any]:
        redis = await self._redis()
        active = sorted(await self.get_active_sections(conversation_id))
        raw_meta = await redis.get(self._meta_key(conversation_id))
        meta = json.loads(raw_meta.decode("utf-8") if isinstance(raw_meta, bytes) else raw_meta) if raw_meta else {}
        ttl = await redis.ttl(self._key(conversation_id))
        active_sections = [{"section_id": section_id} for section_id in active]
        try:
            from .section_router import SectionRouter

            router = SectionRouter()
            enriched = []
            for item in active_sections:
                metadata = await router.get_section_metadata(item["section_id"])
                enriched.append(
                    {
                        **item,
                        "section_header": metadata.get("section_header"),
                        "section_level": metadata.get("section_level"),
                        "file_id": metadata.get("file_id"),
                        "first_seen_at": meta.get("first_seen_at"),
                        "query_count": meta.get("query_count"),
                        "last_boosted_at": meta.get("last_boosted_at"),
                    }
                )
            active_sections = enriched
        except Exception:
            pass
        return {
            "conversation_id": conversation_id,
            "active_sections": active_sections,
            "total_queries": None,
            "scope_age_minutes": None,
            "bias_weight": get_settings().session_scope_bias,
            "is_fresh": ttl > 0,
            "ttl_seconds": ttl,
            "metadata": meta,
        }
