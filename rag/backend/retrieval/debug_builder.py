from __future__ import annotations

from typing import Any

from backend.shared.types import RefusalEvent, RetrievedChunk


def _dense_hit(hit: Any, rank: int) -> dict[str, Any]:
    payload = getattr(hit, "payload", {}) or {}
    return {
        "rank": rank,
        "chunk_id": str(getattr(hit, "id", "")),
        "similarity": float(getattr(hit, "score", 0.0)),
        "page": payload.get("page_number"),
        "section_header": payload.get("section_header"),
    }


def _chunk(chunk: RetrievedChunk, rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "chunk_id": chunk.chunk_id,
        "page": chunk.page_number,
        "section": chunk.section_header,
        "section_header": chunk.section_header,
        "similarity_score": chunk.similarity_score,
        "rrf_score": chunk.rrf_score,
        "reranker_score": chunk.reranker_score,
        "is_table": chunk.is_table,
    }


def build_debug(
    bm25_hits: list[dict[str, Any]],
    dense_hits: list[Any],
    merged: list[RetrievedChunk],
    reranked: list[RetrievedChunk] | None,
    gate1: RefusalEvent | None,
    gate2: RefusalEvent | None,
    gate1_threshold: float | None = None,
    gate2_threshold: float | None = None,
) -> dict[str, Any]:
    max_similarity = float(dense_hits[0].score) if dense_hits else 0.0
    top_reranker_score = float(reranked[0].reranker_score) if reranked else 0.0

    from .refusal_gate import RefusalGate

    return {
        "bm25_hits": [
            {
                "rank": rank,
                "chunk_id": hit.get("chunk_id"),
                "score": float(hit.get("bm25_score", 0.0)),
                "snippet": str(hit.get("text", ""))[:120],
            }
            for rank, hit in enumerate(bm25_hits[:10], start=1)
        ],
        "dense_hits": [
            _dense_hit(hit, rank) for rank, hit in enumerate(dense_hits[:10], start=1)
        ],
        "rrf_merged": [
            _chunk(chunk, rank) for rank, chunk in enumerate(merged[:20], start=1)
        ],
        "reranker": [
            _chunk(chunk, rank) for rank, chunk in enumerate((reranked or [])[:20], start=1)
        ],
        "reranked": [
            _chunk(chunk, rank) for rank, chunk in enumerate((reranked or [])[:20], start=1)
        ],
        "gate_1": {
            "fired": gate1 is not None,
            "max_similarity": round(max_similarity, 4),
            "threshold": gate1_threshold if gate1_threshold is not None else RefusalGate.gate1_threshold(),
        },
        "gate_2": {
            "fired": gate2 is not None,
            "reranker_score": round(top_reranker_score, 4),
            "threshold": gate2_threshold if gate2_threshold is not None else RefusalGate.gate2_threshold(),
        },
    }
