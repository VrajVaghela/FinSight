# Nikhil (RAG Lead) Hierarchical Retrieval Implementation Log

Project: FinSight AI  
Role: Lead RAG Architect & Retrieval Engineer  
Feature Area: Hierarchical Retrieval, Cross-Document Search & Session Scoping  
Date: May 3, 2026

## Objective

Extend the Nikhil (RAG Lead) retrieval module with advanced context-aware retrieval features:

- Hierarchical section routing.
- Section-scoped chunk filtering.
- Cross-document comparative retrieval support.
- Redis-backed session scoping.
- Active section bias for follow-up queries.
- Scope debug endpoint.
- Backward-compatible `query_pipeline()` orchestration.

These features are implemented without changing teammate-owned ingestion, backend chat, reasoning, citation, or frontend code.

## Boundary Confirmation

No changes were made to:

- M2 ingestion modules: `DoclingParser`, `StructuralChunker`, `MetadataExtractor`, `DualIndexer`.
- M3 backend modules: `QueryRewriter`, `MEM1Adapter`, `/api/chat`, SSE streaming.
- M4 reasoning/citation modules: PAL router, code generation, symbolic execution, citation engine, GLEAN verifier.
- M5 frontend modules: PDF overlay, debug panel UI.

## Prerequisite From Member 2

The new features are code-complete but require M2 ingestion support before live validation.

Required chunk payload fields:

- `section_id`
- `section_header`
- `section_level`
- `file_id`
- `parent_section_id`

Required Qdrant collection:

```text
document_sections
```

Expected section payload fields:

- `section_id`
- `project_id`
- `file_id`
- `section_header`
- `section_level`
- `parent_section_id`
- `chunk_count`
- `start_page`
- `end_page`
- `summary_text`

Required Redis BM25 key:

```text
bm25_sections:{project_id}
```

Expected format:

```python
{
    "corpus": list[str],
    "ids": list[str]
}
```

Where `corpus` contains section summaries and `ids` contains section IDs.

## Implemented Files

### Section Router

- `backend/retrieval/section_router.py`

Implemented:

- `SectionMatch` dataclass.
- `SectionRouter`.
- Section-level dense search against `document_sections`.
- Section-level BM25 search against `bm25_sections:{project_id}`.
- Parallel BM25 + dense section retrieval.
- Section-level RRF fusion with `SECTION_RRF_K`.
- Top-k section matching.
- Section metadata LRU cache.
- Chunk filtering by `section_id`.
- Fallback to unfiltered chunks when no section match survives filtering.

Primary methods:

```python
await SectionRouter().route_sections(query, query_vector, project_id, top_k=5)
await SectionRouter().filter_chunks_by_sections(chunks, section_ids)
await SectionRouter().get_section_metadata(section_id)
```

### Cross-Document Retrieval

- `backend/retrieval/cross_document.py`

Implemented:

- `CrossDocumentRetriever`.
- Fast heuristic comparative query detection.
- Temporal marker detection.
- Optional M3 `is_comparative` signal support.
- Target file ID lookup from Redis metadata.
- Multi-file retrieval scaffold.
- Per-file retrieval with file filters.
- Pooling and deduplication by `chunk_id`.
- Joint reranking across pooled chunks.
- `source_file_id` provenance assignment.

Primary methods:

```python
await CrossDocumentRetriever().is_comparative_query(query)
await CrossDocumentRetriever().get_target_file_ids(query, project_id, conversation_history)
await CrossDocumentRetriever().retrieve_multi_file(query, vector, project_id, file_ids)
await CrossDocumentRetriever().pool_and_dedup(chunk_lists)
```

### File Metadata Cache

- `backend/retrieval/file_metadata.py`

Implemented:

- Redis-backed file metadata helper.
- File period lookup.
- File name lookup.
- Metadata write helper with TTL.

Expected Redis keys:

```text
file_meta:{file_id}
file_meta:{project_id}:files
```

### Session Scoping

- `backend/retrieval/session_scoper.py`

Implemented:

