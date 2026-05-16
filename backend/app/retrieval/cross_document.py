from __future__ import annotations

import re
from typing import Any

from app.config import get_settings
from app.shared.types import RetrievedChunk

from .file_metadata import FileMetadataCache
from .hybrid_retriever import HybridRetriever
from .neural_reranker import NeuralReranker
from .rrf_merger import RRFMerger


COMPARATIVE_TERMS = [
    "compare",
    "versus",
    " vs ",
    "difference between",
    "change from",
    "growth from",
    "year over year",
    "q1 vs q2",
]
TEMPORAL_RE = re.compile(r"\b(Q[1-4]|H[1-2]|FY\d{2,4}|20\d{2})\b", re.I)


class CrossDocumentRetriever:
    def __init__(
        self,
        hybrid: HybridRetriever | None = None,
        file_metadata: FileMetadataCache | None = None,
    ) -> None:
        self.hybrid = hybrid
        self.file_metadata = file_metadata or FileMetadataCache()

    async def is_comparative_query(
        self,
        query: str,
        conversation_history: list[dict] | None = None,
        is_comparative: bool | None = None,
    ) -> bool:
        if is_comparative is not None:
            return is_comparative
        normalized = f" {query.lower()} "
        if any(term in normalized for term in COMPARATIVE_TERMS):
            return True
        return len(set(TEMPORAL_RE.findall(query))) >= 2

    async def get_target_file_ids(
        self,
        query: str,
        project_id: str,
        conversation_history: list[dict] | None = None,
    ) -> list[str]:
        markers = {marker.upper() for marker in TEMPORAL_RE.findall(query)}
        file_ids: list[str] = []
        for turn in conversation_history or []:
            for file_id in turn.get("file_ids", []) or []:
                if file_id not in file_ids:
                    file_ids.append(file_id)

        # M2/M3 can populate file_meta:{project_id}:files with a JSON list.
        try:
            import redis.asyncio as aioredis

            settings = get_settings()
            redis = aioredis.Redis(host=settings.redis_host, port=settings.redis_port)
            raw = await redis.get(f"file_meta:{project_id}:files")
            if raw:
                candidates = __import__("json").loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
                for item in candidates:
                    text = f"{item.get('file_name', '')} {item.get('period', '')}".upper()
                    if not markers or any(marker in text for marker in markers):
                        if item["file_id"] not in file_ids:
                            file_ids.append(item["file_id"])
        except Exception:
            pass

        return file_ids[:4]

    async def retrieve_multi_file(
        self,
        query: str,
        query_vector: list[float],
        project_id: str,
        file_ids: list[str],
        top_k_per_file: int = 50,
    ) -> list[RetrievedChunk]:
        chunk_lists = []
        hybrid = self.hybrid or HybridRetriever()
        for file_id in file_ids[:4]:
            bm25_hits, dense_hits = await hybrid.retrieve(
                query,
                query_vector,
                project_id,
                top_k=top_k_per_file,
                file_ids=[file_id],
            )
            chunks = RRFMerger.merge(bm25_hits, dense_hits, k=get_settings().rrf_k)
            chunks = [chunk for chunk in chunks if chunk.file_id == file_id]
            for chunk in chunks:
                chunk.source_file_id = chunk.file_id
            chunk_lists.append(chunks)
        pooled = await self.pool_and_dedup(chunk_lists)
        return await NeuralReranker.get().rerank(query, pooled, top_k=get_settings().reranker_top_k)

    async def pool_and_dedup(self, chunk_lists: list[list[RetrievedChunk]]) -> list[RetrievedChunk]:
        by_id: dict[str, RetrievedChunk] = {}
        for chunks in chunk_lists:
            for chunk in chunks:
                existing = by_id.get(chunk.chunk_id)
                score = max(chunk.reranker_score, chunk.rrf_score, chunk.similarity_score)
                existing_score = max(existing.reranker_score, existing.rrf_score, existing.similarity_score) if existing else -1
                if existing is None or score > existing_score:
                    chunk.source_file_id = chunk.file_id
                    by_id[chunk.chunk_id] = chunk
        return list(by_id.values())
