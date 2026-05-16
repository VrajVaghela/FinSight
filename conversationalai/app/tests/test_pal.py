"""Tests for PAL routing and self-correction loop."""

from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass

import pytest

from app.core.reasoning_engine import PALRouter, SelfCorrectionLoop


@dataclass
class _FakeChunk:
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


def _mock_sync_llm(payload: dict) -> _FakeLLM:
    return _FakeLLM([json.dumps(payload)])


def _mock_async_llm(payload_or_text) -> _FakeLLM:
    text = payload_or_text if isinstance(payload_or_text, str) else json.dumps(payload_or_text)
    return _FakeLLM([text])


def test_pal_router_classifies_calculation_as_pal():
    llm = _mock_sync_llm(
        {"route": "PAL", "confidence": 0.95, "reason": "needs CAGR calc"}
    )
    router = PALRouter(llm=llm)
    decision = router.classify("What is the CAGR from FY22 to FY26?")

    assert decision.route == "PAL"


def test_pal_router_classifies_narrative_as_narrative():
    llm = _mock_sync_llm(
        {"route": "NARRATIVE", "confidence": 0.88, "reason": "qualitative question"}
    )
    router = PALRouter(llm=llm)
    decision = router.classify("What are the major business segments?")

    assert decision.route == "NARRATIVE"


CAGR_CODE = textwrap.dedent("""\
    import math
    revenue_fy22 = 800
    revenue_fy26 = 1400
    n = 4
    cagr = (revenue_fy26 / revenue_fy22) ** (1/n) - 1
    print(f"{cagr*100:.1f}%")
""")


@pytest.mark.asyncio
async def test_self_correction_loop_computes_cagr():
    llm = _mock_async_llm(CAGR_CODE)
    loop = SelfCorrectionLoop(llm=llm)

    chunks = [
        _FakeChunk(raw_text="Revenue FY22 Rs 800 Cr"),
        _FakeChunk(raw_text="Revenue FY26 Rs 1400 Cr"),
    ]
    result = await loop.run("What was the CAGR?", chunks)

    assert result.verified is True
    assert "15" in result.result or "14" in result.result


BROKEN_CODE = "def broken(: pass"
FIXED_CODE = 'print("42")'


@pytest.mark.asyncio
async def test_ast_parse_failure_triggers_fix_and_retry():
    llm = _FakeLLM([BROKEN_CODE, FIXED_CODE])
    loop = SelfCorrectionLoop(llm=llm)

    chunks = [_FakeChunk(raw_text="Revenue is 100")]
    result = await loop.run("What is the revenue?", chunks)

    assert result.verified is True
    assert result.attempts == 2
