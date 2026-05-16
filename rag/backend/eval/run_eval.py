from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.embedding_client import embed_query
from backend.retrieval import query_pipeline


async def run_eval(dataset_path: Path, project_id: str) -> dict:
    from ranx import Qrels, Run, evaluate

    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    eval_rows = [row for row in dataset if not row.get("adversarial")]
    adv_rows = [row for row in dataset if row.get("adversarial")]

    qrels_dict = {
        row["id"]: {chunk_id: 1 for chunk_id in row.get("relevant_ids", [])}
        for row in eval_rows
    }
    run_dict: dict[str, dict[str, float]] = {}
    query_metrics: dict[str, dict] = {}
    ragas_records: list[dict] = []

    for row in eval_rows:
        result = await query_pipeline(row["query"], await embed_query(row["query"]), project_id)
        if hasattr(result, "chunks"):
            run_dict[row["id"]] = {
                chunk.chunk_id: chunk.reranker_score for chunk in result.chunks
            }
            relevant = set(row.get("relevant_ids", []))
            top5 = result.chunks[:5]
            contextual_precision = (
                sum(1 for chunk in top5 if chunk.chunk_id in relevant) / len(top5)
                if top5 and relevant
                else 0.0
            )
            query_metrics[row["id"]] = {
                "contextual_precision": contextual_precision,
                "retrieved_chunk_count": len(result.chunks),
                "top_chunk_reranker_score": result.chunks[0].reranker_score if result.chunks else 0.0,
                "gate1_fired": False,
                "gate2_fired": False,
                "retrieval_ms": result.retrieval_ms,
            }
            ragas_records.append(
                {
                    "question": row["query"],
                    "answer": "",
                    "contexts": [chunk.raw_text for chunk in top5],
                    "ground_truth": row.get("ground_truth", row.get("notes", "")),
                    "query_id": row["id"],
                }
            )
        else:
            run_dict[row["id"]] = {}
            query_metrics[row["id"]] = {
                "contextual_precision": 0.0,
                "retrieved_chunk_count": 0,
                "top_chunk_reranker_score": 0.0,
                "gate1_fired": getattr(result, "level", None) == 1,
                "gate2_fired": getattr(result, "level", None) == 2,
                "retrieval_ms": result.debug.get("retrieval_ms", 0),
            }

    adv_pass = 0
    for row in adv_rows:
        result = await query_pipeline(row["query"], await embed_query(row["query"]), project_id)
        expected_gate = row.get("expected_gate")
        if hasattr(result, "level") and (expected_gate is None or result.level == expected_gate):
            adv_pass += 1

    metrics = {"precision@5": 0.0, "precision@10": 0.0, "mrr": 0.0, "ndcg@10": 0.0}
    rows_with_judgements = {
        query_id: rels for query_id, rels in qrels_dict.items() if rels
    }
    if rows_with_judgements:
        metrics = evaluate(
            Qrels(rows_with_judgements),
            Run({query_id: run_dict.get(query_id, {}) for query_id in rows_with_judgements}),
            ["precision@5", "precision@10", "mrr", "ndcg@10"],
        )

    output = {
        "eval_rows": len(eval_rows),
        "adv_rows": len(adv_rows),
        "adv_pass_rate": round(adv_pass / len(adv_rows), 3) if adv_rows else 1.0,
        "precision@5": round(float(metrics.get("precision@5", 0.0)), 4),
        "precision@10": round(float(metrics.get("precision@10", 0.0)), 4),
        "mrr": round(float(metrics.get("mrr", 0.0)), 4),
        "ndcg@10": round(float(metrics.get("ndcg@10", 0.0)), 4),
        "queries": query_metrics,
        "ragas_records": ragas_records,
    }
    Path("backend/eval/run_eval_output.json").write_text(
        json.dumps(output, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(output, indent=2))
    return output


async def main(assert_ndcg: float | None = None) -> None:
    result = await run_eval(
        Path(__file__).with_name("eval_dataset.json"),
        os.getenv("EVAL_PROJECT_ID", "adani-q2-fy26"),
    )
    if assert_ndcg is not None and result["ndcg@10"] < assert_ndcg:
        raise SystemExit(f"ndcg@10 below threshold {assert_ndcg}: {result['ndcg@10']}")
    print("PASS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--assert-ndcg", type=float, default=None)
    args = parser.parse_args()
    asyncio.run(main(args.assert_ndcg))
