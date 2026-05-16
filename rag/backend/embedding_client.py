from __future__ import annotations

import asyncio
from typing import Any

from backend.config import get_settings


def _embedding_values(embedding: Any) -> list[float]:
    values = getattr(embedding, "values", embedding)
    return [float(value) for value in values]


async def embed_text(text: str, task_type: str = "RETRIEVAL_QUERY") -> list[float]:
    """Embed text with the configured provider, defaulting to Gemini."""
    settings = get_settings()
    provider = settings.ai_provider.lower().strip()

    if provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required for Gemini embeddings")

        def _embed() -> list[float]:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=settings.gemini_api_key)
            result = client.models.embed_content(
                model=settings.embedding_model,
                contents=text,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=settings.qdrant_vector_size,
                ),
            )
            return _embedding_values(result.embeddings[0])

        return await asyncio.to_thread(_embed)

    if provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when AI_PROVIDER=openai")
        from openai import AsyncOpenAI

        response = await AsyncOpenAI(api_key=settings.openai_api_key).embeddings.create(
            input=text,
            model=settings.embedding_model,
        )
        return response.data[0].embedding

    raise RuntimeError(f"Unsupported AI_PROVIDER={settings.ai_provider!r}")


async def embed_query(text: str) -> list[float]:
    return await embed_text(text, task_type="RETRIEVAL_QUERY")


async def embed_document(text: str) -> list[float]:
    return await embed_text(text, task_type="RETRIEVAL_DOCUMENT")
