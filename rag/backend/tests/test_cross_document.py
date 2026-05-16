from __future__ import annotations

import asyncio

from backend.retrieval.cross_document import CrossDocumentRetriever


def test_comparative_detection_without_llm():
    retriever = CrossDocumentRetriever()
    assert asyncio.run(retriever.is_comparative_query("Compare Q1 vs Q2 revenue"))
    assert asyncio.run(retriever.is_comparative_query("What changed from FY25 and FY26?"))
    assert not asyncio.run(retriever.is_comparative_query("What is total income?"))


def test_pool_and_dedup_keeps_highest_score():
    from backend.shared.types import BoundingBox, RetrievedChunk

    def chunk(chunk_id: str, score: float):
        return RetrievedChunk(
            chunk_id=chunk_id,
            project_id="p",
            file_id="f",
            page_number=1,
            chunk_index=1,
            section_header="s",
            raw_text="text",
            context_summary="",
            is_table=False,
            table_html=None,
            bounding_box=BoundingBox(0, 0, 1, 1),
            rrf_score=score,
        )

    retriever = CrossDocumentRetriever()
    pooled = asyncio.run(retriever.pool_and_dedup([[chunk("a", 0.1)], [chunk("a", 0.2), chunk("b", 0.1)]]))
    assert {chunk.chunk_id for chunk in pooled} == {"a", "b"}
    assert next(chunk for chunk in pooled if chunk.chunk_id == "a").rrf_score == 0.2
