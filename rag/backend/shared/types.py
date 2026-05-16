from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class BoundingBox:
    x: float
    y: float
    w: float
    h: float

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "BoundingBox":
        data = payload or {}
        return cls(
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            w=float(data.get("w", 0.0)),
            h=float(data.get("h", 0.0)),
        )


@dataclass(slots=True)
class RetrievedChunk:
    chunk_id: str
    project_id: str
    file_id: str
    page_number: int
    chunk_index: int
    section_header: str
    raw_text: str
    context_summary: str
    is_table: bool
    table_html: Optional[str]
    bounding_box: BoundingBox
    similarity_score: float = 0.0
    rrf_score: float = 0.0
    reranker_score: float = 0.0
    section_id: Optional[str] = None
    section_level: Optional[int] = None
    parent_section_id: Optional[str] = None
    source_file_id: Optional[str] = None

    @classmethod
    def from_qdrant_payload(
        cls,
        chunk_id: str,
        payload: dict[str, Any],
        *,
        similarity_score: float = 0.0,
        rrf_score: float = 0.0,
    ) -> "RetrievedChunk":
        return cls(
            chunk_id=str(chunk_id),
            project_id=str(payload.get("project_id", "")),
            file_id=str(payload.get("file_id", "")),
            page_number=int(payload.get("page_number", 0) or 0),
            chunk_index=int(payload.get("chunk_index", 0) or 0),
            section_header=str(payload.get("section_header", "")),
            raw_text=str(payload.get("raw_text", "")),
            context_summary=str(payload.get("context_summary", "")),
            is_table=bool(payload.get("is_table", False)),
            table_html=payload.get("table_html"),
            bounding_box=BoundingBox.from_payload(payload.get("bounding_box")),
            similarity_score=float(similarity_score or 0.0),
            rrf_score=float(rrf_score or 0.0),
            section_id=payload.get("section_id"),
            section_level=int(payload["section_level"]) if payload.get("section_level") is not None else None,
            parent_section_id=payload.get("parent_section_id"),
            source_file_id=payload.get("source_file_id") or payload.get("file_id"),
        )

    def dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RetrievalResult:
    chunks: list[RetrievedChunk]
    gate1_score: float
    gate2_score: float
    retrieval_ms: int
    debug: dict[str, Any] = field(default_factory=dict)

    def dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RefusalEvent:
    level: int
    reason: str
    message: str = "Not found in the document."
    debug: dict[str, Any] = field(default_factory=dict)

    def dict(self) -> dict[str, Any]:
        return asdict(self)
