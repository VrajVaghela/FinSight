"""
test_citation.py — Tests for the citation engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from app.core.citation_engine import (
    BoundingBoxMapper,
    CitationQueryEngine,
    SentenceSplitter,
)


# ── Helper: lightweight chunk stand-in ───────────────────────────────────────

@dataclass
class _FakeChunk:
    chunk_id: str
    raw_text: str
    page_number: int = 1
    bounding_box: dict | None = None


# ── Test A — prepare_context_with_sources ────────────────────────────────────

def test_prepare_context_formats_chunks_correctly():
    chunks = [
        _FakeChunk(chunk_id="uuid-1", raw_text="Revenue grew 23%"),
        _FakeChunk(chunk_id="uuid-2", raw_text="EBITDA margin was 18%"),
    ]
    engine = CitationQueryEngine()
    formatted, source_map = engine.prepare_context_with_sources(chunks)

    assert "[Source 1]:" in formatted
    assert "[Source 2]:" in formatted
    assert "Revenue grew 23%" in formatted
    assert "EBITDA margin was 18%" in formatted
    assert source_map == {1: "uuid-1", 2: "uuid-2"}


# ── Test B — SentenceSplitter ────────────────────────────────────────────────

def test_sentence_splitter_splits_correctly():
    splitter = SentenceSplitter()
    text = "Revenue grew 23% [Source 1]. EBITDA improved [Source 2]."
    sentences = splitter.split(text)

    assert len(sentences) == 2
    assert "[Source 1]" in sentences[0]


# ── Test C — BoundingBoxMapper with mocked Qdrant ───────────────────────────

@dataclass
class _MockPoint:
    payload: dict


@pytest.mark.asyncio
async def test_bounding_box_mapper_returns_correct_bbox():
    mock_point = _MockPoint(
        payload={
            "bounding_box": {"x": 0.1, "y": 0.3, "w": 0.8, "h": 0.05},
            "page_number": 3,
        }
    )
    mock_qdrant = MagicMock()
    mock_qdrant.retrieve = MagicMock(return_value=[mock_point])

    mapper = BoundingBoxMapper(qdrant_client=mock_qdrant)
    bbox = await mapper.get_bounding_box("some-uuid")

    assert bbox.x == 0.1
    assert bbox.y == 0.3
    assert bbox.w == 0.8
    assert bbox.h == 0.05
    assert bbox.page == 3

    # Validate normalised range [0, 1]
    assert 0 <= bbox.x <= 1
    assert 0 <= bbox.y <= 1
    assert 0 <= bbox.w <= 1
    assert 0 <= bbox.h <= 1


@pytest.mark.asyncio
async def test_bounding_box_mapper_falls_back_to_chunk_bbox_when_qdrant_misses():
    chunk = _FakeChunk(
        chunk_id="revenue-fy26",
        raw_text="Revenue in FY26 was Rs 1,400 Cr.",
        page_number=5,
        bounding_box={"x": 0.2, "y": 0.4, "w": 0.5, "h": 0.06},
    )
    mock_qdrant = MagicMock()
    mock_qdrant.retrieve = MagicMock(return_value=[])

    mapper = BoundingBoxMapper(
        qdrant_client=mock_qdrant,
        fallback_chunks=[chunk],
    )
    bbox = await mapper.get_bounding_box("revenue-fy26")

    assert bbox.x == 0.2
    assert bbox.y == 0.4
    assert bbox.w == 0.5
    assert bbox.h == 0.06
    assert bbox.page == 5


@pytest.mark.asyncio
async def test_bounding_box_mapper_returns_zero_box_for_local_missing_chunk():
    mock_qdrant = MagicMock()
    mock_qdrant.retrieve = MagicMock(return_value=[])

    mapper = BoundingBoxMapper(qdrant_client=mock_qdrant)
    bbox = await mapper.get_bounding_box("revenue-fy26")

    assert bbox.x == 0
    assert bbox.y == 0
    assert bbox.w == 0
    assert bbox.h == 0
    assert bbox.page == 0
