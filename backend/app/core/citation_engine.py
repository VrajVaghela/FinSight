"""
citation_engine.py — Sentence-level citation mapping, bounding-box
resolution, and context preparation for the generation step.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass

import spacy

logger = logging.getLogger(__name__)


# ── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class BoundingBox:
    x: float
    y: float
    w: float
    h: float
    page: int


@dataclass
class Citation:
    source_number: str
    chunk_id: str
    page_number: int
    section_header: str
    score: float
    bounding_box: BoundingBox
    text_snippet: str


@dataclass
class CitedAnswer:
    text: str
    citations: list
    raw_draft: str


# ── Prompt constant ──────────────────────────────────────────────────────────

CITATION_SYSTEM_PROMPT = """
You are a financial document AI. Answer ONLY using the provided sources.
If the answer cannot be deduced from the context, reply EXACTLY with: 'Not found in the document.'
When providing an answer, YOU MUST include citations in the format [pX:cY] at the end of relevant sentences.
Example: "Revenue grew 23% [p13:c2]."
If multiple sources support a claim, cite all: "... [p13:c2][p14:c1]."""



# ── CitationQueryEngine ─────────────────────────────────────────────────────

class CitationQueryEngine:
    """Prepares retrieval context with numbered source annotations and
    parses [Source N] markers from generated text."""

    def prepare_context_with_sources(self, chunks: list) -> tuple:
        """Assign pX:cY IDs to each chunk.

        Returns:
            (formatted_context, source_map)
            - formatted_context: str with "[pX:cY]: …" blocks
            - source_map: {"pX:cY": chunk_id, …}
        """
        parts: list[str] = []
        source_map: dict[str, str] = {}

        for chunk in chunks:
            page = getattr(chunk, "page_number", 0)
            cidx = getattr(chunk, "chunk_index", 0)
            marker = f"p{page}:c{cidx}"
            parts.append(f"[{marker}]: {chunk.raw_text}")
            source_map[marker] = chunk.chunk_id

        formatted_context = "\n\n".join(parts)
        return formatted_context, source_map

    def parse_source_markers(
        self, text: str, source_map: dict
    ) -> list[tuple[str, str]]:
        """Extract all ``[pX:cY]`` markers from *text*.

        Returns a deduplicated list of ``(marker, chunk_id)`` tuples.
        """
        raw_markers = re.findall(r"\[(p\d+:c\d+)\]", text)

        seen: set[str] = set()
        results: list[tuple[str, str]] = []

        for num in raw_markers:
            if num in seen:
                continue
            seen.add(num)

            if num not in source_map:
                logger.warning(
                    "Source marker [%s] not found in source_map — skipping",
                    num,
                )
                continue

            results.append((num, source_map[num]))

        return results


# ── SentenceSplitter ─────────────────────────────────────────────────────────

class SentenceSplitter:
    """Splits generated text using spaCy and maps citations per sentence."""

    def __init__(self):
        # Use a blank English pipeline with just the sentencizer.
        # spacy.load("en_core_web_sm") includes a dependency parser that
        # mis-splits sentences around symbols like "%" — a blank model
        # with the rule-based sentencizer handles citation text correctly.
        self.nlp = spacy.blank("en")
        self.nlp.add_pipe("sentencizer")

    def split(self, text: str) -> list[str]:
        """Split *text* into sentences, stripping whitespace."""
        doc = self.nlp(text)
        return [
            sent.text.strip()
            for sent in doc.sents
            if sent.text.strip()
        ]

    def map_citations_to_sentences(
        self, sentences: list[str], source_map: dict
    ) -> list[dict]:
        """For each sentence, find all [pX:cY] markers.

        Returns:
            [{"sentence": str, "source_numbers": [str, …], "chunk_ids": [str, …]}, …]
        """
        results: list[dict] = []

        for sentence in sentences:
            nums = re.findall(r"\[(p\d+:c\d+)\]", sentence)
            chunk_ids = [
                source_map[n] for n in nums if n in source_map
            ]
            results.append(
                {
                    "sentence": sentence,
                    "source_numbers": nums,
                    "chunk_ids": chunk_ids,
                }
            )

        return results


