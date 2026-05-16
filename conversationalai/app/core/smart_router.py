"""Pass 1: combined relevance and PAL routing."""

from __future__ import annotations

from langchain_core.prompts import PromptTemplate

from app.core.llm_client import ainvoke_structured, get_llm
from app.core.schemas import RouterDecision


SMART_ROUTER_PROMPT = PromptTemplate.from_template(
    """You are FinSight's zero-hallucination routing layer.

Decide whether the retrieved document context can answer the user's query and
whether proactive Python-assisted calculations would improve the response.

Rules:
- is_relevant is true only when the answer is directly supported by CONTEXT.
- If the user asks for facts absent from CONTEXT, set is_relevant false.
- requires_pal is true when arithmetic, ratios, totals, margins, growth, CAGR,
  variance, ranking by numeric values, or verification of a number would improve
  the answer.
- Also set requires_pal true when the query sounds high-level but CONTEXT has raw
  numbers where a concise calculated insight would make the answer more useful.
- Do not infer from outside knowledge.
- refusal_reason must be polite, brief, and specific when is_relevant is false.

QUERY:
{query}

CONTEXT:
{context}
"""
)


class SmartRouter:
    def __init__(self, llm=None):
        self.llm = get_llm(llm)

    async def route(self, query: str, formatted_context: str) -> RouterDecision:
        if not formatted_context.strip():
            return RouterDecision(
                is_relevant=False,
                refusal_reason="I cannot answer this based on the provided documents.",
                requires_pal=False,
            )

        decision = await ainvoke_structured(
            self.llm,
            SMART_ROUTER_PROMPT,
            RouterDecision,
            {"query": query, "context": formatted_context},
        )
        if decision.is_relevant and not decision.requires_pal:
            decision.requires_pal = _looks_quantitative(query)
        return decision


def _looks_quantitative(query: str) -> bool:
    q = query.lower()
    return any(
        term in q
        for term in [
            "calculate",
            "compute",
            "percentage",
            "percent",
            "%",
            "ratio",
            "cagr",
            "growth",
            "sum",
            "total",
            "difference",
            "increase",
            "decrease",
            "verify",
        ]
    )
