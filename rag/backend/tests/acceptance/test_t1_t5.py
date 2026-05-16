from __future__ import annotations

import asyncio
import os
import time

from backend.embedding_client import embed_query
from backend.retrieval import query_pipeline
from backend.shared.types import RefusalEvent, RetrievalResult


async def acceptance() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is required for acceptance tests")

    project_id = os.getenv("EVAL_PROJECT_ID", "adani-q2-fy26")

    q1 = "What are the major business segments?"
    r1 = await query_pipeline(q1, await embed_query(q1), project_id)
    assert isinstance(r1, RetrievalResult)
    assert all(chunk.page_number > 0 and chunk.bounding_box.w > 0 for chunk in r1.chunks[:5])
    assert len({chunk.section_header for chunk in r1.chunks[:10]}) >= 2

    q2 = "What is consolidated total income H1-26?"
    r2 = await query_pipeline(q2, await embed_query(q2), project_id)
    assert isinstance(r2, RetrievalResult)
    assert any(chunk.is_table or "income" in chunk.section_header.lower() for chunk in r2.chunks[:3])
    assert any("total income" in hit.get("snippet", "").lower() for hit in r2.debug.get("bm25_hits", []))

    q3 = "What drivers are mentioned for EBITDA changes in H1-26?"
    r3 = await query_pipeline(q3, await embed_query(q3), project_id)
    assert isinstance(r3, RetrievalResult)
    sections = [chunk.section_header for chunk in r3.chunks[:10]]
    assert len(set(sections)) >= 2
    assert max(sections.count(section) for section in set(sections)) <= 6

    q4 = "What is the CEO's email address?"
    start = time.perf_counter()
    r4 = await query_pipeline(q4, await embed_query(q4), project_id)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    assert isinstance(r4, RefusalEvent)
    assert r4.level in {1, 2}
    assert "Not found" in r4.message
    assert elapsed_ms < 100

    q5a = "Summarize airport performance"
    q5b = "Break down airport performance by passenger traffic and cargo"
    r5a = await query_pipeline(q5a, await embed_query(q5a), project_id)
    r5b = await query_pipeline(q5b, await embed_query(q5b), project_id)
    assert isinstance(r5a, RetrievalResult)
    assert isinstance(r5b, RetrievalResult)
    overlap = {chunk.chunk_id for chunk in r5a.chunks[:5]} & {chunk.chunk_id for chunk in r5b.chunks[:5]}
    assert len(overlap) >= 2


if __name__ == "__main__":
    asyncio.run(acceptance())
