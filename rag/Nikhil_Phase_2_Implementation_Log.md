# Nikhil (RAG Lead) Phase 2 Implementation Log

Project: FinSight AI  
Role: Lead RAG Architect & Retrieval Engineer  
Phase: Phase 2 - Advanced Retrieval, Calibration & Evaluation  
Date: May 3, 2026

## Objective

Implement the post-retrieval optimization layer for the Nikhil (RAG Lead) RAG module without touching teammate-owned ingestion, backend chat, reasoning, citation, or frontend surfaces.

Phase 2 focuses on:

- Neural CrossEncoder reranking.
- Refusal Gate L2 using reranker scores.
- Gate 2 threshold calibration tooling.
- Retrieval evaluation dataset and metrics runner.
- Retrieval debug endpoint for M5.
- Latency profiling harness and mitigation documentation.

## Boundary Confirmation

The following teammate-owned areas were not modified:

- M2 ingestion components: `DoclingParser`, `StructuralChunker`, `MetadataExtractor`, `DualIndexer`.
- M3 chat/backend orchestration: `QueryRewriter`, `MEM1Adapter`, `SLMCompressor`, `PromptCache`, SSE streaming.
- M4 reasoning/citation components: PAL router, code generation, symbolic execution, citation engine, GLEAN verifier.
- M5 frontend and PDF overlay UI.

## Implemented Files

### Neural Reranking

- `backend/retrieval/neural_reranker.py`

Implemented:

- Module-level CrossEncoder cache via `_model`.
- `_get_model()` helper for one-time model loading.
- Async `NeuralReranker.rerank()`.
- `asyncio.to_thread(model.predict, pairs)` to avoid blocking the FastAPI event loop.
- In-place `chunk.reranker_score` assignment.
- Top-k sorted reranked output.
- `RERANKER_TOP_K` support through settings.

Default model:

```text
cross-encoder/ms-marco-MiniLM-L-6-v2
```

### Gate 2 Refusal Logic

- `backend/retrieval/refusal_gate.py`

Implemented:

- `RefusalGate.check_reranker(reranked)`.
- `GATE2_THRESHOLD` read from environment-backed settings.
- `RefusalEvent(level=2, reason="level_2_reranker")`.
- Debug payload with rounded reranker score and threshold.

Current default:

```text
GATE2_THRESHOLD=0.0
```

This means Gate 2 is structurally implemented but intentionally permissive until calibration is run on real project data.

### Full Pipeline Integration

- `backend/retrieval/__init__.py`

Implemented:

- Async reranker integration in `query_pipeline()`.
- Gate 1 short-circuit remains before RRF.
- RRF merge remains before reranking.
- Gate 2 now runs after reranking.
- Retrieval timing is added to successful results and refusal events.
- Debug traces are stored in `last_debug_trace`.

Pipeline order:

1. Hybrid BM25 + dense retrieval.
2. Gate 1 dense similarity check.
3. RRF merge.
4. CrossEncoder rerank.
5. Gate 2 reranker threshold check.
6. Return `RetrievalResult` or `RefusalEvent`.

### Debug Builder

- `backend/retrieval/debug_builder.py`

Implemented M5-friendly debug payload keys:

- `bm25_hits`
- `dense_hits`
- `rrf_merged`
- `reranked`
- `gate_1`
- `gate_2`

Each payload includes ranks, chunk IDs, scores, pages, and section metadata where available.

### Debug Endpoint

- `backend/api/debug_endpoint.py`

Implemented:

- `GET /api/retrieval/debug`
- Live rerun mode:

```text
/api/retrieval/debug?project_id=adani-q2-fy26&query=...
```

- Stored trace mode:

```text
/api/retrieval/debug?session_id=...
```

- `store_debug(session_id, debug)` helper for M3 chat integration.
- Local fallback auth shim until M3's `backend.auth.get_current_user` exists.

Expected M3 integration:

```python
from backend.api.debug_endpoint import store_debug

result = await query_pipeline(query, vector, project_id)
if isinstance(result, RetrievalResult):
    store_debug(str(conversation_id), result.debug)
```

### Gate 2 Calibration

- `backend/eval/calibrate_gate2.py`

Implemented:

- Good-query set.
- Bad/adversarial-query set.
- OpenAI `text-embedding-3-large` embedding calls.
- `query_pipeline()` execution per query.
- Good and bad reranker score collection.
- Threshold search for:
  - false positive rate `< 5%`
  - true positive rate `> 80%`
- `.env` output line:

```text
GATE2_THRESHOLD=0.XXXX
```

Also supports offline score JSON:

```powershell
python backend\eval\calibrate_gate2.py --scores-json scores.json
```

### Evaluation Dataset

- `backend/eval/eval_dataset.json`

Implemented:

- 52 total rows.
- 42 positive evaluation questions.
- 10 adversarial questions.
- Required fields:
  - `id`
  - `query`
  - `relevant_ids`
  - `expected_page`
  - `is_numeric`
  - `adversarial`
  - `expected_gate`
  - `notes`

Important:

Positive rows currently contain placeholder relevance IDs such as:

```text
TODO_QDRANT_CHUNK_Q001
```

These must be replaced with real Qdrant chunk IDs after M2 ingestion completes.

### Evaluation Runner

- `backend/eval/run_eval.py`

Implemented:

