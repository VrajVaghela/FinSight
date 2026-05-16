"""
reasoning_engine.py — PAL routing, code generation, symbolic execution,
self-correction loop, and the top-level process_query entry-point.
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Literal, Optional

from app.config import settings
from app.core.llm_client import create_chat_completion
from app.core.refusal_gate import Level3Gate, Level4Gate, RefusalResult  # noqa: E402


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class RouteDecision:
    route: Literal["PAL", "NARRATIVE"]
    confidence: float
    reason: str


@dataclass
class PALResult:
    code: str
    result: str
    verified: bool
    attempts: int


class PALFailure(Exception):
    """Raised when the PAL pipeline exhausts its retry budget."""
    pass


class ExecutionError(Exception):
    """Raised when sandboxed code execution fails."""
    pass


@dataclass
class FinalResponse:
    answer_text: str
    citations: list
    pal_execution: Optional[PALResult]
    refusal: Optional[RefusalResult]
    ui_component_hint: str
    glean_verified: bool
    gate4_passed: bool
    latency_breakdown: dict = field(default_factory=dict)


# ── Prompt constants ─────────────────────────────────────────────────────────

PAL_CLASSIFIER_PROMPT = """\
Classify the following financial question.
Reply with JSON only: {{"route": "PAL" or "NARRATIVE", "confidence": 0.0-1.0, "reason": "one sentence"}}

Route to PAL if the question asks for:
- A calculation (percentage, ratio, CAGR, growth rate, sum, difference)
- A numeric comparison that requires arithmetic
- Verification of a stated number

Route to NARRATIVE for:
- Descriptions, summaries, segment overviews
- Qualitative questions (why, what, who)
- Lists of items without arithmetic

Question: {query}"""


PAL_GENERATION_PROMPT = """\
You are a financial calculation assistant.
Given the CONTEXT below (extracted from a financial document) and the USER QUESTION,
write Python code that:
1. Uses ONLY the numbers that appear explicitly in the CONTEXT
2. Computes the answer to the USER QUESTION
3. Prints the final result as a formatted string (e.g., "23.5%", "₹1,234 Cr")
4. Uses only built-in Python + math module — no other imports

CONTEXT:
{numeric_context}

USER QUESTION:
{query}

Respond with ONLY the Python code. No explanation. No markdown fences."""


PAL_FIX_PROMPT = """\
The following Python code produced an error. Fix it.\
 Error: {error_message}

Code:
{code}

