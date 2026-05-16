"""Local FastAPI harness for Member 4's Conversational AI pipeline."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    pass

from app.core.reasoning_engine import process_query


class RetrievedChunk(BaseModel):
    chunk_id: str
    raw_text: str
    page_number: int = 1
    section_header: str = ""
    reranker_score: float = 1.0
    bounding_box: dict[str, float] | None = None


class ChatRequest(BaseModel):
    query: str
    project_id: str
    language: str = "English"
    session_id: str | None = None
    chunks: list[RetrievedChunk] = Field(default_factory=list)


class _DefaultGuidelineDB:
    async def fetch(self, sql: str, *args):
        if "project_guidelines" in sql:
            return []
        return [
            {
                "id": "default-never-invent-numbers",
                "rule": "Never state a number not explicitly present in the retrieved context.",
                "severity": "block",
            },
            {
                "id": "default-source-required",
                "rule": "Every factual claim must be supported by the retrieved context.",
                "severity": "block",
            },
        ]


class _NullQdrantClient:
    def retrieve(self, *args, **kwargs):
        return []


def _jsonable(value: Any):
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, default=str)}\n\n"


app = FastAPI(title="FinSight Conversational AI")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    async def stream():
        yield _sse({"type": "started", "session_id": request.session_id})

        try:
            response = await process_query(
                query=request.query,
                chunks=request.chunks,
                project_id=request.project_id,
                language=request.language,
                db_conn=_DefaultGuidelineDB(),
                qdrant_client=_NullQdrantClient(),
            )
        except Exception as exc:
            yield _sse({"type": "error", "message": str(exc)})
            yield _sse({"type": "done"})
            return

        if response.pal_execution is not None:
            yield _sse(
                {
                    "type": "pal_execution",
                    **_jsonable(response.pal_execution),
                }
            )

        for citation in response.citations:
            yield _sse({"type": "chunk", **_jsonable(citation)})

        if response.refusal is not None:
            yield _sse({"type": "refusal", **_jsonable(response.refusal)})
        else:
            yield _sse(
                {
                    "type": "answer",
                    "text": response.answer_text,
                    "ui_component_hint": response.ui_component_hint,
                    "citations": _jsonable(response.citations),
                    "glean_verified": response.glean_verified,
                    "gate4_passed": response.gate4_passed,
                }
            )

        yield _sse({"type": "done", "latency": response.latency_breakdown})

    return StreamingResponse(stream(), media_type="text/event-stream")
