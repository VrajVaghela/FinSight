from __future__ import annotations

import asyncio
import os
import time

from backend.embedding_client import embed_query
from backend.retrieval import query_pipeline


QUERIES = [
    "What are the major business segments?",
    "What is consolidated total income H1-26?",
    "What drove EBITDA growth?",
    "Describe airport performance",
    "What is the CEO's email address?",
]


def percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, round((len(ordered) - 1) * pct))
    return ordered[idx]


async def run_batch(concurrency: int, duration_seconds: int) -> dict:
    project_id = os.getenv("EVAL_PROJECT_ID", "adani-q2-fy26")
    vectors = {query: await embed_query(query) for query in QUERIES}
    stop_at = time.perf_counter() + duration_seconds
    latencies: list[int] = []
    errors = 0

    async def worker(worker_id: int) -> None:
        nonlocal errors
        index = worker_id
        while time.perf_counter() < stop_at:
            query = QUERIES[index % len(QUERIES)]
            try:
                result = await query_pipeline(query, vectors[query], project_id)
                latencies.append(getattr(result, "retrieval_ms", 0))
            except Exception:
                errors += 1
            index += concurrency

    await asyncio.gather(*(worker(i) for i in range(concurrency)))
    total = len(latencies) + errors
    return {
        "concurrency": concurrency,
        "requests": total,
        "rps": round(total / duration_seconds, 2) if duration_seconds else 0,
        "p50": percentile(latencies, 0.50),
        "p95": percentile(latencies, 0.95),
        "p99": percentile(latencies, 0.99),
        "error_rate": errors / total if total else 0,
    }


async def main() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is required for load test")

    print("warmup", await run_batch(concurrency=1, duration_seconds=10))
    ramp = []
    for concurrency in [1, 5, 10, 25, 50]:
        ramp.append(await run_batch(concurrency=concurrency, duration_seconds=12))
    sustained = await run_batch(concurrency=50, duration_seconds=300)
    spike = await run_batch(concurrency=100, duration_seconds=30)
    recovery = await run_batch(concurrency=10, duration_seconds=60)
    print({"ramp": ramp, "sustained": sustained, "spike": spike, "recovery": recovery})
    assert sustained["p99"] < 1000
    assert sustained["error_rate"] < 0.01
    assert recovery["p99"] < 500


if __name__ == "__main__":
    asyncio.run(main())
