from __future__ import annotations

import asyncio
import os

from backend.embedding_client import embed_query
from backend.retrieval import query_pipeline
from backend.retrieval.neural_reranker import _get_model


def rss_mb() -> float:
    try:
        import psutil

        return psutil.Process().memory_info().rss / 1024 / 1024
    except Exception:
        return 0.0


async def main() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is required for memory test")

    project_id = os.getenv("EVAL_PROJECT_ID", "adani-q2-fy26")
    model = _get_model()
    before = rss_mb()
    queries = [
        "What are the major business segments?",
        "What is consolidated total income H1-26?",
        "What drove EBITDA growth?",
        "Describe airport performance",
    ]
    vectors = [await embed_query(query) for query in queries]
    for index in range(100):
        query = queries[index % len(queries)]
        vector = vectors[index % len(vectors)]
        await query_pipeline(query, vector, project_id)
        assert _get_model() is model
    after = rss_mb()
    if before and after:
        assert after - before < 50, f"Memory grew by {after - before:.1f}MB"


if __name__ == "__main__":
    asyncio.run(main())
