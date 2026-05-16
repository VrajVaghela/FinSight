from __future__ import annotations

from typing import Any

from openai import AsyncOpenAI

from app.config import settings


def get_llm_client() -> AsyncOpenAI:
    """Return an OpenAI-compatible async LLM client for the configured provider."""
    provider = settings.ai_provider.lower().strip()

    if provider == "groq":
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not set")
        return AsyncOpenAI(
            api_key=settings.groq_api_key,
            base_url=settings.groq_openai_base_url,
        )

    if provider == "gemini":
        if not settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        return AsyncOpenAI(
            api_key=settings.gemini_api_key,
            base_url=settings.gemini_openai_base_url,
        )

    if provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        return AsyncOpenAI(api_key=settings.openai_api_key)

    raise RuntimeError(
        f"Unsupported AI_PROVIDER={settings.ai_provider!r}. "
        "Use 'groq', 'gemini', or 'openai'."
    )


def _should_retry_without_response_format(exc: Exception, kwargs: dict[str, Any]) -> bool:
    if "response_format" not in kwargs:
        return False

    provider = settings.ai_provider.lower().strip()
    if provider != "gemini":
        return False

    message = str(exc).lower()
    return any(
        marker in message
        for marker in ("response_format", "json", "unsupported", "invalid")
    )


async def create_chat_completion(client: AsyncOpenAI, **kwargs: Any) -> Any:
    """Create a chat completion, retrying Gemini JSON-mode calls without response_format."""
    try:
        return await client.chat.completions.create(**kwargs)
    except Exception as exc:
        if not _should_retry_without_response_format(exc, kwargs):
            raise
        retry_kwargs = dict(kwargs)
        retry_kwargs.pop("response_format", None)
        return await client.chat.completions.create(**retry_kwargs)