- `SessionScoper`.
- Redis-backed active section storage.
- 24-hour default TTL.
- Active section add/get/clear operations.
- Add active sections from top retrieved chunks.
- Section-level scope bias.
- Chunk-level scope bias.
- Scope debug payload.

Primary methods:

```python
await SessionScoper().get_active_sections(conversation_id)
await SessionScoper().add_active_section(conversation_id, section_id)
await SessionScoper().add_active_sections_from_chunks(conversation_id, chunks)
await SessionScoper().score_with_scope_bias(sections, conversation_id)
await SessionScoper().score_chunks_with_scope_bias(chunks, conversation_id)
await SessionScoper().debug_scope(conversation_id)
await SessionScoper().clear(conversation_id)
```

### Scope Debug Endpoint

- `backend/api/scope_debug_endpoint.py`
- `backend/api/main.py`

Implemented:

```text
GET /api/retrieval/scope?conversation_id=...
POST /api/retrieval/scope/clear?conversation_id=...
```

The endpoint uses M3 auth if `backend.auth.get_current_user` exists, with a local fallback for standalone development.

### Extended Query Pipeline

- `backend/retrieval/__init__.py`

Extended `query_pipeline()` while preserving backward compatibility.

New signature:

```python
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
) -> RetrievalResult | RefusalEvent
```

Old calls still work:

```python
await query_pipeline(query, vector, project_id)
```

Pipeline additions:

1. Route sections when `use_section_routing=True`.
2. Apply session scope bias when `conversation_id` is present.
3. Detect comparative queries or consume M3 `is_comparative=True`.
4. Apply optional `file_ids` and `section_ids` filters to BM25 and dense retrieval.
5. Fallback to unfiltered retrieval if section filtering produces no hits.
6. Filter merged chunks by selected sections.
7. Apply chunk-level session bias after reranking.
8. Store active sections from successful retrieval.
9. Add advanced debug fields.

### Searcher Extensions

- `backend/retrieval/vector_searcher.py`
- `backend/retrieval/bm25_searcher.py`
- `backend/retrieval/hybrid_retriever.py`

Implemented:

- Optional `file_ids` filtering.
- Optional `section_ids` filtering.
- Qdrant payload filters for `file_id` and `section_id`.
- BM25 metadata-aware filtering when M2 includes metadata in Redis BM25 payload.

### Shared Type Extensions

- `backend/shared/types.py`

Added optional fields to `RetrievedChunk`:

- `section_id`
- `section_level`
- `parent_section_id`
- `source_file_id`

Existing fields were not removed or renamed.

## Debug Output Additions

`RetrievalResult.debug` and `RefusalEvent.debug` now include:

```json
{
  "section_routing": {
    "enabled": true,
    "sections_found": 0,
    "top_sections": [],
    "filter_applied": false
  },
  "session_scope": {
    "enabled": true,
    "active_sections": [],
    "bias_weight": 0.15,
    "bias_applied": false
  },
  "cross_document": {
    "enabled": false,
    "files_queried": 1,
    "file_ids": []
  }
}
```

These fields are safe for M5 debug rendering.

## Environment Variables Added

```text
QDRANT_SECTION_COLLECTION=document_sections
SECTION_RRF_K=30
SECTION_TOP_K=5
SESSION_SCOPE_BIAS=0.15
SESSION_CHUNK_SCOPE_BIAS=0.05
SESSION_SCOPE_TTL_SECONDS=86400
```

Files updated:

- `.env`
- `.env.example`

## Tests Added

- `backend/tests/test_section_router.py`
- `backend/tests/test_cross_document.py`
- `backend/tests/test_session_scope.py`

Covered:

- Section filtering preserves order.
- Section filtering falls back when no chunks match.
- Comparative query detection works without LLM calls.
- Pooling and dedup keeps the strongest duplicate.
- Session scope bias boosts active sections.

## Verification Performed

Syntax compilation:

```powershell
python -m compileall backend scripts
```

Result:

```text
Passed
```

Local non-live tests:

