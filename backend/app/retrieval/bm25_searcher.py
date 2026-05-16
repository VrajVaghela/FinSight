from __future__ import annotations

import os
import asyncio
import pickle
import re
from typing import Any

from app.config import get_settings


TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._%-]*")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


class BM25Searcher:
    def __init__(self, redis_client: Any | None = None) -> None:
        self.redis = redis_client

    async def _redis(self) -> Any:
        if self.redis is None:
            try:
                import redis.asyncio as aioredis
            except ImportError as exc:
                raise RuntimeError("redis is required for BM25Searcher") from exc
            self.redis = aioredis.from_url(get_settings().redis_url)
        return self.redis

    async def search(
        self,
        query: str,
        project_id: str,
        top_k: int = 150,
        file_ids: list[str] | None = None,
        section_ids: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        raw = await (await self._redis()).get(f"bm25:{project_id}")
        if not raw:
            return []

        try:
            data = pickle.loads(raw)
        except Exception as exc:
            raise ValueError(f"Invalid BM25 payload for project {project_id!r}") from exc

        corpus = data.get("corpus", [])
        chunk_ids = data.get("chunk_ids", [])
        metadata = data.get("metadata", [{} for _ in corpus])
        if len(corpus) != len(chunk_ids):
            raise ValueError("BM25 corpus and chunk_ids lengths differ")

        try:
            from rank_bm25 import BM25Okapi
        except ImportError as exc:
            raise RuntimeError("rank-bm25 is required for BM25Searcher") from exc

        tokenized_corpus = [tokenize(text) for text in corpus]
        query_tokens = tokenize(query)
        if not tokenized_corpus or not query_tokens:
            return []

        bm25 = BM25Okapi(tokenized_corpus)
        scores = await asyncio.to_thread(bm25.get_scores, query_tokens)
        ranked = sorted(
            zip(chunk_ids, corpus, scores, metadata),
            key=lambda item: float(item[2]),
            reverse=True,
        )
        filtered = []
        for chunk_id, text, score, meta in ranked:
            if float(score) <= 0:
                continue
            if file_ids and meta.get("file_id") and meta.get("file_id") not in file_ids:
                continue
            if section_ids and meta.get("section_id") and meta.get("section_id") not in section_ids:
                continue
            filtered.append(
                {
                    "chunk_id": str(chunk_id),
                    "text": text,
                    "bm25_score": float(score),
                    "file_id": meta.get("file_id"),
                    "section_id": meta.get("section_id"),
                }
            )
            if len(filtered) >= top_k:
                break
        return filtered
