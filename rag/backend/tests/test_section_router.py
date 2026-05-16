from __future__ import annotations

import asyncio

from backend.retrieval.section_router import SectionRouter
from backend.shared.types import BoundingBox, RetrievedChunk


def make_chunk(section_id: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=section_id,
        project_id="p",
        file_id="f",
        page_number=1,
        chunk_index=1,
        section_header="Airport Operations",
        raw_text="text",
        context_summary="",
        is_table=False,
        table_html=None,
        bounding_box=BoundingBox(0, 0, 1, 1),
        section_id=section_id,
    )


def test_section_filter_preserves_order_and_falls_back():
    router = SectionRouter(qdrant_client=object(), redis_client=object())
    chunks = [make_chunk("a"), make_chunk("b"), make_chunk("c")]
    filtered = asyncio.run(router.filter_chunks_by_sections(chunks, ["b", "c"]))
    assert [chunk.section_id for chunk in filtered] == ["b", "c"]
    fallback = asyncio.run(router.filter_chunks_by_sections(chunks, ["missing"]))
    assert fallback == chunks
