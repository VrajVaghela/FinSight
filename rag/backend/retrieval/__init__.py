from __future__ import annotations

import time
from typing import Any

from backend.config import get_settings
from backend.shared.types import RefusalEvent, RetrievalResult

from .debug_builder import build_debug
from .cross_document import CrossDocumentRetriever
from .dynamic_threshold import DynamicThreshold
from .hybrid_retriever import HybridRetriever
from .neural_reranker import NeuralReranker
from .query_logger import QueryLogger
from .refusal_gate import RefusalGate
from .rrf_merger import RRFMerger
from .section_router import SectionRouter
from .session_scoper import SessionScoper


last_debug_trace: dict[str, dict[str, Any]] = {}
_retriever: HybridRetriever | None = None


def get_retriever() -> HybridRetriever:
    global _retriever
    if _retriever is None:
        _retriever = HybridRetriever()
    return _retriever


def set_retriever_for_tests(retriever: HybridRetriever | None) -> None:
    global _retriever
    _retriever = retriever


async def startup() -> None:
    from .startup import startup as retrieval_startup

    await retrieval_startup()


async def query_pipeline(
    query: str,
    vector: list[float],
    project_id: str,
    conversation_id: str | None = None,
    file_ids: list[str] | None = None,
    is_comparative: bool = False,
    use_section_routing: bool = True,
    use_session_scope: bool = True,
    top_k: int | None = None,
    user_id: str = "default",
    standalone_query: str | None = None,
    enable_logging: bool = True,
) -> RetrievalResult | RefusalEvent:
    t0 = time.perf_counter()
    settings = get_settings()
    try:
        from .dashboard_data import mark_query_finished, mark_query_started

        mark_query_started()
    except Exception:
        mark_query_started = None
        mark_query_finished = None

    retrieval_top_k = top_k or settings.retrieval_top_k
    section_matches = []
    section_ids: list[str] = []
    section_filter_applied = False
    scope_active_sections: list[str] = []
    scope_bias_applied = False
    cross_document_enabled = False
    files_queried = file_ids[:] if file_ids else []

    section_router: SectionRouter | None = None
    session_scoper: SessionScoper | None = None
    if use_section_routing:
        try:
            section_router = SectionRouter()
            section_matches = await section_router.route_sections(
                query,
                vector,
                project_id,
                top_k=settings.section_top_k,
            )
            if conversation_id and use_session_scope:
                session_scoper = SessionScoper()
                scope_active_sections = sorted(await session_scoper.get_active_sections(conversation_id))
                section_matches = await session_scoper.score_with_scope_bias(section_matches, conversation_id)
                scope_bias_applied = bool(scope_active_sections)
            section_ids = [section.section_id for section in section_matches[: settings.section_top_k]]
            section_filter_applied = bool(section_ids)
        except Exception as exc:
            section_matches = []
            section_ids = []
            section_filter_applied = False

    cross_document = CrossDocumentRetriever()
    try:
        cross_document_enabled = bool(
            file_ids
            or is_comparative
            or await cross_document.is_comparative_query(query, is_comparative=is_comparative)
        )
        if not files_queried and cross_document_enabled:
            files_queried = await cross_document.get_target_file_ids(query, project_id, [])
    except Exception:
        cross_document_enabled = bool(file_ids)

    bm25_hits, dense_hits = await get_retriever().retrieve(
        query,
        vector,
        project_id,
        top_k=retrieval_top_k,
        file_ids=files_queried or None,
        section_ids=section_ids or None,
    )
    if section_ids and not dense_hits and not bm25_hits:
        section_filter_applied = False
        bm25_hits, dense_hits = await get_retriever().retrieve(
            query,
            vector,
            project_id,
            top_k=retrieval_top_k,
            file_ids=files_queried or None,
        )

    gate1_decision = DynamicThreshold.adjust_gate1(query, dense_hits)
    gate1 = RefusalGate.check_threshold(dense_hits, threshold=gate1_decision.threshold)
    if gate1:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        gate1.debug["retrieval_ms"] = elapsed_ms
        gate1.debug["gate1_base_threshold"] = gate1_decision.base_threshold
        gate1.debug["gate1_adjustments"] = gate1_decision.adjustments
        gate1.debug.update(
            build_debug(
                bm25_hits,
                dense_hits,
                [],
                None,
                gate1,
                None,
                gate1_threshold=gate1_decision.threshold,
            )
        )
        gate1.debug["latency_ms"] = elapsed_ms
        gate1.debug["query"] = query
        gate1.debug["project_id"] = project_id
        gate1.debug.update(
            _advanced_debug(
                section_matches,
                section_filter_applied,
                use_section_routing,
                use_session_scope,
                scope_active_sections,
                scope_bias_applied,
                cross_document_enabled,
                files_queried,
            )
        )
        last_debug_trace[user_id] = gate1.debug
        if enable_logging:
            QueryLogger().enqueue(
                query=query,
                query_vector=vector,
                project_id=project_id,
                result=gate1,
                conversation_id=conversation_id,
                user_id=user_id,
                standalone_query=standalone_query,
                gate1_threshold=gate1_decision.threshold,
                gate2_threshold=settings.gate2_threshold,
                gate1_adjustments=gate1_decision.adjustments,
                gate2_adjustments=[],
            )
        if mark_query_finished:
            mark_query_finished()
        return gate1

    merged = RRFMerger.merge(bm25_hits, dense_hits, k=settings.rrf_k)
    RRFMerger.assert_no_duplicates(merged)
    if files_queried:
        scoped = [chunk for chunk in merged if chunk.file_id in files_queried]
        merged = scoped or merged
    if section_router and section_ids:
        filtered = await section_router.filter_chunks_by_sections(merged, section_ids)
        section_filter_applied = filtered is not merged
        merged = filtered

    reranked = await NeuralReranker.get().rerank(
        query,
        merged[:retrieval_top_k],
        top_k=settings.reranker_top_k,
    )
    if conversation_id and use_session_scope:
        try:
            session_scoper = session_scoper or SessionScoper()
            reranked = await session_scoper.score_chunks_with_scope_bias(reranked, conversation_id)
            scope_active_sections = sorted(await session_scoper.get_active_sections(conversation_id))
            scope_bias_applied = bool(scope_active_sections)
        except Exception:
            pass

    gate2_decision = DynamicThreshold.adjust_gate2(query, reranked)
    gate2 = RefusalGate.check_reranker(reranked, threshold=gate2_decision.threshold)
    if gate2:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        gate2.debug["retrieval_ms"] = elapsed_ms
        gate2.debug["gate1_base_threshold"] = gate1_decision.base_threshold
        gate2.debug["gate1_adjustments"] = gate1_decision.adjustments
        gate2.debug["gate2_base_threshold"] = gate2_decision.base_threshold
        gate2.debug["gate2_adjustments"] = gate2_decision.adjustments
        gate2.debug.update(
            build_debug(
                bm25_hits,
                dense_hits,
                merged,
                reranked,
                None,
                gate2,
                gate1_threshold=gate1_decision.threshold,
                gate2_threshold=gate2_decision.threshold,
            )
        )
        gate2.debug["latency_ms"] = elapsed_ms
        gate2.debug["query"] = query
        gate2.debug["project_id"] = project_id
        gate2.debug.update(
            _advanced_debug(
                section_matches,
                section_filter_applied,
                use_section_routing,
                use_session_scope,
                scope_active_sections,
                scope_bias_applied,
                cross_document_enabled,
                files_queried,
            )
        )
        last_debug_trace[user_id] = gate2.debug
        if enable_logging:
            QueryLogger().enqueue(
                query=query,
                query_vector=vector,
                project_id=project_id,
                result=gate2,
                conversation_id=conversation_id,
                user_id=user_id,
                standalone_query=standalone_query,
                gate1_threshold=gate1_decision.threshold,
                gate2_threshold=gate2_decision.threshold,
                gate1_adjustments=gate1_decision.adjustments,
                gate2_adjustments=gate2_decision.adjustments,
            )
        if mark_query_finished:
            mark_query_finished()
        return gate2

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    debug = build_debug(
        bm25_hits,
        dense_hits,
        merged,
        reranked,
        None,
        None,
        gate1_threshold=gate1_decision.threshold,
        gate2_threshold=gate2_decision.threshold,
    )
    debug["latency_ms"] = elapsed_ms
    debug["query"] = query
    debug["project_id"] = project_id
    debug["gate1_base_threshold"] = gate1_decision.base_threshold
    debug["gate1_adjustments"] = gate1_decision.adjustments
    debug["gate2_base_threshold"] = gate2_decision.base_threshold
    debug["gate2_adjustments"] = gate2_decision.adjustments
    debug.update(
        _advanced_debug(
            section_matches,
            section_filter_applied,
            use_section_routing,
            use_session_scope,
            scope_active_sections,
            scope_bias_applied,
            cross_document_enabled,
            files_queried,
        )
    )
    last_debug_trace[user_id] = debug

    result = RetrievalResult(
        chunks=reranked,
        gate1_score=float(dense_hits[0].score) if dense_hits else 0.0,
        gate2_score=float(reranked[0].reranker_score) if reranked else 0.0,
        retrieval_ms=elapsed_ms,
        debug=debug,
    )
    if enable_logging:
        QueryLogger().enqueue(
            query=query,
            query_vector=vector,
            project_id=project_id,
            result=result,
            conversation_id=conversation_id,
            user_id=user_id,
            standalone_query=standalone_query,
            gate1_threshold=gate1_decision.threshold,
            gate2_threshold=gate2_decision.threshold,
            gate1_adjustments=gate1_decision.adjustments,
            gate2_adjustments=gate2_decision.adjustments,
        )
    if conversation_id and use_session_scope:
        try:
            await (session_scoper or SessionScoper()).add_active_sections_from_chunks(conversation_id, reranked)
        except Exception:
            pass
    if mark_query_finished:
        mark_query_finished()
    return result


def _advanced_debug(
    section_matches,
    section_filter_applied: bool,
    section_routing_enabled: bool,
    session_scope_enabled: bool,
    active_sections: list[str],
    scope_bias_applied: bool,
    cross_document_enabled: bool,
    file_ids: list[str],
) -> dict[str, Any]:
    return {
        "section_routing": {
            "enabled": section_routing_enabled,
            "sections_found": len(section_matches),
            "top_sections": [
                {
                    "section_id": section.section_id,
                    "header": section.section_header,
                    "file_id": section.file_id,
                    "rrf_score": section.rrf_score,
                }
                for section in section_matches[:5]
            ],
            "filter_applied": section_filter_applied,
        },
        "session_scope": {
            "enabled": session_scope_enabled,
            "active_sections": active_sections,
            "bias_weight": get_settings().session_scope_bias,
            "bias_applied": scope_bias_applied,
        },
        "cross_document": {
            "enabled": cross_document_enabled,
            "files_queried": len(file_ids) if file_ids else 1,
            "file_ids": file_ids,
        },
    }
