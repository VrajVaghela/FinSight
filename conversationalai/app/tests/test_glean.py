"""Tests for the GLEAN verifier."""

from __future__ import annotations

import json
from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest

from app.core.citation_engine import CitedAnswer
from app.core.glean_verifier import Guideline, GuidelineLoader, Violation, VerifierGate


@dataclass
class _FakeChunk:
    chunk_id: str
    raw_text: str


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


BLOCK_GUIDELINE = Guideline(
    id="g1",
    rule="Never state a number not in retrieved context",
    severity="block",
)


def _mock_llm(text: str) -> _FakeLLM:
    return _FakeLLM([text])


def _mock_db_conn(project_rows, default_rows=None):
    conn = AsyncMock()
    if default_rows is not None:
        conn.fetch = AsyncMock(side_effect=[project_rows, default_rows])
    else:
        conn.fetch = AsyncMock(return_value=project_rows)
    return conn


@pytest.mark.asyncio
async def test_verifier_rejects_hallucinated_number():
    llm = _mock_llm(
        json.dumps({"violated": True, "detail": "CEO earned Rs 5 Cr bonus not in context"})
    )
    db_conn = _mock_db_conn(
        project_rows=[{"id": "g1", "rule": BLOCK_GUIDELINE.rule, "severity": "block"}]
    )

    gate = VerifierGate(db_conn=db_conn, llm=llm)
    bad_answer = CitedAnswer(
        text="The CEO earned Rs 5 Cr bonus [Source 1].",
        citations=[],
        raw_draft="",
    )
    chunks = [_FakeChunk(chunk_id="c1", raw_text="Revenue was Rs 1,234 Cr")]

    result = await gate.verify(bad_answer, chunks, project_id="test-project")

    assert result.passed is False
    assert len(result.violations) > 0


@pytest.mark.asyncio
async def test_verifier_passes_grounded_answer():
    llm = _mock_llm(json.dumps({"violated": False, "detail": ""}))
    db_conn = _mock_db_conn(
        project_rows=[{"id": "g1", "rule": BLOCK_GUIDELINE.rule, "severity": "block"}]
    )

    gate = VerifierGate(db_conn=db_conn, llm=llm)
    good_answer = CitedAnswer(
        text="Revenue for H1-FY26 was Rs 1,234 Cr [Source 1].",
        citations=[],
        raw_draft="",
    )
    chunks = [_FakeChunk(chunk_id="c1", raw_text="Revenue for H1-FY26 was Rs 1,234 Cr")]

    result = await gate.verify(good_answer, chunks, project_id="test-project")

    assert result.passed is True


@pytest.mark.asyncio
async def test_self_correct_calls_llm_with_violation_details():
    corrected_text = "Corrected answer text with proper citations."
    llm = _mock_llm(corrected_text)
    db_conn = AsyncMock()

    gate = VerifierGate(db_conn=db_conn, llm=llm)
    violation = Violation(
        guideline=BLOCK_GUIDELINE,
        detail="CEO earned Rs 5 Cr bonus not in context",
    )
    chunks = [_FakeChunk(chunk_id="c1", raw_text="Revenue was Rs 1,234 Cr")]

    result = await gate.self_correct(
        draft="bad text", violations=[violation], chunks=chunks
    )

    assert result == corrected_text
    assert "VIOLATIONS" in llm.prompts[0]


@pytest.mark.asyncio
async def test_guideline_loader_falls_back_to_defaults():
    default_rows = [
        {"id": "d1", "rule": "Always cite sources", "severity": "block"},
        {"id": "d2", "rule": "Use formal tone", "severity": "warn"},
    ]
    db_conn = _mock_db_conn(project_rows=[], default_rows=default_rows)

    loader = GuidelineLoader(db_conn=db_conn)
    guidelines = await loader.load("nonexistent-project-id")

    assert len(guidelines) == 2
    assert guidelines[0].id == "d1"
    assert guidelines[1].id == "d2"
