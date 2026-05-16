"""PAL engine plus the consolidated FinSight RAG orchestration."""

from __future__ import annotations

import ast
import asyncio
import contextlib
import io
import math
import os
import re
import time
from dataclasses import dataclass
from typing import Literal
from typing import Any

from langchain_core.prompts import PromptTemplate

from app.core.citation_engine import (
    BoundingBoxMapper,
    CitationQueryEngine,
    build_citations_from_draft,
)
from app.core.llm_client import ainvoke_structured, get_llm, parse_json_object, response_text
from app.core.master_auditor import MasterAuditor
from app.core.proactive_generator import ProactiveGenerator
from app.core.schemas import (
    FinalResponse,
    PALCode,
    PALResult,
    RefusalResult,
    RouterDecision,
)
from app.core.smart_router import SmartRouter


PAL_PROMPT = PromptTemplate.from_template(
    """You are FinSight's proactive PAL Python code generator.

Write safe Python code that calculates useful financial insights from CONTEXT.

Rules:
- Use only numbers explicitly present in CONTEXT.
- If the user asks for an explicit calculation, compute it.
- If the query is high-level but CONTEXT has useful raw numbers, proactively
  compute helpful totals, margins, changes, growth rates, comparisons, or ranks.
- Use only built-ins and the math module.
- Print concise, human-readable outputs that can be passed to the final answer.
- Include source references in printed lines when possible, such as [Source 2].
- No markdown fences. No explanations outside code.

QUERY:
{query}

CONTEXT:
{context}
"""
)


class PALFailure(Exception):
    """Raised when PAL code generation or execution fails safely."""


@dataclass
class RouteDecision:
    route: Literal["PAL", "NARRATIVE"]
    confidence: float
    reason: str


