from __future__ import annotations

from dataclasses import dataclass

from app.config import get_settings
from app.shared.types import RetrievedChunk


NUMERIC_TERMS = {
    "revenue",
    "income",
    "ebitda",
    "cagr",
    "growth",
    "growth %",
    "margin",
    "pat",
    "cash flow",
    "debt",
}
PERSONAL_INFO_TERMS = {"email", "phone", "address", "home", "mobile", "linkedin"}
FOLLOW_UP_TERMS = {"it", "that", "this", "those", "they", "them"}
SPECULATIVE_TERMS = {"will", "future", "predict", "next year", "forecast", "should i"}


@dataclass(slots=True)
class ThresholdDecision:
    threshold: float
    base_threshold: float
    adjustments: list[dict[str, float | str]]


class DynamicThreshold:
    @staticmethod
    def _contains(query: str, terms: set[str]) -> bool:
        normalized = query.lower()
        return any(term in normalized for term in terms)

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, value))

    @classmethod
    def adjust_gate1(cls, query: str, dense_hits: list) -> ThresholdDecision:
        settings = get_settings()
        base = settings.gate1_threshold
        threshold = base
        adjustments: list[dict[str, float | str]] = []

        if not settings.dynamic_thresholds_enabled:
            return ThresholdDecision(base, base, adjustments)

        if cls._contains(query, NUMERIC_TERMS):
            threshold += settings.gate1_numeric_delta
            adjustments.append({"reason": "numeric_query", "delta": settings.gate1_numeric_delta})
        if len(query.split()) < 4:
            threshold += settings.gate1_short_query_delta
            adjustments.append({"reason": "short_query", "delta": settings.gate1_short_query_delta})
        if cls._contains(query, PERSONAL_INFO_TERMS):
            threshold += settings.gate1_personal_info_delta
            adjustments.append({"reason": "personal_info", "delta": settings.gate1_personal_info_delta})

        return ThresholdDecision(cls._clamp(threshold), base, adjustments)

    @classmethod
    def adjust_gate2(cls, query: str, reranked: list[RetrievedChunk]) -> ThresholdDecision:
        settings = get_settings()
        base = settings.gate2_threshold
        threshold = base
        adjustments: list[dict[str, float | str]] = []

        if not settings.dynamic_thresholds_enabled:
            return ThresholdDecision(base, base, adjustments)

        if reranked and reranked[0].is_table:
            threshold += settings.gate2_table_delta
            adjustments.append({"reason": "top_chunk_is_table", "delta": settings.gate2_table_delta})
        if cls._contains(query, FOLLOW_UP_TERMS):
            threshold += settings.gate2_followup_delta
            adjustments.append({"reason": "follow_up_query", "delta": settings.gate2_followup_delta})
        if cls._contains(query, SPECULATIVE_TERMS):
            threshold += settings.gate2_speculative_delta
            adjustments.append({"reason": "speculative_query", "delta": settings.gate2_speculative_delta})

        return ThresholdDecision(cls._clamp(threshold), base, adjustments)
