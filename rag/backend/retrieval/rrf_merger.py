from __future__ import annotations

from collections import defaultdict
from typing import Any

from backend.shared.types import RetrievedChunk

from .vector_searcher import COLLECTION_NAME, get_client


class RRFMerger:
    @staticmethod
    def merge(
        bm25_hits: list[dict[str, Any]],
        dense_hits: list[Any],
        k: int = 60,
        client: Any | None = None,
    ) -> list[RetrievedChunk]:
        scores: dict[str, float] = defaultdict(float)

        for rank, hit in enumerate(bm25_hits, start=1):
            scores[str(hit["chunk_id"])] += 1 / (k + rank)

        for rank, hit in enumerate(dense_hits, start=1):
            scores[str(hit.id)] += 1 / (k + rank)

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        ranked_ids = [chunk_id for chunk_id, _ in ranked]
        if not ranked_ids:
            return []

        qdrant = client or get_client()
        points = qdrant.retrieve(
            collection_name=COLLECTION_NAME,
            ids=ranked_ids,
            with_payload=True,
        )
        payload_map = {str(point.id): point.payload for point in points}
        dense_score_map = {str(hit.id): float(hit.score) for hit in dense_hits}
        rrf_score_map = dict(ranked)

        chunks: list[RetrievedChunk] = []
        for chunk_id in ranked_ids:
            payload = payload_map.get(chunk_id)
            if not payload:
                continue
            chunks.append(
                RetrievedChunk.from_qdrant_payload(
                    chunk_id,
                    payload,
                    similarity_score=dense_score_map.get(chunk_id, 0.0),
                    rrf_score=rrf_score_map.get(chunk_id, 0.0),
                )
            )
        return chunks

    @staticmethod
    def assert_no_duplicates(chunks: list[RetrievedChunk]) -> None:
        ids = [chunk.chunk_id for chunk in chunks]
        duplicates = sorted({chunk_id for chunk_id in ids if ids.count(chunk_id) > 1})
        if duplicates:
            raise AssertionError(f"RRF returned duplicate chunk IDs: {duplicates[:5]}")
