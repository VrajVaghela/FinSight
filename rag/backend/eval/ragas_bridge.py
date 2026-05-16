from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def get_retrieval_metrics(query_id: str, run_output_path: str = "backend/eval/run_eval_output.json") -> dict[str, Any]:
    path = Path(run_output_path)
    if not path.exists():
        return {
            "query_id": query_id,
            "contextual_precision": None,
            "retrieved_chunk_count": 0,
            "top_chunk_reranker_score": None,
            "gate1_fired": None,
            "gate2_fired": None,
            "retrieval_ms": None,
            "note": "Run output not found yet.",
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    query_metrics = data.get("queries", {}).get(query_id, {})
    return {
        "query_id": query_id,
        "contextual_precision": query_metrics.get("contextual_precision"),
        "retrieved_chunk_count": query_metrics.get("retrieved_chunk_count", 0),
        "top_chunk_reranker_score": query_metrics.get("top_chunk_reranker_score"),
        "gate1_fired": query_metrics.get("gate1_fired", False),
        "gate2_fired": query_metrics.get("gate2_fired", False),
        "retrieval_ms": query_metrics.get("retrieval_ms"),
    }


def export_for_ragas(eval_output_path: str) -> str:
    source = Path(eval_output_path)
    data = json.loads(source.read_text(encoding="utf-8"))
    records = data.get("ragas_records", data if isinstance(data, list) else [])
    out = source.with_name("ragas_ready.json")
    out.write_text(json.dumps(records, indent=2), encoding="utf-8")
    return str(out)
