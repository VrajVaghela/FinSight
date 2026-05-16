from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any

from backend.config import get_settings
from backend.shared.types import RefusalEvent, RetrievalResult


_write_lock = Lock()


def vector_hash(vector: list[float]) -> str:
    digest = hashlib.sha256()
    digest.update(",".join(f"{value:.8f}" for value in vector).encode("utf-8"))
    return digest.hexdigest()


@dataclass(slots=True)
class QueryLogEntry:
    query_id: str
    timestamp: str
    project_id: str
    conversation_id: str | None
    query_text: str
    query_vector_hash: str
    standalone_query: str | None
    retrieval_result_type: str
    gate1_score: float
    gate2_score: float
    gate_fired: str | None
    chunks_retrieved: int
    top_chunk_ids: list[str]
    retrieval_ms: int
    bm25_hit_count: int
    dense_hit_count: int
    rrf_k: int
    reranker_model: str
    user_id: str | None
    gate1_base_threshold: float
    gate1_threshold: float
    gate2_base_threshold: float
    gate2_threshold: float
    gate1_adjustments: list[dict[str, Any]]
    gate2_adjustments: list[dict[str, Any]]


class QueryLogger:
    def __init__(self, db_session: Any | None = None, log_path: str | None = None) -> None:
        self.db_session = db_session
        self.log_path = Path(log_path or get_settings().query_log_path)

    def build_entry(
        self,
        *,
        query: str,
        query_vector: list[float],
        project_id: str,
        result: RetrievalResult | RefusalEvent,
        conversation_id: str | None = None,
        user_id: str | None = None,
        standalone_query: str | None = None,
        gate1_threshold: float | None = None,
        gate2_threshold: float | None = None,
        gate1_adjustments: list[dict[str, Any]] | None = None,
        gate2_adjustments: list[dict[str, Any]] | None = None,
    ) -> QueryLogEntry:
        settings = get_settings()
        debug = result.debug
        if isinstance(result, RetrievalResult):
            gate_fired = None
            gate1_score = result.gate1_score
            gate2_score = result.gate2_score
            chunks_retrieved = len(result.chunks)
            top_chunk_ids = [chunk.chunk_id for chunk in result.chunks[:5]]
            retrieval_ms = result.retrieval_ms
        else:
            gate_fired = f"L{result.level}"
            gate1_score = float(debug.get("gate_1", {}).get("max_similarity", debug.get("max_similarity", 0.0)))
            gate2_score = float(debug.get("gate_2", {}).get("reranker_score", debug.get("reranker_score", 0.0)))
            chunks_retrieved = 0
            top_chunk_ids = []
            retrieval_ms = int(debug.get("retrieval_ms", debug.get("latency_ms", 0)))

        return QueryLogEntry(
            query_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            project_id=project_id,
            conversation_id=conversation_id,
            query_text=query,
            query_vector_hash=vector_hash(query_vector),
            standalone_query=standalone_query,
            retrieval_result_type=type(result).__name__,
            gate1_score=float(gate1_score),
            gate2_score=float(gate2_score),
            gate_fired=gate_fired,
            chunks_retrieved=chunks_retrieved,
            top_chunk_ids=top_chunk_ids,
            retrieval_ms=int(retrieval_ms),
            bm25_hit_count=len(debug.get("bm25_hits", [])),
            dense_hit_count=len(debug.get("dense_hits", [])),
            rrf_k=settings.rrf_k,
            reranker_model=settings.reranker_model,
            user_id=user_id,
            gate1_base_threshold=settings.gate1_threshold,
            gate1_threshold=gate1_threshold if gate1_threshold is not None else settings.gate1_threshold,
            gate2_base_threshold=settings.gate2_threshold,
            gate2_threshold=gate2_threshold if gate2_threshold is not None else settings.gate2_threshold,
            gate1_adjustments=gate1_adjustments or [],
            gate2_adjustments=gate2_adjustments or [],
        )

    async def log_query(self, **kwargs: Any) -> None:
        entry = self.build_entry(**kwargs)
        await asyncio.to_thread(self._write_entry, entry)

    def enqueue(self, **kwargs: Any) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        loop.create_task(self.log_query(**kwargs))

    def _write_entry(self, entry: QueryLogEntry) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(asdict(entry), separators=(",", ":"), default=str)
        with _write_lock:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")


def read_query_logs(log_path: str | None = None) -> list[dict[str, Any]]:
    path = Path(log_path or get_settings().query_log_path)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows
