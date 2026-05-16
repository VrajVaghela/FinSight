from __future__ import annotations

import asyncio
import pickle
from collections import OrderedDict, defaultdict
from dataclasses import asdict, dataclass
from typing import Any

from app.config import get_settings
from app.shared.types import RetrievedChunk

from .bm25_searcher import tokenize
from .vector_searcher import get_client


@dataclass(slots=True)
class SectionMatch:
    section_id: str
    section_header: str
    section_level: int
    file_id: str
    start_page: int
    end_page: int
    chunk_count: int
    bm25_score: float
    dense_score: float
    rrf_score: float
    summary_text: str

    def dict(self) -> dict[str, Any]:
        return asdict(self)


class SectionRouter:
    def __init__(self, qdrant_client: Any | None = None, redis_client: Any | None = None) -> None:
        self.client = qdrant_client or get_client()
        self.redis = redis_client
        self.collection = get_settings().section_collection
        self._metadata_cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._cache_limit = 1000

    async def _redis(self) -> Any:
        if self.redis is None:
            import redis.asyncio as aioredis

            settings = get_settings()
            self.redis = aioredis.Redis(host=settings.redis_host, port=settings.redis_port)
        return self.redis

    async def _bm25_sections(self, query: str, project_id: str, top_k: int) -> list[dict[str, Any]]:
        raw = await (await self._redis()).get(f"bm25_sections:{project_id}")
        if not raw:
            return []
        data = pickle.loads(raw)
        corpus = data.get("corpus", [])
        ids = data.get("ids", data.get("section_ids", []))
        if not corpus or not ids:
            return []
        from rank_bm25 import BM25Okapi

        bm25 = BM25Okapi([tokenize(text) for text in corpus])
        scores = await asyncio.to_thread(bm25.get_scores, tokenize(query))
        ranked = sorted(zip(ids, corpus, scores), key=lambda item: float(item[2]), reverse=True)
        return [
            {"section_id": str(section_id), "text": text, "bm25_score": float(score)}
            for section_id, text, score in ranked[:top_k]
            if float(score) > 0
        ]

    async def _dense_sections(self, query_vector: list[float], project_id: str, top_k: int) -> list[Any]:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        query_filter = Filter(
            must=[FieldCondition(key="project_id", match=MatchValue(value=project_id))]
        )
        if hasattr(self.client, "search"):
            return await asyncio.to_thread(
                self.client.search,
                collection_name=self.collection,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=top_k,
                with_payload=True,
            )
        response = await asyncio.to_thread(
            self.client.query_points,
            collection_name=self.collection,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        return response.points

    async def route_sections(
        self,
        query: str,
        query_vector: list[float],
        project_id: str,
        top_k: int = 5,
    ) -> list[SectionMatch]:
        settings = get_settings()
        bm25_task = asyncio.create_task(self._bm25_sections(query, project_id, top_k * 4))
        dense_task = asyncio.create_task(self._dense_sections(query_vector, project_id, top_k * 4))
        bm25_hits, dense_hits = await asyncio.gather(bm25_task, dense_task)

        scores: dict[str, float] = defaultdict(float)
        bm25_score_map = {hit["section_id"]: float(hit["bm25_score"]) for hit in bm25_hits}
        dense_score_map = {str(hit.id): float(hit.score) for hit in dense_hits}

        for rank, hit in enumerate(bm25_hits, start=1):
            scores[hit["section_id"]] += 1 / (settings.section_rrf_k + rank)
        for rank, hit in enumerate(dense_hits, start=1):
            scores[str(hit.id)] += 1 / (settings.section_rrf_k + rank)

        ranked_ids = [section_id for section_id, _ in sorted(scores.items(), key=lambda item: item[1], reverse=True)]
        if not ranked_ids:
            return []

        points = await asyncio.to_thread(
            self.client.retrieve,
            collection_name=self.collection,
            ids=ranked_ids[: top_k * 2],
            with_payload=True,
        )
        payloads = {str(point.id): point.payload or {} for point in points}
        matches = []
        for section_id in ranked_ids:
            payload = payloads.get(section_id)
            if not payload:
                payload = await self.get_section_metadata(section_id)
            if not payload:
                continue
            matches.append(
                SectionMatch(
                    section_id=section_id,
                    section_header=str(payload.get("section_header", "")),
                    section_level=int(payload.get("section_level", 1) or 1),
                    file_id=str(payload.get("file_id", "")),
                    start_page=int(payload.get("start_page", 0) or 0),
                    end_page=int(payload.get("end_page", 0) or 0),
                    chunk_count=int(payload.get("chunk_count", 0) or 0),
                    bm25_score=bm25_score_map.get(section_id, 0.0),
                    dense_score=dense_score_map.get(section_id, 0.0),
                    rrf_score=scores.get(section_id, 0.0),
                    summary_text=str(payload.get("summary_text", ""))[:200],
                )
            )
            if len(matches) >= top_k:
                break
        return matches

    async def filter_chunks_by_sections(
        self,
        chunks: list[RetrievedChunk],
        section_ids: list[str],
    ) -> list[RetrievedChunk]:
        if not section_ids:
            return chunks
        allowed = set(section_ids)
        filtered = [chunk for chunk in chunks if chunk.section_id in allowed]
        return filtered or chunks

    async def get_section_metadata(self, section_id: str) -> dict[str, Any]:
        if section_id in self._metadata_cache:
            self._metadata_cache.move_to_end(section_id)
            return self._metadata_cache[section_id]
        points = await asyncio.to_thread(
            self.client.retrieve,
            collection_name=self.collection,
            ids=[section_id],
            with_payload=True,
        )
        payload = points[0].payload if points else {}
        self._metadata_cache[section_id] = payload or {}
        if len(self._metadata_cache) > self._cache_limit:
            self._metadata_cache.popitem(last=False)
        return self._metadata_cache[section_id]
