from __future__ import annotations

import os
import uuid

import pytest

from backend.embedding_client import embed_query
from backend.retrieval import query_pipeline
from backend.shared.types import RetrievalResult


pytestmark = pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="Live integration test requires GEMINI_API_KEY, Qdrant, and Redis.",
)


@pytest.mark.anyio
async def test_m4_chunk_contract_for_numeric_query():
    query = "What is total income H1-26?"
    project_id = os.getenv("EVAL_PROJECT_ID", "adani-q2-fy26")
    result = await query_pipeline(query, await embed_query(query), project_id)
    assert isinstance(result, RetrievalResult)

    for chunk in result.chunks:
        assert isinstance(chunk.raw_text, str) and chunk.raw_text.strip()
        assert isinstance(chunk.bounding_box.x, float)
        assert isinstance(chunk.bounding_box.y, float)
        assert isinstance(chunk.bounding_box.w, float)
        assert isinstance(chunk.bounding_box.h, float)
        assert 0.0 <= chunk.bounding_box.x <= 1.0
        assert 0.0 <= chunk.bounding_box.y <= 1.0
        assert 0.0 <= chunk.bounding_box.w <= 1.0
        assert 0.0 <= chunk.bounding_box.h <= 1.0
        assert isinstance(chunk.page_number, int) and chunk.page_number >= 1
        assert isinstance(chunk.is_table, bool)
        uuid.UUID(chunk.chunk_id)

    assert any(
        chunk.is_table or "income" in chunk.section_header.lower()
        for chunk in result.chunks[:5]
    )
