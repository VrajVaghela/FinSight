from __future__ import annotations

import asyncio
from threading import Lock
from typing import Any

from backend.config import get_settings
from backend.shared.types import RetrievedChunk


_model: Any | None = None
_model_lock = Lock()


def _get_model() -> Any:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                try:
                    from sentence_transformers import CrossEncoder
                except ImportError as exc:
                    raise RuntimeError("sentence-transformers is required for NeuralReranker") from exc
                _model = CrossEncoder(get_settings().reranker_model)
    return _model


def is_model_loaded() -> bool:
    return _model is not None


class NeuralReranker:
    _instance: "NeuralReranker | None" = None
    _lock = Lock()

    def __init__(self, model_name: str | None = None, model: Any | None = None) -> None:
        self.model_name = model_name or get_settings().reranker_model
        self.model = model

    @classmethod
    def get(cls) -> "NeuralReranker":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def set_for_tests(cls, instance: "NeuralReranker | None") -> None:
        cls._instance = instance

    async def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        if not chunks:
            return []

        limit = top_k or get_settings().reranker_top_k
        model = self.model or _get_model()
        pairs = [(query, chunk.raw_text) for chunk in chunks]
        scores = await asyncio.to_thread(model.predict, pairs)
        if hasattr(scores, "tolist"):
            scores = scores.tolist()

        for chunk, score in zip(chunks, scores):
            chunk.reranker_score = float(score)

        ranked = sorted(chunks, key=lambda chunk: chunk.reranker_score, reverse=True)
        return ranked[:limit]
