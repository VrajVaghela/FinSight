from __future__ import annotations

import argparse
import asyncio

from backend.embedding_client import embed_query
from backend.retrieval.vector_searcher import VectorSearcher


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("query")
    parser.add_argument("--project-id", default="adani")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    hits = await VectorSearcher().dense_search(
        await embed_query(args.query),
        project_id=args.project_id,
        top_k=args.top_k,
    )
    for hit in hits:
        payload = hit.payload or {}
        assert payload.get("project_id") == args.project_id, "project_id filter failed"
        assert payload.get("bounding_box"), "bounding_box missing"
        print(
            payload.get("page_number"),
            round(float(hit.score), 4),
            payload.get("section_header", ""),
        )


if __name__ == "__main__":
    asyncio.run(main())
