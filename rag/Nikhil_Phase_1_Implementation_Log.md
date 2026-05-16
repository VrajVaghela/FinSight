# Nikhil (RAG Lead) Phase 1 Implementation Log

Project: FinSight AI  
Role: Lead RAG Architect & Retrieval Engineer  
Phase: Phase 1 - Foundation: Repo, Qdrant, Basic Vector Search  
Date: May 3, 2026

## Objective

Bootstrap the retrieval backend foundation for FinSight AI and establish the canonical contracts required by the downstream chat, reasoning, citation, and evaluation modules.

Phase 1 focuses on:

- Creating the backend retrieval package structure.
- Defining shared retrieval dataclasses.
- Implementing Qdrant vector search with mandatory `project_id` filtering.
- Providing Qdrant collection setup helpers.
- Preparing initial runtime configuration and health/debug integration points.

## Implemented Files

### Shared Contracts

- `backend/shared/types.py`
  - `BoundingBox`
  - `RetrievedChunk`
  - `RetrievalResult`
  - `RefusalEvent`

These types match the Nikhil (RAG Lead) implementation plan and are intended as the frozen interface for M3, M4, and M5.

### Retrieval Foundation

- `backend/retrieval/vector_searcher.py`
  - Qdrant client factory.
  - `create_collection_if_not_exists()`.
  - `VectorSearcher.dense_search()`.
  - Mandatory `project_id` payload filter on every dense search.

- `backend/retrieval/__init__.py`
  - Retrieval startup hook.
  - Dependency readiness checks.
  - `query_pipeline()` entry point scaffold used by M3.

- `backend/config.py`
  - Centralized environment-backed settings.

### API Integration

- `backend/api/main.py`
  - FastAPI app bootstrap.
  - Lifespan startup integration.

- `backend/api/health_endpoint.py`
  - `/api/health` endpoint.
  - Qdrant, Redis, and retrieval sub-checks.

- `backend/api/debug_endpoint.py`
  - `/api/retrieval/debug` endpoint.

### Runtime Support

- `.env.example`
  - Qdrant, Redis, gate, RRF, and reranker environment variables.

- `docker-compose.yml`
  - API, Qdrant, Redis, and model cache services.

- `requirements.txt`
  - Runtime dependencies for retrieval and API service.

- `scripts/smoke_dense_search.py`
  - Manual dense-search smoke test for ingested project data.

## Qdrant Collection Contract

Collection name:

```text
document_chunks
```

Vector configuration:

```text
size: 1536
distance: cosine
```

Indexed payload fields created by `create_collection_if_not_exists()`:

- `project_id`
- `file_id`
- `page_number`
- `section_header`
- `chunk_index`
- `is_table`
- `token_count`

Required stored payload fields expected by `RetrievedChunk.from_qdrant_payload()`:

- `raw_text`
- `context_summary`
- `bounding_box`
- `table_html`

## Vector Search Behavior

`VectorSearcher.dense_search(vector, project_id, top_k)` performs a Qdrant search/query with this mandatory filter:

```text
project_id == request project_id
```

This is the Phase 1 cross-project contamination guard. It must not be bypassed by callers.

## Acceptance Status

### Completed

- Backend package structure created.
- Shared dataclasses implemented.
- Qdrant collection creation helper implemented.
- Payload indexes defined.
- Dense search implemented.
- Mandatory `project_id` filter implemented.
- Runtime configuration added.
- Health endpoint includes retrieval dependency checks.
- Smoke-search script added for post-ingestion verification.

### Pending External Integration

- M2 must ingest at least one document into Qdrant.
- M2 must populate `bounding_box` on every chunk payload.
- M2 must confirm final payload field names match this implementation.
- A real Qdrant service must be running to execute the dense-search smoke test.
- OpenAI embedding credentials are required for `scripts/smoke_dense_search.py`.

## Phase 1 Go/No-Go Checklist

- [x] `RetrievedChunk`, `RetrievalResult`, `RefusalEvent`, and `BoundingBox` implemented.
- [x] Qdrant collection schema helper implemented.
- [x] Payload indexes for retrieval filters implemented.
- [x] Dense vector search implemented.
- [x] Dense vector search always applies `project_id` filter.
- [ ] Smoke test run against ingested Adani PDF.
- [ ] Confirm every returned chunk includes `page_number`.
- [ ] Confirm every returned chunk includes valid `bounding_box`.
- [ ] Confirm zero cross-project leakage with mixed-project data.

## Verification Performed

Syntax compilation was run across backend and script files:

```powershell
python -m compileall backend scripts
```

Result:

```text
Passed
```

No live Qdrant/Redis/OpenAI smoke test was run yet because ingestion data and services are not present in the local workspace.

## Notes For M2

The retrieval module expects each Qdrant point payload to include:

```json
{
  "project_id": "adani",
  "file_id": "file-id",
  "page_number": 1,
  "section_header": "Section title",
  "chunk_index": 0,
  "raw_text": "Full chunk text",
  "context_summary": "Short context prefix",
  "is_table": false,
  "table_html": null,
  "bounding_box": {
    "x": 0.0,
    "y": 0.0,
    "w": 0.0,
    "h": 0.0
  }
}
```

`bounding_box.w` and `bounding_box.h` must be greater than zero for citation overlays to work.

## Notes For M3

The intended integration call is:

```python
from backend.retrieval import query_pipeline

result = await query_pipeline(query, vector, project_id, user_id=user_id)
```

The result will be either:

- `RetrievalResult`
- `RefusalEvent`

M3 should serialize those into SSE events according to the main implementation plan.

## Phase 1 Summary

Phase 1 foundation implementation is complete from the code side. The remaining Phase 1 validation requires live Qdrant data from M2 ingestion and a smoke test using a real embedded query.
