from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from backend.embedding_client import embed_query
from backend.retrieval import query_pipeline
from backend.shared.types import RefusalEvent, RetrievalResult


async def run_suite() -> None:
    if not os.getenv("GEMINI_API_KEY"):
        raise RuntimeError("GEMINI_API_KEY is required for adversarial suite")

    project_id = os.getenv("EVAL_PROJECT_ID", "adani-q2-fy26")
    suite = json.loads(Path("backend/eval/adversarial_suite.json").read_text(encoding="utf-8"))
    caught = 0
    gate1 = 0
    gate2 = 0

    for row in suite:
        result = await query_pipeline(row["query"], await embed_query(row["query"]), project_id)
        assert isinstance(result, RefusalEvent), f"{row['id']} returned {type(result)}"
        assert result.level <= row["expected_gate"] or result.level == row["expected_gate"]
        assert "Not found" in result.message
        caught += 1
        gate1 += int(result.level == 1)
        gate2 += int(result.level == 2)

    dataset = json.loads(Path("backend/eval/eval_dataset.json").read_text(encoding="utf-8"))
    good_queries = [row for row in dataset if not row.get("adversarial")][:40]
    false_positive_count = 0
    for row in good_queries:
        result = await query_pipeline(row["query"], await embed_query(row["query"]), project_id)
        false_positive_count += int(isinstance(result, RefusalEvent))
        assert isinstance(result, RetrievalResult), f"Good query refused: {row['id']}"

    print(
        {
            "pass_rate": caught / len(suite),
            "gate1_catch_rate": gate1 / len(suite),
            "gate2_catch_rate": gate2 / len(suite),
            "false_positive_count": false_positive_count,
        }
    )


if __name__ == "__main__":
    asyncio.run(run_suite())
