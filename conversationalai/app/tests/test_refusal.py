"""Tests for refusal gates and process_query acceptance paths."""

from __future__ import annotations

import json
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.refusal_gate import Level3Gate
from app.core.reasoning_engine import PALResult, process_query


@dataclass
class _FakeChunk:
    chunk_id: str = "uuid-1"
    raw_text: str = "placeholder"
    page_number: int = 1
    section_header: str = "Section"
    reranker_score: float = 0.9


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content


class _FakeLLM:
    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.prompts: list[str] = []

    def _next(self, prompt: str) -> _FakeMessage:
        self.prompts.append(prompt)
        return _FakeMessage(self.responses.pop(0))

    def invoke(self, prompt: str) -> _FakeMessage:
        return self._next(prompt)

    async def ainvoke(self, prompt: str) -> _FakeMessage:
        return self._next(prompt)


def _mock_llm_response(payload: dict) -> _FakeLLM:
    return _FakeLLM([json.dumps(payload)])


@pytest.mark.asyncio
async def test_should_return_relevant_true_when_context_matches():
    chunk = _FakeChunk(raw_text="Total income for H1-FY26 was Rs 1,234 Cr")
    llm = _mock_llm_response(
        {"relevant": True, "reason": "Context contains matching figures", "confidence": 0.95}
    )

    gate = Level3Gate(llm=llm)
    result = await gate.check(query="What was H1-FY26 income?", chunks=[chunk])

    assert result.relevant is True


@pytest.mark.asyncio
async def test_should_return_relevant_false_for_ceo_email():
    chunk = _FakeChunk(raw_text="Revenue grew by 23% YoY")
    llm = _mock_llm_response(
        {"relevant": False, "reason": "No email address in context", "confidence": 0.02}
    )

    gate = Level3Gate(llm=llm)
    result = await gate.check(query="What is the CEO's email?", chunks=[chunk])

    assert result.relevant is False
    assert result.reason


@pytest.mark.asyncio
async def test_t2_numeric_question_triggers_pal():
    chunks = [_FakeChunk(chunk_id="c1", raw_text="Total income H1-FY26 Rs 1,234 Cr")]

    llm = _FakeLLM([
        json.dumps({"relevant": True, "reason": "matches", "confidence": 0.99}),
        "The consolidated total income in H1-FY26 was Rs 1,234 Cr [Source 1].",
        json.dumps({"violated": False, "detail": ""}),
        json.dumps({"passed": True, "violations": [], "grounded_count": 1, "total_claims": 1}),
    ])

    with patch(
        "app.core.reasoning_engine.PALRouter.classify",
        return_value=MagicMock(route="PAL", confidence=0.95, reason="needs calc"),
    ), patch(
        "app.core.reasoning_engine.SelfCorrectionLoop.run",
        new_callable=AsyncMock,
        return_value=PALResult(
            code="print('Rs 1,234 Cr')",
            result="Rs 1,234 Cr",
            verified=True,
            attempts=1,
        ),
    ):
        db_conn = AsyncMock()
        db_conn.fetch = AsyncMock(return_value=[
            {"id": "g1", "rule": "no hallucination", "severity": "block"}
        ])

        qdrant_client = MagicMock()
        qdrant_client.retrieve = MagicMock(return_value=[])

        response = await process_query(
            query="What is the consolidated total income in H1-26?",
            chunks=chunks,
            project_id="test",
            language="English",
            llm=llm,
            db_conn=db_conn,
            qdrant_client=qdrant_client,
        )

    assert response.pal_execution is not None
    assert response.refusal is None
    assert response.ui_component_hint == "CodeBlock"


@pytest.mark.asyncio
async def test_t4_ceo_email_returns_refusal():
    chunks = [_FakeChunk(raw_text="Revenue grew by 23% YoY")]
    llm = _mock_llm_response(
        {"relevant": False, "reason": "No email in document", "confidence": 0.02}
    )

    response = await process_query(
        query="What is the CEO's email address?",
        chunks=chunks,
        project_id="test",
        language="English",
        llm=llm,
        db_conn=AsyncMock(),
        qdrant_client=MagicMock(),
    )

    assert response.refusal is not None
    assert response.refusal.reason == "level_3_grader"
    assert "Not found" in response.answer_text