Respond with ONLY corrected Python code."""


# ── Helpers ──────────────────────────────────────────────────────────────────

def _strip_code_fences(text: str) -> str:
    """Remove accidental ```python … ``` fences from LLM output."""
    text = text.strip()
    text = re.sub(r"^```(?:python)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def extract_numeric_context(chunks: list) -> str:
    """Concatenate chunk texts into a numbered passage list."""
    return "\n\n".join(
        f"Passage {i}: {_chunk_text(chunk)}"
        for i, chunk in enumerate(chunks, start=1)
    )


def _chunk_text(chunk) -> str:
    if isinstance(chunk, dict):
        return str(chunk.get("raw_text", ""))
    return str(getattr(chunk, "raw_text", ""))


def infer_ui_component(query: str, pal_triggered: bool) -> str:
    """Pick the frontend component hint based on query semantics."""
    if pal_triggered:
        return "CodeBlock"
    q = query.lower()
    if any(kw in q for kw in ["trend", "over time", "quarter", "annual", "growth", "year"]):
        return "BarChart"
    if any(kw in q for kw in ["compare", "breakdown", "segment", "list", "table", "vs"]):
        return "Table"
    return "Paragraph"


def build_generation_user_prompt(
    query: str,
    formatted_context: str,
    pal_result: Optional[PALResult],
    language: str,
) -> str:
    """Build the user-role message for the generation LLM call."""
    parts: list[str] = []
    if pal_result is not None:
        parts.append(
            f"CALCULATED RESULT (use this exact value): {pal_result.result}\n"
        )
    parts.append(f"SOURCES:\n{formatted_context}\n")
    parts.append(f"QUESTION: {query}\n")
    parts.append(f"Answer in language: {language}")
    return "\n".join(parts)


# ── PALRouter ────────────────────────────────────────────────────────────────

class PALRouter:
    """Classifies an incoming query as PAL (code) or NARRATIVE (text)."""

    def __init__(self, openai_client):
        self.openai_client = openai_client

    async def classify(self, query: str) -> RouteDecision:
        model = os.getenv("GRADER_MODEL", settings.grader_model)
        prompt = PAL_CLASSIFIER_PROMPT.format(query=query)

        response = await create_chat_completion(
            self.openai_client,
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=100,
            response_format={"type": "json_object"},
        )

        try:
            data = json.loads(response.choices[0].message.content)
            return RouteDecision(
                route=data["route"],
                confidence=float(data["confidence"]),
                reason=str(data["reason"]),
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return RouteDecision(
                route="NARRATIVE",
                confidence=0.0,
                reason="parse error",
            )


# ── CodeGenerator ────────────────────────────────────────────────────────────

class CodeGenerator:
    """LLM-backed Python code generator for quantitative queries."""

    def __init__(self, openai_client):
        self.openai_client = openai_client

    async def generate(self, query: str, numeric_context: str) -> str:
        model = os.getenv("PAL_MODEL", settings.pal_model)
        prompt = PAL_GENERATION_PROMPT.format(
            query=query,
            numeric_context=numeric_context,
        )

        response = await create_chat_completion(
            self.openai_client,
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=800,
        )
        return _strip_code_fences(response.choices[0].message.content)

    async def fix(self, code: str, error_message: str) -> str:
        model = os.getenv("PAL_MODEL", settings.pal_model)
        prompt = PAL_FIX_PROMPT.format(code=code, error_message=error_message)

        response = await create_chat_completion(
            self.openai_client,
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=800,
        )
        return _strip_code_fences(response.choices[0].message.content)


# ── SymbolicExecutor ─────────────────────────────────────────────────────────

class SymbolicExecutor:
    """Runs generated code inside a restricted subprocess sandbox."""

    def execute(self, code: str) -> str:
        timeout = int(os.getenv("PAL_TIMEOUT_SECONDS", "5"))
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            raise ExecutionError(result.stderr)
        return result.stdout.strip()


# ── SelfCorrectionLoop ───────────────────────────────────────────────────────

class SelfCorrectionLoop:
    """Iteratively generates, executes, and fixes PAL code."""

    def __init__(self, openai_client):
        self.router = PALRouter(openai_client)
        self.code_generator = CodeGenerator(openai_client)
        self.executor = SymbolicExecutor()

    async def run(self, query: str, chunks: list) -> PALResult:
        numeric_context = extract_numeric_context(chunks)
        max_retries = int(os.getenv("PAL_MAX_RETRIES", "3"))
        code = None

        for attempt in range(max_retries):
            last_attempt = attempt == max_retries - 1

            # ── Generate (or re-generate on first pass) ──────────────
            if code is None:
                code = await self.code_generator.generate(query, numeric_context)

            # ── AST validation ───────────────────────────────────────
            try:
                ast.parse(code)
            except SyntaxError as exc:
                if last_attempt:
                    raise PALFailure(f"Syntax error after {attempt + 1} attempts: {exc}")
                code = await self.code_generator.fix(code, str(exc))
                continue

            # ── Sandboxed execution ──────────────────────────────────
            try:
                result = self.executor.execute(code)
            except (ExecutionError, subprocess.TimeoutExpired) as exc:
                if last_attempt:
                    raise PALFailure(f"Execution failed after {attempt + 1} attempts: {exc}")
                code = await self.code_generator.fix(code, str(exc))
                continue

            # ── Success ──────────────────────────────────────────────
            return PALResult(
                code=code,
                result=result,
                verified=True,
                attempts=attempt + 1,
            )

        raise PALFailure("Max retries exceeded")


# ── Top-level entry-point ────────────────────────────────────────────────────

async def process_query(
    query: str,
    chunks: list,
    project_id: str,
    language: str,
    openai_client,
    db_conn,
    qdrant_client,
) -> FinalResponse:
    """
    Orchestrates the full Member-4 pipeline:
    Gate-3 → PAL route → Generate → Cite → GLEAN verify → Gate-4 → respond.
    """
    from app.core.citation_engine import (
        CITATION_SYSTEM_PROMPT,
        BoundingBoxMapper,
        CitationQueryEngine,
        CitedAnswer,
        build_citations_from_draft,
    )
    from app.core.glean_verifier import VerifierGate

    latency: dict[str, int] = {}

    # ── GATE 3: LLM relevance grader ────────────────────────────────
    t0 = time.time()
    gate3 = Level3Gate(openai_client)
    grade = await gate3.check(query, chunks)
    latency["gate3_ms"] = int((time.time() - t0) * 1000)

    if not grade.relevant:
        return FinalResponse(
            answer_text="Not found in the document.",
            citations=[],
            pal_execution=None,
            refusal=RefusalResult(
                reason="level_3_grader",
                message="Not found in the document.",
            ),
            ui_component_hint="Paragraph",
            glean_verified=False,
            gate4_passed=False,
            latency_breakdown=latency,
        )

    # ── PAL ROUTER ──────────────────────────────────────────────────
    router = PALRouter(openai_client)
    route_decision = await router.classify(query)
    pal_result: Optional[PALResult] = None

    if route_decision.route == "PAL":
        t0 = time.time()
        try:
            loop = SelfCorrectionLoop(openai_client)
            pal_result = await loop.run(query, chunks)
        except PALFailure:
            pal_result = None  # fall through to narrative generation
        latency["pal_ms"] = int((time.time() - t0) * 1000)

    # ── GENERATION (premium LLM) ────────────────────────────────────
    citation_engine = CitationQueryEngine()
    formatted_context, source_map = citation_engine.prepare_context_with_sources(chunks)

    generation_messages = [
        {"role": "system", "content": CITATION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_generation_user_prompt(
                query, formatted_context, pal_result, language
            ),
        },
    ]

    gen_response = await create_chat_completion(
        openai_client,
        model=os.getenv("GENERATION_MODEL", settings.generation_model),
        messages=generation_messages,
        temperature=0.1,
        max_tokens=2000,
    )
    draft_answer = gen_response.choices[0].message.content

    # ── CITATION RESOLUTION ─────────────────────────────────────────
    citations = build_citations_from_draft(draft_answer, chunks, source_map)
    mapper = BoundingBoxMapper(qdrant_client)
    citations = await mapper.resolve_all(citations)
    cited_answer = CitedAnswer(
        text=draft_answer, citations=citations, raw_draft=draft_answer
    )

    # ── GLEAN VERIFIER (with retry loop) ────────────────────────────
    t0 = time.time()
    verifier = VerifierGate(db_conn, openai_client)
    glean_passed = False
    max_glean = int(os.getenv("GLEAN_MAX_RETRIES", "2"))

    for attempt in range(max_glean + 1):
        vr = await verifier.verify(cited_answer, chunks, project_id)
        if vr.passed:
            glean_passed = True
            break
        if attempt == max_glean:
            return FinalResponse(
                answer_text="Not found in the document.",
                citations=[],
                pal_execution=pal_result,
                refusal=RefusalResult(
                    reason="glean_verifier",
                    message="Answer failed compliance verification after multiple attempts.",
                ),
                ui_component_hint="Paragraph",
                glean_verified=False,
                gate4_passed=False,
                latency_breakdown=latency,
            )
        # Self-correct and rebuild citations
        draft_answer = await verifier.self_correct(
            cited_answer.text, vr.violations, chunks
        )
        citations = build_citations_from_draft(draft_answer, chunks, source_map)
        citations = await mapper.resolve_all(citations)
        cited_answer = CitedAnswer(
            text=draft_answer, citations=citations, raw_draft=draft_answer
        )

    latency["glean_ms"] = int((time.time() - t0) * 1000)

    # ── GATE 4: post-generation groundedness check ──────────────────
    gate4 = Level4Gate(openai_client)
    gate4_result = await gate4.check(cited_answer.text, chunks)

    if not gate4_result.passed:
        return FinalResponse(
            answer_text="Not found in the document.",
            citations=[],
            pal_execution=pal_result,
            refusal=RefusalResult(
                reason="level_4_postgen",
                message="Answer could not be verified against source documents.",
            ),
            ui_component_hint="Paragraph",
            glean_verified=True,
            gate4_passed=False,
            latency_breakdown=latency,
        )

    # ── SUCCESS ─────────────────────────────────────────────────────
    return FinalResponse(
        answer_text=cited_answer.text,
        citations=cited_answer.citations,
        pal_execution=pal_result,
        refusal=None,
        ui_component_hint=infer_ui_component(
            query, pal_triggered=(pal_result is not None)
        ),
        glean_verified=True,
        gate4_passed=True,
        latency_breakdown=latency,
    )
