from __future__ import annotations

import asyncio

from backend.retrieval.neural_reranker import NeuralReranker
from backend.shared.types import BoundingBox, RetrievedChunk


class FakeCrossEncoder:
    def predict(self, pairs):
        return [0.91 if "Revenue" in pair[1] else 0.12 for pair in pairs]


def chunk(chunk_id: str, text: str) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        project_id="adani-q2-fy26",
        file_id="file-1",
        page_number=1,
        chunk_index=0,
        section_header="Financial Performance",
        raw_text=text,
        context_summary="",
        is_table=False,
        table_html=None,
        bounding_box=BoundingBox(x=0.1, y=0.1, w=0.5, h=0.1),
        similarity_score=0.8,
    )


def test_reranker_orders_chunks():
    reranker = NeuralReranker(model=FakeCrossEncoder())
    chunks = [
        chunk("1", "Revenue grew 23% in Q1"),
        chunk("2", "CEO biography and background"),
        chunk("3", "Revenue grew 25% in Q2"),
    ]

    result = asyncio.run(reranker.rerank("What was revenue growth?", chunks, top_k=2))

    assert len(result) == 2
    assert all(item.reranker_score > 0 for item in result)
    assert all("Revenue" in item.raw_text for item in result)
