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


GOOD_QUERIES = [
    "What are the major business segments?",
    "What is consolidated total income H1-26?",
    "What drove EBITDA growth in H1-26?",
    "Describe airport performance in H1-26",
    "What is total revenue from energy segment?",
    "How did logistics performance change in H1-26?",
]

BAD_QUERIES = [
    "What is the CEO's email address?",
    "What is the chairman's phone number?",
    "What is Tesla's revenue?",
    "What will Adani do in 2035?",
    "Summarise slide 47",
    "What is the weather in Mumbai today?",
    "Give me the CFO's private mobile number.",
    "Which stock should I buy tomorrow?",
]


async def score_query(query: str, project_id: str) -> float:
    result = await query_pipeline(query, await embed_query(query), project_id)
    if hasattr(result, "chunks") and result.chunks:
        return float(result.chunks[0].reranker_score)
    return 0.0


def choose_threshold(good_scores: list[float], bad_scores: list[float]) -> tuple[float, float, float] | None:
    if not good_scores or not bad_scores:
        return None

    for threshold in sorted(set(good_scores + bad_scores)):
        fpr = sum(1 for score in good_scores if score < threshold) / len(good_scores)
        tpr = sum(1 for score in bad_scores if score < threshold) / len(bad_scores)
        if fpr < 0.05 and tpr > 0.80:
            return threshold, fpr, tpr
    return None


async def calibrate(project_id: str) -> int:
    good_scores = [await score_query(query, project_id) for query in GOOD_QUERIES]
    bad_scores = [await score_query(query, project_id) for query in BAD_QUERIES]

    selected = choose_threshold(good_scores, bad_scores)
    if selected is None:
        print("WARNING: Could not find threshold with FPR < 5% and TPR > 80%.")
        print(f"Good scores: {[round(score, 4) for score in good_scores]}")
        print(f"Bad scores:  {[round(score, 4) for score in bad_scores]}")
        return 1

    threshold, fpr, tpr = selected
    print(f"GATE2_THRESHOLD={threshold:.4f}  # FPR={fpr:.1%}, TPR={tpr:.1%}")
    print(f"Add to .env:  GATE2_THRESHOLD={threshold:.4f}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-id", default=os.getenv("EVAL_PROJECT_ID", "adani-q2-fy26"))
    parser.add_argument(
        "--scores-json",
        help="Optional offline JSON with {'good': [...], 'bad': [...]} scores.",
    )
    args = parser.parse_args()

    if args.scores_json:
        scores = json.loads(Path(args.scores_json).read_text(encoding="utf-8"))
        selected = choose_threshold(
            [float(score) for score in scores.get("good", [])],
            [float(score) for score in scores.get("bad", [])],
        )
        if selected is None:
            raise SystemExit("No threshold satisfies FPR < 5% and TPR > 80%.")
        threshold, fpr, tpr = selected
        print(f"GATE2_THRESHOLD={threshold:.4f}  # FPR={fpr:.1%}, TPR={tpr:.1%}")
        print(f"Add to .env:  GATE2_THRESHOLD={threshold:.4f}")
        return

    raise SystemExit(asyncio.run(calibrate(args.project_id)))


if __name__ == "__main__":
    main()