class PALRouter:
    """Backward-compatible lightweight PAL router.

    Production routing lives in SmartRouter, which combines relevance and PAL
    routing in one structured LLM call.
    """

    def __init__(self, llm=None):
        self.llm = get_llm(llm)

    def classify(self, query: str) -> RouteDecision:
        q = query.lower()
        pal_terms = [
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
        if any(term in q for term in pal_terms):
            return RouteDecision("PAL", 0.8, "Matched quantitative keywords.")
        return RouteDecision("NARRATIVE", 0.7, "No calculation intent detected.")


class PALExecutor:
    def __init__(self, llm=None):
        self.llm = get_llm(llm)

    async def run(self, query: str, formatted_context: str | list) -> PALResult:
        if isinstance(formatted_context, list):
            formatted_context = "\n\n".join(
                f"[Source {idx}]: {getattr(chunk, 'raw_text', '')}"
                for idx, chunk in enumerate(formatted_context, start=1)
            )

        max_attempts = int(os.getenv("PAL_MAX_RETRIES", "2")) + 1
        last_error = ""

        for attempt in range(1, max_attempts + 1):
            prompt_context = formatted_context
            if last_error:
                prompt_context += (
                    "\n\nPrevious code failed. Fix the issue and keep the code safe.\n"
                    f"Error: {last_error}"
                )

            pal_code = await ainvoke_structured(
                self.llm,
                PAL_PROMPT,
                PALCode,
                {"query": query, "context": prompt_context},
            )
            code = _strip_code_fences(pal_code.code)

            try:
                result = execute_pal_code(code)
                return PALResult(
                    code=code,
                    result=result,
                    verified=True,
                    attempts=attempt,
                )
            except Exception as exc:
                last_error = str(exc)

        raise PALFailure(last_error or "PAL execution failed")


def _strip_code_fences(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:python)?\s*\n?", "", cleaned)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned)
    return cleaned.strip()


def execute_pal_code(code: str) -> str:
    """Validate and execute restricted PAL code, returning captured stdout."""
    tree = ast.parse(code)
    _validate_ast(tree)

    stdout = io.StringIO()
    safe_builtins = {
        "abs": abs,
        "all": all,
        "any": any,
        "bool": bool,
        "dict": dict,
        "enumerate": enumerate,
        "float": float,
        "int": int,
        "len": len,
        "list": list,
        "max": max,
        "min": min,
        "pow": pow,
        "print": print,
        "range": range,
        "round": round,
        "sorted": sorted,
        "str": str,
        "sum": sum,
        "tuple": tuple,
        "zip": zip,
    }
    safe_builtins["__import__"] = _safe_import
    globals_dict: dict[str, Any] = {"__builtins__": safe_builtins, "math": math}
    locals_dict: dict[str, Any] = {}

    with contextlib.redirect_stdout(stdout):
        exec(compile(tree, "<pal>", "exec"), globals_dict, locals_dict)

    output = stdout.getvalue().strip()
    if not output:
        raise PALFailure("PAL code produced no output")
    return output


def _validate_ast(tree: ast.AST) -> None:
    allowed_nodes = (
        ast.Module,
        ast.Expr,
        ast.Assign,
        ast.AnnAssign,
        ast.BinOp,
        ast.UnaryOp,
        ast.BoolOp,
        ast.Compare,
        ast.Call,
        ast.Attribute,
        ast.Import,
        ast.alias,
        ast.Name,
        ast.Load,
        ast.Store,
        ast.Constant,
        ast.List,
        ast.Tuple,
        ast.Dict,
        ast.Set,
        ast.Subscript,
        ast.Slice,
        ast.For,
        ast.If,
        ast.IfExp,
        ast.comprehension,
        ast.ListComp,
        ast.DictComp,
        ast.GeneratorExp,
        ast.Return,
        ast.FunctionDef,
        ast.arguments,
        ast.arg,
        ast.keyword,
        ast.JoinedStr,
        ast.FormattedValue,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.And,
        ast.Or,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
    )
    banned_names = {"eval", "exec", "open", "__import__", "compile", "input"}

    for node in ast.walk(tree):
        if not isinstance(node, allowed_nodes):
            raise PALFailure(f"Unsafe PAL syntax: {type(node).__name__}")
        if isinstance(node, ast.Name) and node.id in banned_names:
            raise PALFailure(f"Unsafe PAL name: {node.id}")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                if not (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "math"
                ):
                    raise PALFailure("Only math.* attribute calls are allowed")
            if isinstance(node.func, ast.Name) and node.func.id in banned_names:
                raise PALFailure(f"Unsafe PAL call: {node.func.id}")
        if isinstance(node, ast.Import):
            if any(alias.name != "math" for alias in node.names):
                raise PALFailure("Only importing math is allowed")


def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    if name == "math" and level == 0:
        return math
    raise PALFailure("Only importing math is allowed")


async def _load_rules(db_conn, project_id: str) -> str:
    if db_conn is None:
        return "Never state a number not explicitly present in the retrieved context."

    try:
        rows = await db_conn.fetch(
            "SELECT id, rule, severity FROM project_guidelines WHERE project_id = $1",
            project_id,
        )
        if not rows:
            rows = await db_conn.fetch(
                "SELECT id, rule, severity FROM default_guidelines"
            )
    except Exception:
        return "Never state a number not explicitly present in the retrieved context."

    return "\n".join(
        f"- {row['severity']}: {row['rule']} ({row['id']})"
        for row in rows
    )


async def process_query(
    query: str,
    chunks: list,
    project_id: str,
    language: str,
    llm=None,
    db_conn=None,
    qdrant_client=None,
) -> FinalResponse:
    """Run the 3-pass RAG pipeline with optional PAL between pass 1 and 2."""
    llm = get_llm(llm)
    latency: dict[str, int] = {}

    citation_engine = CitationQueryEngine()
    formatted_context, source_map = citation_engine.prepare_context_with_sources(chunks)

    t0 = time.time()
    router = SmartRouter(llm)
    route = await router.route(query, formatted_context)
    latency["smart_router_ms"] = int((time.time() - t0) * 1000)

    if not route.is_relevant:
        message = (
            "I cannot answer this based on the provided documents. "
            "Not found in the document."
        )
        return FinalResponse(
            answer_text=message,
            citations=[],
            pal_execution=None,
            refusal=RefusalResult(reason="level_3_grader", message=message),
            ui_component_hint="Paragraph",
            glean_verified=False,
            gate4_passed=False,
            latency_breakdown=latency,
        )

    pal_result: PALResult | None = None
    if route.requires_pal:
        t0 = time.time()
        try:
            pal_result = await SelfCorrectionLoop(llm).run(query, formatted_context)
        except PALFailure:
            pal_result = None
        latency["pal_ms"] = int((time.time() - t0) * 1000)

    t0 = time.time()
    generated = await ProactiveGenerator(llm).generate(
        query=query,
        formatted_context=formatted_context,
        pal_output=pal_result.result if pal_result else None,
        language=language,
    )
    latency["proactive_generator_ms"] = int((time.time() - t0) * 1000)

    citations = build_citations_from_draft(
        generated.answer_text,
        chunks,
        source_map,
    )
    mapper = BoundingBoxMapper(qdrant_client, fallback_chunks=chunks)
    citations = await mapper.resolve_all(citations)

    t0 = time.time()
    rules = await _load_rules(db_conn, project_id)
    audit = await MasterAuditor(llm).audit(
        query=query,
        formatted_context=formatted_context,
        draft_answer=generated.answer_text,
        ui_component_hint=generated.ui_component_hint,
        rules=rules,
        pal_output=pal_result.result if pal_result else None,
    )
    latency["master_auditor_ms"] = int((time.time() - t0) * 1000)

    if not audit.is_safe:
        message = (
            audit.audit_failure_reason
            or "I cannot answer this based on the provided documents."
        )
        return FinalResponse(
            answer_text=message,
            citations=[],
            pal_execution=pal_result,
            refusal=RefusalResult(reason="master_auditor", message=message),
            ui_component_hint="Paragraph",
            glean_verified=False,
            gate4_passed=False,
            latency_breakdown=latency,
        )

    return FinalResponse(
        answer_text=generated.answer_text,
        citations=citations,
        pal_execution=pal_result,
        refusal=None,
        ui_component_hint=(
            "CodeBlock"
            if pal_result is not None and generated.ui_component_hint == "Paragraph"
            else generated.ui_component_hint
        ),
        glean_verified=True,
        gate4_passed=True,
        latency_breakdown=latency,
    )


# Backward-compatible alias for older tests/imports.
SelfCorrectionLoop = PALExecutor
