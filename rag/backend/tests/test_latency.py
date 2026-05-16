from __future__ import annotations

import asyncio
import os
import time

from backend.embedding_client import embed_query
from backend.retrieval import query_pipeline


async def bench() -> None:
    project_id = os.getenv("EVAL_PROJECT_ID", "adani-q2-fy26")
    queries = [
        "business segments",
        "total income",
        "EBITDA drivers",
        "airport performance",
        "revenue growth",
        "PAT margin",
        "debt ratio",
        "cash flow",
        "capital expenditure",
        "dividend",
    ]

    vectors = await asyncio.gather(*(embed_query(query) for query in queries))
    start = time.perf_counter()
    results = await asyncio.gather(
        *[
            query_pipeline(query, vector, project_id)
            for query, vector in zip(queries, vectors)
        ]
    )
    total_ms = int((time.perf_counter() - start) * 1000)
    latencies = sorted(
        result.retrieval_ms for result in results if hasattr(result, "retrieval_ms")
    )
    if not latencies:
        raise AssertionError("No successful RetrievalResult latencies to measure")

    p50 = latencies[len(latencies) // 2]
    p95 = latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))]
    p99 = max(latencies)
    print(f"p50={p50}ms p95={p95}ms p99={p99}ms total={total_ms}ms")
    assert p99 < 500, f"p99={p99}ms exceeds 500ms budget"


if __name__ == "__main__":
    asyncio.run(bench())
