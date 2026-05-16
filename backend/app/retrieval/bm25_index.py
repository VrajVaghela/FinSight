from __future__ import annotations

import pickle
from typing import Iterable


def build_bm25_payload(chunks: Iterable[dict]) -> bytes:
    ordered = sorted(chunks, key=lambda item: int(item.get("chunk_index", 0)))
    return pickle.dumps(
        {
            "corpus": [str(chunk.get("raw_text", "")) for chunk in ordered],
            "chunk_ids": [str(chunk["chunk_id"]) for chunk in ordered],
        }
    )


async def write_bm25_index(redis_client, project_id: str, chunks: Iterable[dict]) -> None:
    await redis_client.set(f"bm25:{project_id}", build_bm25_payload(chunks))
