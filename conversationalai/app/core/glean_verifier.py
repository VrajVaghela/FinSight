"""
glean_verifier.py — Guideline-based Enforcement with Evidence Accumulation.

Loads project-specific compliance guidelines from PostgreSQL, checks each
guideline against the generated answer with a targeted LLM call, and rejects
answers with any "block"-severity violation.  On failure the self-correction
path rewrites the answer within the retrieved context.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Literal

from app.core.llm_client import ainvoke_text, get_llm, parse_json_object

from app.core.citation_engine import CitedAnswer  # noqa: F401 — used in type hints

logger = logging.getLogger(__name__)


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class Guideline:
    id: str
    rule: str
    severity: Literal["block", "warn"]


@dataclass
class Evidence:
    guideline_id: str
    violates: bool
    detail: str
    supporting_chunk_ids: list


@dataclass
class Violation:
    guideline: Guideline
    detail: str


@dataclass
class VerificationResult:
    passed: bool
    violations: list
    evidence: list


# ── Prompt constants ─────────────────────────────────────────────────────────

GLEAN_CHECK_PROMPT = """\
You are a compliance checker for a financial AI system.

GUIDELINE: {rule}

ANSWER TO CHECK:
{answer}

RETRIEVED CONTEXT (ground truth):
{context}

Does the answer violate the guideline above?
Respond with JSON only:
{{"violated": true/false, "detail": "specific sentence that violates, or empty string"}}"""


GLEAN_BATCH_CHECK_PROMPT = """\
You are a compliance checker for a financial AI system.

GUIDELINES:
{guidelines}

ANSWER TO CHECK:
{answer}

RETRIEVED CONTEXT (ground truth):
{context}

For each guideline, decide whether the answer violates it.
Respond with JSON only:
{{"evidence": [
  {{"guideline_id": "id", "violated": true/false, "detail": "specific sentence that violates, or empty string"}}
]}}"""


SELF_CORRECTION_PROMPT = """\
The following answer was rejected because it violated compliance guidelines.

ORIGINAL ANSWER:
{draft}

VIOLATIONS FOUND:
{violations}

RETRIEVED CONTEXT (you must stay within this):
{context}

