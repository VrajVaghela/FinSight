from __future__ import annotations

from typing import Any

from backend.config import get_settings
from backend.shared.types import RefusalEvent, RetrievedChunk


class RefusalGate:
    @staticmethod
    def gate1_threshold() -> float:
        return get_settings().gate1_threshold

    @staticmethod
    def gate2_threshold() -> float:
        return get_settings().gate2_threshold

    @classmethod
    def check_threshold(cls, dense_hits: list[Any], threshold: float | None = None) -> RefusalEvent | None:
        threshold = cls.gate1_threshold() if threshold is None else threshold
        max_similarity = float(dense_hits[0].score) if dense_hits else 0.0
        if max_similarity < threshold:
            return RefusalEvent(
                level=1,
                reason="level_1_threshold",
                debug={
                    "max_similarity": round(max_similarity, 4),
                    "threshold": threshold,
                },
            )
        return None

    @classmethod
    def check_reranker(
        cls,
        reranked: list[RetrievedChunk],
        threshold: float | None = None,
    ) -> RefusalEvent | None:
        threshold = cls.gate2_threshold() if threshold is None else threshold
        top_score = float(reranked[0].reranker_score) if reranked else 0.0
        if top_score < threshold:
            return RefusalEvent(
                level=2,
                reason="level_2_reranker",
                debug={
                    "reranker_score": round(top_score, 4),
                    "threshold": threshold,
                },
            )
        return None
