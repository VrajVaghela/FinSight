from __future__ import annotations

import json

from backend.retrieval.debug_builder import build_debug
from backend.shared.types import BoundingBox, RetrievedChunk


class DenseHit:
    def __init__(self, chunk_id: str, score: float, page: int) -> None:
        self.id = chunk_id
        self.score = score
        self.payload = {"page_number": page, "section_header": "Revenue"}


def chunk(chunk_id: str, rank: int) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        project_id="adani-q2-fy26",
        file_id="file-1",
        page_number=rank,
        chunk_index=rank,
        section_header="Revenue",
        raw_text="Total income and EBITDA details.",
        context_summary="",
        is_table=rank == 1,
        table_html=None,
        bounding_box=BoundingBox(0.1, 0.1, 0.5, 0.2),
        similarity_score=0.8,
        rrf_score=0.03,
        reranker_score=0.9,
    )


def test_m5_debug_payload_contract_is_json_serializable():
    debug = build_debug(
        [{"chunk_id": "a", "bm25_score": 4.2, "text": "x" * 200}],
        [DenseHit("a", 0.87, 12)],
        [chunk("a", 1)],
        [chunk("a", 1)],
        None,
        None,
    )
    json.dumps(debug)

    assert set(["bm25_hits", "dense_hits", "rrf_merged", "reranked", "gate_1", "gate_2"]).issubset(debug)
    assert len(debug["bm25_hits"][0]["snippet"]) <= 120
    assert isinstance(debug["dense_hits"][0]["similarity"], float)
    assert isinstance(debug["rrf_merged"][0]["rrf_score"], float)
    assert isinstance(debug["reranked"][0]["reranker_score"], float)
    assert isinstance(debug["gate_1"]["fired"], bool)
    assert isinstance(debug["gate_2"]["fired"], bool)