- Loads `eval_dataset.json`.
- Splits positive and adversarial rows.
- Embeds queries with `text-embedding-3-large`.
- Runs `query_pipeline()`.
- Builds ranx Qrels and Run objects.
- Computes:
  - `precision@5`
  - `precision@10`
  - `mrr`
  - `ndcg@10`
  - `adv_pass_rate`
- Supports CI gate:

```powershell
python backend\eval\run_eval.py --assert-ndcg=0.75
```

### Latency Profiling

- `backend/tests/test_latency.py`
- `PERFORMANCE.md`

Implemented:

- 10-query concurrency benchmark.
- OpenAI embedding preparation.
- Concurrent `query_pipeline()` execution.
- p50, p95, and p99 reporting.
- p99 assertion below 500ms.
- Mitigation playbook.

Mitigation order:

1. Reduce `RETRIEVAL_TOP_K` from `150` to `100`.
2. Switch `RERANKER_MODEL` to `cross-encoder/ms-marco-MiniLM-L-2-v2`.
3. Tune Qdrant search parameters such as `ef_search=32`.
4. Verify Redis contains `bm25:{project_id}`.

### Environment

- `.env`
- `.env.example`
- `docker-compose.yml`

Added/confirmed:

- `GATE2_THRESHOLD`
- `RERANKER_TOP_K`
- `RERANKER_MODEL`
- `EVAL_PROJECT_ID`
- Hugging Face and Torch cache volume mounts for reranker model caching.

## Verification Performed

Syntax compilation was run:

```powershell
python -m compileall backend scripts
```

Result:

```text
Passed
```

No live calibration, NDCG evaluation, or latency benchmark was completed because the local workspace does not yet have:

- M2-ingested Qdrant data.
- Redis BM25 indexes.
- Real Qdrant chunk IDs for `eval_dataset.json`.
- OpenAI API credentials configured.

## Phase 2 Checklist Status

- [x] NeuralReranker loads model through a global module-level cache.
- [x] NeuralReranker uses `asyncio.to_thread()` for model prediction.
- [x] Reranker assigns `reranker_score` in-place.
- [x] Reranker returns top-k chunks sorted by reranker score.
- [x] RefusalGate L2 checks `reranker_score` against `GATE2_THRESHOLD`.
- [x] `query_pipeline()` integrates Gate 2 after reranking.
- [x] Debug builder returns `bm25_hits`, `dense_hits`, `rrf_merged`, `reranked`, `gate_1`, `gate_2`.
- [x] `/api/retrieval/debug` supports live query reruns.
- [x] `/api/retrieval/debug` supports stored session traces.
- [x] Calibration script implemented.
- [x] Evaluation script implemented.
- [x] Eval dataset scaffold has at least 50 rows.
- [x] Eval dataset includes at least 10 adversarial rows.
- [x] Latency profiling harness implemented.
- [x] Performance mitigation playbook documented.
- [ ] `GATE2_THRESHOLD` calibrated on real data.
- [ ] `.env` updated with calibrated non-zero Gate 2 threshold.
- [ ] Positive eval rows updated with real Qdrant chunk IDs.
- [ ] `run_eval.py --assert-ndcg=0.75` executed successfully.
- [ ] Reranker NDCG improvement over raw RRF measured.
- [ ] Latency p99 < 500ms verified against live services.
- [ ] T4 confirmed against real data: CEO email query returns `RefusalEvent`.
- [ ] M3 confirms `query_pipeline()` integration in chat service.
- [ ] M5 confirms debug JSON matches frontend debug panel.

## Commands For Next Live Validation

After M2 ingestion and environment setup:

```powershell
python scripts\smoke_dense_search.py "business segments" --project-id adani-q2-fy26
```

Run Gate 2 calibration:

```powershell
python backend\eval\calibrate_gate2.py --project-id adani-q2-fy26
```

Copy the printed threshold into `.env`:

```text
GATE2_THRESHOLD=0.XXXX
```

Run eval:

```powershell
python backend\eval\run_eval.py --assert-ndcg=0.75
```

Run latency profile:

```powershell
python backend\tests\test_latency.py
```

## Handoff To Member 3

Import:

```python
from backend.retrieval import query_pipeline
from backend.shared.types import RefusalEvent, RetrievalResult
```

Call:

```python
result = await query_pipeline(query, query_vector, project_id, user_id=str(conversation_id))
```

Handle:

- If `isinstance(result, RefusalEvent)`, emit refusal SSE and stop.
- If `isinstance(result, RetrievalResult)`, pass `result.chunks` to M4.
- Store debug traces with `store_debug(session_id, result.debug)` if session polling is needed.

## Handoff To Member 4

`RetrievalResult.chunks` contains reranked `RetrievedChunk` objects with:

- `chunk_id`
- `raw_text`
- `bounding_box`
- `page_number`
- `section_header`
- `is_table`
- `table_html`
- `reranker_score`

These chunks are ready for PAL routing, citation preparation, and reasoning context construction.

## Handoff To Member 5

Debug endpoint:

```text
GET /api/retrieval/debug?project_id=adani-q2-fy26&query=...
```

Returns:

- BM25 hits.
- Dense hits.
- RRF merged chunks.
- Reranked chunks.
- Gate 1 decision.
- Gate 2 decision.
- Latency fields.

Eval assets:

- `backend/eval/eval_dataset.json`
- `backend/eval/run_eval.py`

## Phase 2 Summary

Phase 2 is implemented from the code and tooling side. The remaining work is live-system calibration and validation after M2 ingestion produces real Qdrant chunks and BM25 indexes.
