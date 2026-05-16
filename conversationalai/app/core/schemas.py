"""Shared schemas for the consolidated FinSight RAG pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional

from pydantic import BaseModel, Field


UIComponentHint = Literal["Paragraph", "Table", "BarChart", "LineChart", "CodeBlock", "MermaidDiagram"]


class RouterDecision(BaseModel):
    """Pass 1 output: document relevance plus PAL intent."""

    is_relevant: bool = Field(
        description="True only when the retrieved context can answer the query."
    )
    refusal_reason: str = Field(
        default="",
        description="Short reason to return when the answer is not in context.",
    )
    requires_pal: bool = Field(
        description="True when Python calculations would materially improve the answer."
    )


class GeneratedAnswer(BaseModel):
    """Pass 2 output: grounded answer plus UI hint."""

    answer_text: str = Field(
        description="Professional answer with inline [Source N] citations."
    )
    ui_component_hint: UIComponentHint = Field(
        default="Paragraph",
        description="Best frontend component for the answer shape.",
    )


class AuditDecision(BaseModel):
    """Pass 3 output: combined factual and compliance audit."""

    is_safe: bool = Field(
        description="True only if every claim is grounded and rules are satisfied."
    )
    audit_failure_reason: str = Field(
        default="",
        description="User-safe failure message when the draft must be rejected.",
    )


class PALCode(BaseModel):
    """Structured PAL code-generation output."""

    code: str = Field(
        description="Python code only. Must print useful calculated insights."
    )


@dataclass
class RefusalResult:
    reason: str
    message: str


@dataclass
class PALResult:
    code: str
    result: str
    verified: bool
    attempts: int


@dataclass
class FinalResponse:
    answer_text: str
    citations: list
    pal_execution: Optional[PALResult]
    refusal: Optional[RefusalResult]
    ui_component_hint: UIComponentHint
    glean_verified: bool
    gate4_passed: bool
    latency_breakdown: dict = field(default_factory=dict)
