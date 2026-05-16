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


async def export(project_id: str, output_path: Path, top_k: int = 5) -> Path:
    dataset = json.loads((ROOT / "backend" / "eval" / "eval_dataset.json").read_text(encoding="utf-8"))
    records = []
    for row in dataset:
        if row.get("adversarial"):
            continue
        result = await query_pipeline(row["query"], await embed_query(row["query"]), project_id)
        contexts = []
        if hasattr(result, "chunks"):
            contexts = [chunk.raw_text for chunk in result.chunks[:top_k]]
        records.append(
            {
                "question": row["query"],
                "answer": "",
                "contexts": contexts,
                "ground_truth": row.get("ground_truth", row.get("notes", "")),
                "query_id": row["id"],
            }
        )
    output_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
    print(output_path)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", default=os.getenv("EVAL_PROJECT_ID", "adani-q2-fy26"))
    parser.add_argument("--out", default=str(ROOT / "backend" / "eval" / "ragas_input.json"))
    args = parser.parse_args()
    asyncio.run(export(args.project_id, Path(args.out)))


if __name__ == "__main__":
    main()
