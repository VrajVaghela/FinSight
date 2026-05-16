from __future__ import annotations

import asyncio
from typing import Any

from .bm25_searcher import BM25Searcher
from .vector_searcher import VectorSearcher


class HybridRetriever:
    def __init__(
        self,
        bm25: BM25Searcher | None = None,
        vector: VectorSearcher | None = None,
    ) -> None:
        self.bm25 = bm25 or BM25Searcher()
        self.vector = vector or VectorSearcher()

    async def retrieve(
        self,
        query: str,
        query_vector: list[float],
        project_id: str,
        top_k: int = 150,
        file_ids: list[str] | None = None,
        section_ids: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], list[Any]]:
        bm25_task = asyncio.create_task(
            self.bm25.search(query, project_id, top_k, file_ids=file_ids, section_ids=section_ids)
        )
        dense_task = asyncio.create_task(
            self.vector.dense_search(query_vector, project_id, top_k, file_ids=file_ids, section_ids=section_ids)
        )
        return await asyncio.gather(bm25_task, dense_task)
