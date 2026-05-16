from __future__ import annotations

import os

import pytest

from backend.embedding_client import embed_query
from backend.retrieval import query_pipeline
from backend.shared.types import RefusalEvent, RetrievalResult


pytestmark = pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="Live integration test requires GEMINI_API_KEY, Qdrant, and Redis.",
)


@pytest.mark.anyio
async def test_m3_query_pipeline_handoff_contract():
    query = "What are the major business segments?"
    project_id = os.getenv("EVAL_PROJECT_ID", "adani-q2-fy26")
    result = await query_pipeline(query, await embed_query(query), project_id)

    assert isinstance(result, (RetrievalResult, RefusalEvent))
    if isinstance(result, RetrievalResult):
        assert isinstance(result.chunks, list)
        assert len(result.chunks) <= 20
        assert isinstance(result.gate1_score, float)
        assert 0.0 <= result.gate1_score <= 1.0
        assert isinstance(result.gate2_score, float)
        assert isinstance(result.retrieval_ms, int)
        assert result.retrieval_ms > 0
        for key in ["bm25_hits", "dense_hits", "rrf_merged", "reranked", "gate_1", "gate_2"]:
            assert key in result.debug
        for chunk in result.chunks:
            assert chunk.chunk_id
            assert chunk.raw_text
            assert chunk.bounding_box
            assert chunk.page_number >= 1
            assert isinstance(chunk.reranker_score, float)
    else:
        assert result.level in {1, 2}
        assert result.reason in {"level_1_threshold", "level_2_reranker"}
        assert result.message == "Not found in the document."
        assert "threshold" in str(result.debug)
