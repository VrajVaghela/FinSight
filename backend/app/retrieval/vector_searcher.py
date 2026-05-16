from __future__ import annotations

import os
import asyncio
from typing import Any


from app.config import get_settings


COLLECTION_NAME = get_settings().qdrant_collection
VECTOR_SIZE = get_settings().qdrant_vector_size

_client: Any | None = None


def get_client() -> Any:
    global _client
    if _client is None:
        try:
            from qdrant_client import QdrantClient
        except ImportError as exc:
            raise RuntimeError("qdrant-client is required for VectorSearcher") from exc
        _client = QdrantClient(
            host=get_settings().qdrant_host,
            port=get_settings().qdrant_port,
            check_compatibility=False,
        )
    return _client


def create_collection_if_not_exists() -> None:
    from qdrant_client.models import Distance, PayloadSchemaType, VectorParams

    client = get_client()
    if client.collection_exists(COLLECTION_NAME):
        return

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    for field, schema in [
        ("project_id", PayloadSchemaType.KEYWORD),
        ("file_id", PayloadSchemaType.KEYWORD),
        ("page_number", PayloadSchemaType.INTEGER),
        ("section_header", PayloadSchemaType.KEYWORD),
        ("section_id", PayloadSchemaType.KEYWORD),
        ("section_level", PayloadSchemaType.INTEGER),
        ("parent_section_id", PayloadSchemaType.KEYWORD),
        ("chunk_index", PayloadSchemaType.INTEGER),
        ("is_table", PayloadSchemaType.BOOL),
        ("token_count", PayloadSchemaType.INTEGER),
    ]:
        client.create_payload_index(COLLECTION_NAME, field, schema)


class VectorSearcher:
    def __init__(self, client: Any | None = None) -> None:
        self.client = client or get_client()

    async def dense_search(
        self,
        vector: list[float],
        project_id: str,
        top_k: int = 150,
        file_ids: list[str] | None = None,
        section_ids: list[str] | None = None,
    ) -> list[Any]:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        def condition(key: str, values: list[str]):
            if len(values) == 1:
                return FieldCondition(key=key, match=MatchValue(value=values[0]))
            try:
                from qdrant_client.models import MatchAny

                return FieldCondition(key=key, match=MatchAny(any=values))
            except Exception:
                return FieldCondition(key=key, match=MatchValue(value=values[0]))

        must = [FieldCondition(key="project_id", match=MatchValue(value=project_id))]
        if file_ids:
            must.append(condition("file_id", file_ids[:4]))
        if section_ids:
            must.append(condition("section_id", section_ids))

        query_filter = Filter(must=must)
        if hasattr(self.client, "search"):
            return await asyncio.to_thread(
                self.client.search,
                collection_name=COLLECTION_NAME,
                query_vector=vector,
                query_filter=query_filter,
                limit=top_k,
                with_payload=True,
            )
        response = await asyncio.to_thread(
            self.client.query_points,
            collection_name=COLLECTION_NAME,
            query=vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        return response.points