# ── BoundingBoxMapper ────────────────────────────────────────────────────────

class BoundingBoxMapper:
    """Resolves visual bounding-box coordinates for cited chunks
    by querying the Qdrant vector store."""

    def __init__(self, qdrant_client, collection_name: str | None = None):
        self.qdrant_client = qdrant_client
        self.collection = collection_name or os.getenv(
            "QDRANT_COLLECTION", "document_chunks"
        )

    async def get_bounding_box(self, chunk_id: str) -> BoundingBox:
        """Fetch the bounding box for a single chunk from Qdrant."""
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            points, _ = self.qdrant_client.scroll(
                collection_name=self.collection,
                scroll_filter=Filter(
                    must=[FieldCondition(key="chunk_id", match=MatchValue(value=chunk_id))]
                ),
                limit=1,
                with_payload=True,
                with_vectors=False,
            )

            if not points:
                logger.warning(
                    "Chunk %s not found in Qdrant collection %s",
                    chunk_id,
                    self.collection,
                )
                return BoundingBox(x=0, y=0, w=0, h=0, page=0)

            payload = points[0].payload
            bbox_data = payload.get("bounding_box")

            if bbox_data is None:
                logger.warning(
                    "Chunk %s has no bounding_box in payload", chunk_id
                )
                return BoundingBox(x=0, y=0, w=0, h=0, page=0)

            return BoundingBox(
                x=float(bbox_data["x"]),
                y=float(bbox_data["y"]),
                w=float(bbox_data["w"]),
                h=float(bbox_data["h"]),
                page=int(payload.get("page_number", 0)),
            )

        except Exception:
            logger.warning(
                "Failed to retrieve bounding box for chunk %s",
                chunk_id,
                exc_info=True,
            )
            return BoundingBox(x=0, y=0, w=0, h=0, page=0)

    async def resolve_all(self, citations: list[Citation]) -> list[Citation]:
        """Populate ``bounding_box`` on every *Citation* in the list.

        Validates that all coordinates are in [0.0, 1.0] as expected by
        Member 5's frontend (normalised percentage offsets on PDF pages).
        """
        for citation in citations:
            bbox = await self.get_bounding_box(citation.chunk_id)

            # Validate normalised coordinate range
            for coord_name in ("x", "y", "w", "h"):
                value = getattr(bbox, coord_name)
                if value < 0.0 or value > 1.0:
                    logger.warning(
                        "BoundingBox coordinate %s=%.4f for chunk %s is "
                        "outside normalised [0, 1] range",
                        coord_name,
                        value,
                        citation.chunk_id,
                    )

            citation.bounding_box = bbox

        return citations


# ── Top-level helper ─────────────────────────────────────────────────────────

def build_citations_from_draft(
    draft_answer: str,
    chunks: list,
    source_map: dict,
) -> list[Citation]:
    """Parse ``[Source N]`` markers from a draft answer and build
    :class:`Citation` objects for each referenced chunk.

    Bounding boxes are initialised to zero and should be resolved later
    via :meth:`BoundingBoxMapper.resolve_all`.
    """
    engine = CitationQueryEngine()
    markers = engine.parse_source_markers(draft_answer, source_map)

    # Build a lookup by chunk_id for fast access
    chunk_lookup: dict[str, object] = {
        chunk.chunk_id: chunk for chunk in chunks
    }

    citations: list[Citation] = []
    for source_number, chunk_id in markers:
        chunk = chunk_lookup.get(chunk_id)
        if chunk is None:
            logger.warning(
                "chunk_id %s from source_map not found in chunks list", chunk_id
            )
            continue

        citations.append(
            Citation(
                source_number=source_number,
                chunk_id=chunk_id,
                page_number=getattr(chunk, "page_number", 0),
                section_header=getattr(chunk, "section_header", ""),
                score=getattr(chunk, "reranker_score", 0.0),
                bounding_box=BoundingBox(0, 0, 0, 0, 0),
                text_snippet=chunk.raw_text[:100],
            )
        )

    return citations
