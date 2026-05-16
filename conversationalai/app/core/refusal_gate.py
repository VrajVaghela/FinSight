"""
refusal_gate.py — Pre-generation (Level-3) and post-generation (Level-4)
safety / relevance gates that decide whether to refuse a query.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from app.core.llm_client import ainvoke_text, get_llm, parse_json_object


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class GradeResult:
    relevant: bool
    reason: str
    confidence: float


@dataclass
class PostGenResult:
    passed: bool
    violations: list
    grounded_sentences: int
    total_sentences: int


@dataclass
class RefusalResult:
    reason: str
    message: str


# ── Prompts ──────────────────────────────────────────────────────────────────

LEVEL3_PROMPT = """\
You are a document relevance checker.
Given the QUERY and RETRIEVED PASSAGES, determine if the passages contain
sufficient information to answer the query accurately.

QUERY: {query}

RETRIEVED PASSAGES:
{passages}

Respond with JSON only:
{{"relevant": true/false, "reason": "one sentence explanation", "confidence": 0.0 to 1.0}}"""


LEVEL4_PROMPT = """\
You are a fact-grounding auditor for a financial AI system.

FINAL ANSWER:
{answer}

RETRIEVED SOURCES:
{sources}

For each factual claim in the answer, check if it is supported by the sources.
Respond with JSON only:
{{
  "passed": true/false,
  "violations": ["claim that is not grounded", ...],
  "grounded_count": N,
  "total_claims": N
}}"""


# ── Level-3 gate implementation ─────────────────────────────────────────────

class Level3Gate:
    """Pre-generation relevance gate — rejects off-topic queries early."""

    def __init__(self, llm=None):
        self.llm = get_llm(llm)

    async def check(self, query: str, chunks: list) -> GradeResult:
        # Fast-exit when no context was retrieved
        if not chunks:
            return GradeResult(
                relevant=False,
                reason="No context retrieved",
                confidence=0.0,
            )

        # Format numbered passage list
        passages = "\n\n".join(
            f"Passage {i}:\n{chunk.raw_text}"
            for i, chunk in enumerate(chunks, start=1)
        )

        prompt = LEVEL3_PROMPT.format(query=query, passages=passages)

        # LLM call
        response_text = await ainvoke_text(self.llm, prompt)

        # Parse response
        try:
            data = parse_json_object(response_text)
            result = GradeResult(
                relevant=bool(data["relevant"]),
                reason=str(data["reason"]),
                confidence=float(data["confidence"]),
            )
        except (KeyError, TypeError, ValueError):
            return GradeResult(
                relevant=False,
                reason="Grader parse error",
                confidence=0.0,
            )

        # Confidence threshold override
        threshold = float(os.getenv("GATE3_CONFIDENCE_THRESHOLD", "0.5"))
        if result.confidence < threshold:
            result.relevant = False

        return result


# ── Level-4 gate implementation ──────────────────────────────────────────────

class Level4Gate:
    """Post-generation groundedness gate — ensures every factual claim in the
    answer is supported by at least one retrieved chunk."""

    def __init__(self, llm=None):
        self.llm = get_llm(llm)

    async def check(self, final_answer: str, chunks: list) -> PostGenResult:
        # Build numbered source list
        sources = "\n".join(
            f"Source {i}: {chunk.raw_text}"
            for i, chunk in enumerate(chunks, start=1)
        )

        prompt = LEVEL4_PROMPT.format(answer=final_answer, sources=sources)

        response_text = await ainvoke_text(self.llm, prompt)

        try:
            data = parse_json_object(response_text)
            grounded = int(data["grounded_count"])
            total = int(data["total_claims"])
            violations = list(data.get("violations", []))
            passed = bool(data["passed"])
        except (KeyError, TypeError, ValueError):
            return PostGenResult(
                passed=False,
                violations=["Gate-4 parse error"],
                grounded_sentences=0,
                total_sentences=0,
            )

        # Override pass decision based on grounding ratio threshold
        ratio = grounded / max(total, 1)
        min_ratio = float(os.getenv("GATE4_MIN_GROUNDED_RATIO", "0.8"))
        if ratio < min_ratio:
            passed = False

        return PostGenResult(
            passed=passed,
            violations=violations,
            grounded_sentences=grounded,
            total_sentences=total,
        )
