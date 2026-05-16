"""Pass 3: combined groundedness, citation, and compliance audit."""

from __future__ import annotations

from langchain_core.prompts import PromptTemplate

from app.core.llm_client import ainvoke_structured, get_llm
from app.core.schemas import AuditDecision


MASTER_AUDITOR_PROMPT = PromptTemplate.from_template(
    """You are FinSight's final blocking auditor.

Review DRAFT_ANSWER against CONTEXT and COMPLIANCE_RULES.

Pass only if all are true:
- Every factual claim is directly supported by CONTEXT or PAL_OUTPUT.
- Every factual sentence has valid [Source N] citations.
- No citation points to a missing source.
- The answer does not invent numbers, dates, names, entities, causality, or
  conclusions.
- The answer follows all block-severity compliance rules.
- Markdown tables or chart hints are acceptable only when their values are
  grounded.

If unsafe, set is_safe false and write audit_failure_reason as a short,
user-facing response. Do not expose chain-of-thought. Prefer:
"I cannot answer this based on the provided documents."

QUERY:
{query}

CONTEXT:
{context}

PAL_OUTPUT:
{pal_output}

COMPLIANCE_RULES:
{rules}

DRAFT_ANSWER:
{draft_answer}

UI_COMPONENT_HINT:
{ui_component_hint}
"""
)


class MasterAuditor:
    def __init__(self, llm=None):
        self.llm = get_llm(llm)

    async def audit(
        self,
        query: str,
        formatted_context: str,
        draft_answer: str,
        ui_component_hint: str,
        rules: str,
        pal_output: str | None = None,
    ) -> AuditDecision:
        return await ainvoke_structured(
            self.llm,
            MASTER_AUDITOR_PROMPT,
            AuditDecision,
            {
                "query": query,
                "context": formatted_context,
                "draft_answer": draft_answer,
                "ui_component_hint": ui_component_hint,
                "rules": rules or "No project-specific rules.",
                "pal_output": pal_output or "None",
            },
        )