```powershell
python -m pytest backend\tests\test_cross_document.py backend\tests\test_session_scope.py backend\tests\test_section_router.py backend\tests\integration\test_m5_contract.py -q -o cache_dir=$env:TEMP\finsight-pytest-cache
```

Result:

```text
5 passed
```

## Live Validation Pending

The following require M2/M3 live integration:

- M2 confirms `section_id`, `section_level`, and `parent_section_id` in chunk payloads.
- M2 creates and populates `document_sections`.
- M2 creates `bm25_sections:{project_id}`.
- M2 includes BM25 metadata for chunk-level `file_id` and `section_id` filtering.
- M3 passes `conversation_id`.
- M3 passes `is_comparative=True` when QueryRewriter detects comparison.
- M3 optionally passes explicit `file_ids`.
- Redis is available for session scoping.
- Qdrant is available for section metadata lookup.

## Checklist Status

- [x] SectionRouter implemented.
- [x] Section-level BM25 + dense retrieval implemented.
- [x] Section-level RRF `k=30` implemented.
- [x] Section metadata cache implemented.
- [x] Chunk filtering by section implemented.
- [x] Fallback to unfiltered chunks implemented.
- [x] Comparative query detection implemented without LLM calls.
- [x] Cross-document pooling and dedup implemented.
- [x] File provenance field added.
- [x] File metadata cache implemented.
- [x] SessionScoper implemented.
- [x] Redis-backed active section set implemented.
- [x] 24-hour TTL implemented.
- [x] Section-level scope bias implemented.
- [x] Chunk-level scope bias implemented.
- [x] Scope debug endpoint implemented.
- [x] Extended `query_pipeline()` remains backward-compatible.
- [x] Advanced debug fields added.
- [x] New features can be disabled independently.
- [x] Local non-live tests pass.
- [ ] Live SectionRouter returns 3-5 relevant sections per query.
- [ ] Section filtering reduces result set without losing relevant chunks.
- [ ] Comparative retrieval returns 2-4 file-scoped result pools.
- [ ] Joint reranking across files verified live.
- [ ] Follow-up queries retrieve chunks from active sections.
- [ ] New topics can break out of session scope.
- [ ] M2 confirms required schema and indexes.
- [ ] M3 confirms optional params integration.
- [ ] M4 confirms new optional chunk fields do not break citations.
- [ ] M5 confirms scope debug rendering.

## Handoff To Member 2

Required chunk payload additions:

```json
{
  "section_id": "sec-001",
  "section_level": 1,
  "parent_section_id": null
}
```

Required section collection:

```text
document_sections
```

Required section BM25 key:

```text
bm25_sections:{project_id}
```

For chunk BM25 filtering, include optional metadata:

```python
{
    "corpus": [...],
    "chunk_ids": [...],
    "metadata": [
        {"file_id": "file-001", "section_id": "sec-001"}
    ]
}
```

## Handoff To Member 3

New optional `query_pipeline()` parameters:

```python
await query_pipeline(
    query,
    vector,
    project_id,
    conversation_id=str(conversation_id),
    file_ids=file_ids,
    is_comparative=is_comparative,
)
```

Recommendations:

- Pass `conversation_id` for session scoping.
- Pass `is_comparative=True` when QueryRewriter detects comparison.
- Pass explicit `file_ids` for known multi-document requests.
- Leave all advanced flags at defaults unless doing A/B testing.

## Handoff To Member 4

`RetrievedChunk` now includes optional fields:

- `section_id`
- `section_level`
- `parent_section_id`
- `source_file_id`

No existing fields were removed or renamed.

## Handoff To Member 5

New endpoint:

```text
GET /api/retrieval/scope?conversation_id=...
```

Clear endpoint for testing:

```text
POST /api/retrieval/scope/clear?conversation_id=...
```

Enhanced debug output includes:

- `section_routing`
- `session_scope`
- `cross_document`

## Summary

Hierarchical retrieval, cross-document scaffolding, and session scoping are implemented and wired into the retrieval pipeline. The implementation is backward-compatible and can be disabled feature-by-feature. Final validation depends on M2 section payloads/indexes, M3 optional parameter integration, and live Qdrant/Redis data.