Rewrite the answer to fix all violations while keeping it accurate and citing sources."""


# ── GuidelineLoader ──────────────────────────────────────────────────────────

class GuidelineLoader:
    """Fetches compliance guidelines for a given project from PostgreSQL.

    Falls back to ``default_guidelines`` when the project has none.
    Results are cached per *project_id* for the session lifetime.
    """

    def __init__(self, db_conn):
        self.db_conn = db_conn
        self._cache: dict[str, list[Guideline]] = {}

    async def load(self, project_id: str) -> list[Guideline]:
        # Return cached guidelines if available
        if project_id in self._cache:
            return self._cache[project_id]

        # Try project-specific guidelines first
        rows = await self.db_conn.fetch(
            "SELECT id, rule, severity FROM project_guidelines WHERE project_id = $1",
            project_id,
        )

        # Fall back to defaults when no project-level rows exist
        if not rows:
            rows = await self.db_conn.fetch(
                "SELECT id, rule, severity FROM default_guidelines"
            )

        guidelines = [
            Guideline(id=row["id"], rule=row["rule"], severity=row["severity"])
            for row in rows
        ]

        self._cache[project_id] = guidelines
        return guidelines


# ── EvidenceAccumulator ──────────────────────────────────────────────────────

class EvidenceAccumulator:
    """Checks an answer against every loaded guideline via LLM calls."""

    def __init__(self, llm=None):
        self.llm = get_llm(llm)

    async def check_guideline(
        self, answer: str, guideline: Guideline, chunks: list
    ) -> Evidence:
        context = "\n".join(chunk.raw_text for chunk in chunks)
        prompt = GLEAN_CHECK_PROMPT.format(
            rule=guideline.rule,
            answer=answer,
            context=context,
        )

        response_text = await ainvoke_text(self.llm, prompt)

        try:
            data = parse_json_object(response_text)
            return Evidence(
                guideline_id=guideline.id,
                violates=bool(data["violated"]),
                detail=str(data.get("detail", "")),
                supporting_chunk_ids=[
                    getattr(c, "chunk_id", "") for c in chunks
                ],
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("GLEAN check parse error for guideline %s: %s", guideline.id, exc)
            return Evidence(
                guideline_id=guideline.id,
                violates=False,
                detail=f"parse error: {exc}",
                supporting_chunk_ids=[],
            )

    async def check_all(
        self, answer: str, guidelines: list[Guideline], chunks: list
    ) -> list[Evidence]:
        """Check all guidelines in one LLM call to stay under free-tier quota."""
        if not guidelines:
            return []
        if os.getenv("GLEAN_BATCH_CHECK", "1") != "1":
            return list(
                await asyncio.gather(
                    *(self.check_guideline(answer, g, chunks) for g in guidelines)
                )
            )

        context = "\n".join(chunk.raw_text for chunk in chunks)
        guideline_text = "\n".join(
            f"- id: {g.id}\n  severity: {g.severity}\n  rule: {g.rule}"
            for g in guidelines
        )
        prompt = GLEAN_BATCH_CHECK_PROMPT.format(
            guidelines=guideline_text,
            answer=answer,
            context=context,
        )

        response_text = await ainvoke_text(self.llm, prompt)
        guideline_ids = {g.id for g in guidelines}
        try:
            data = parse_json_object(response_text)
            if "evidence" not in data and len(guidelines) == 1:
                return [
                    Evidence(
                        guideline_id=guidelines[0].id,
                        violates=bool(data["violated"]),
                        detail=str(data.get("detail", "")),
                        supporting_chunk_ids=[
                            getattr(c, "chunk_id", "") for c in chunks
                        ],
                    )
                ]
            raw_evidence = data.get("evidence", [])
            evidence_by_id = {
                str(item["guideline_id"]): item
                for item in raw_evidence
                if str(item.get("guideline_id", "")) in guideline_ids
            }
            return [
                Evidence(
                    guideline_id=guideline.id,
                    violates=bool(evidence_by_id.get(guideline.id, {}).get("violated", False)),
                    detail=str(evidence_by_id.get(guideline.id, {}).get("detail", "")),
                    supporting_chunk_ids=[
                        getattr(c, "chunk_id", "") for c in chunks
                    ],
                )
                for guideline in guidelines
            ]
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("GLEAN batch check parse error: %s", exc)
            return [
                Evidence(
                    guideline_id=guideline.id,
                    violates=False,
                    detail=f"parse error: {exc}",
                    supporting_chunk_ids=[],
                )
                for guideline in guidelines
            ]


# ── VerifierGate ─────────────────────────────────────────────────────────────

class VerifierGate:
    """Top-level gate that orchestrates GLEAN verification."""

    def __init__(self, db_conn, llm=None):
        self.guideline_loader = GuidelineLoader(db_conn)
        self.accumulator = EvidenceAccumulator(llm)
        self.llm = get_llm(llm)

    async def verify(
        self, cited_answer: CitedAnswer, chunks: list, project_id: str
    ) -> VerificationResult:
        guidelines = await self.guideline_loader.load(project_id)
        evidences = await self.accumulator.check_all(
            cited_answer.text, guidelines, chunks
        )

        # Build a quick lookup from guideline_id → Guideline
        guideline_map = {g.id: g for g in guidelines}

        violations: list[Violation] = []
        for ev in evidences:
            if ev.violates:
                guideline = guideline_map.get(ev.guideline_id)
                if guideline and guideline.severity == "block":
                    violations.append(Violation(guideline=guideline, detail=ev.detail))

        return VerificationResult(
            passed=(len(violations) == 0),
            violations=violations,
            evidence=evidences,
        )

    async def self_correct(
        self, draft: str, violations: list[Violation], chunks: list
    ) -> str:
        violations_text = "\n".join(
            f"- Rule: {v.guideline.rule}\n  Violation: {v.detail}"
            for v in violations
        )
        context = "\n".join(chunk.raw_text for chunk in chunks)

        prompt = SELF_CORRECTION_PROMPT.format(
            draft=draft,
            violations=violations_text,
            context=context,
        )

        response_text = await ainvoke_text(self.llm, prompt)
        return response_text.strip()
