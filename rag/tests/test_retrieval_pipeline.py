from __future__ import annotations

import asyncio
from dataclasses import dataclass

from backend.retrieval import query_pipeline, set_retriever_for_tests
from backend.retrieval.neural_reranker import NeuralReranker
from backend.retrieval.refusal_gate import RefusalGate
from backend.retrieval.rrf_merger import RRFMerger
from backend.shared.types import RefusalEvent, RetrievalResult, RetrievedChunk


@dataclass
class DenseHit:
    id: str
    score: float
    payload: dict


def payload(project_id: str = "adani", page_number: int = 1) -> dict:
    return {
        "project_id": project_id,
        "file_id": "file-1",
        "page_number": page_number,
        "chunk_index": page_number - 1,
        "section_header": f"Section {page_number}",
        "raw_text": f"Chunk text {page_number}",
        "context_summary": "Summary",
        "is_table": False,
        "table_html": None,
        "bounding_box": {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4},
    }


class FakeQdrant:
    def __init__(self, payloads: dict[str, dict]) -> None:
        self.payloads = payloads

    def retrieve(self, collection_name: str, ids: list[str], with_payload: bool):
        return [DenseHit(id=chunk_id, score=0.0, payload=self.payloads[chunk_id]) for chunk_id in ids]


class FakeRetriever:
    async def retrieve(self, query: str, query_vector: list[float], project_id: str, top_k: int):
        return (
            [{"chunk_id": "a", "text": "alpha", "bm25_score": 2.0}],
            [DenseHit("a", 0.91, payload(page_number=1)), DenseHit("b", 0.83, payload(page_number=2))],
        )


class FakeModel:
    def predict(self, pairs):
        return [0.4, 0.9]


def test_refusal_gate_level_1(monkeypatch):
    monkeypatch.setenv("GATE1_THRESHOLD", "0.5")
    event = RefusalGate.check_threshold([DenseHit("x", 0.49, {})])
    assert isinstance(event, RefusalEvent)
    assert event.level == 1
    assert event.message == "Not found in the document."


def test_rrf_merger_deduplicates_and_maps_payloads():
    chunks = RRFMerger.merge(
        [{"chunk_id": "a", "text": "alpha", "bm25_score": 2.0}],
        [DenseHit("a", 0.9, payload(page_number=1)), DenseHit("b", 0.8, payload(page_number=2))],
        client=FakeQdrant({"a": payload(page_number=1), "b": payload(page_number=2)}),
    )

    assert [chunk.chunk_id for chunk in chunks] == ["a", "b"]
    assert chunks[0].bounding_box.w == 0.3
    assert chunks[0].similarity_score == 0.9


def test_query_pipeline_returns_reranked_result(monkeypatch):
    import backend.retrieval as retrieval

    monkeypatch.setattr(retrieval.RRFMerger, "merge", staticmethod(lambda bm25, dense, k=60: [
        RetrievedChunk.from_qdrant_payload("a", payload(page_number=1), similarity_score=0.91),
        RetrievedChunk.from_qdrant_payload("b", payload(page_number=2), similarity_score=0.83),
    ]))
    set_retriever_for_tests(FakeRetriever())
    NeuralReranker.set_for_tests(NeuralReranker(model=FakeModel()))

    try:
        result = asyncio.run(query_pipeline("query", [0.1], "adani", user_id="u1"))
    finally:
        set_retriever_for_tests(None)
        NeuralReranker.set_for_tests(None)

    assert isinstance(result, RetrievalResult)
    assert [chunk.chunk_id for chunk in result.chunks] == ["b", "a"]
    assert result.gate1_score == 0.91
    assert result.gate2_score == 0.9
