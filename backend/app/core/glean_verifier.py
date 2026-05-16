"""
glean_verifier.py — Guideline-based Enforcement with Evidence Accumulation.

Loads project-specific compliance guidelines from PostgreSQL, checks each
guideline against the generated answer with a targeted LLM call, and rejects
answers with any "block"-severity violation.  On failure the self-correction
path rewrites the answer within the retrieved context.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from typing import Literal

from app.config import settings
from app.core.llm_client import create_chat_completion

from app.core.citation_engine import CitedAnswer  # noqa: F401 — used in type hints

logger = logging.getLogger(__name__)


def _chunk_text(chunk) -> str:
    if isinstance(chunk, dict):
        return str(chunk.get("raw_text", ""))
    return str(getattr(chunk, "raw_text", ""))


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

    def __init__(self, openai_client):
        self.openai_client = openai_client

    async def check_guideline(
        self, answer: str, guideline: Guideline, chunks: list
    ) -> Evidence:
        context = "\n".join(_chunk_text(chunk) for chunk in chunks)
        prompt = GLEAN_CHECK_PROMPT.format(
            rule=guideline.rule,
            answer=answer,
            context=context,
        )

        response = await create_chat_completion(
            self.openai_client,
            model=os.getenv("GRADER_MODEL", settings.grader_model),
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200,
            response_format={"type": "json_object"},
        )

        try:
            data = json.loads(response.choices[0].message.content)
            return Evidence(
                guideline_id=guideline.id,
                violates=bool(data["violated"]),
                detail=str(data.get("detail", "")),
                supporting_chunk_ids=[
                    getattr(c, "chunk_id", "") for c in chunks
                ],
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
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
        """Check all guidelines concurrently."""
        return list(
            await asyncio.gather(
                *(self.check_guideline(answer, g, chunks) for g in guidelines)
            )
        )


# ── VerifierGate ─────────────────────────────────────────────────────────────

class VerifierGate:
    """Top-level gate that orchestrates GLEAN verification."""

    def __init__(self, db_conn, openai_client):
        self.guideline_loader = GuidelineLoader(db_conn)
        self.accumulator = EvidenceAccumulator(openai_client)
        self.openai_client = openai_client

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
        context = "\n".join(_chunk_text(chunk) for chunk in chunks)

        prompt = SELF_CORRECTION_PROMPT.format(
            draft=draft,
            violations=violations_text,
            context=context,
        )

        response = await create_chat_completion(
            self.openai_client,
            model=os.getenv("GENERATION_MODEL", settings.generation_model),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500,
        )

        return response.choices[0].message.content.strip()
