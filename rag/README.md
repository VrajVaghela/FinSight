# FinSight AI Retrieval Backend

This implements the Nikhil (RAG Lead) RAG retrieval slice from `M1_RAG_Complete_Implementation_Plan.docx`.

## Runtime Surface

- `backend.retrieval.query_pipeline(query, vector, project_id, user_id="default")`
- `backend.retrieval.startup()`
- `GET /api/health`
- `GET /api/retrieval/debug?project_id=adani-q2-fy26&query=...`
- `GET /api/retrieval/debug?session_id=...`

## Pipeline

1. BM25 Redis search and Qdrant dense search run concurrently.
2. Gate 1 refuses when max dense similarity is below `GATE1_THRESHOLD`.
3. RRF merges BM25 and dense hits with `RRF_K`.
4. CrossEncoder reranks the merged top chunks.
5. Gate 2 refuses when top reranker score is below `GATE2_THRESHOLD`.
6. Successful calls return `RetrievalResult`; refused calls return `RefusalEvent`.

## Phase 2 Commands

Calibrate Gate 2 after real Qdrant data is available:

```powershell
python backend\eval\calibrate_gate2.py --project-id adani-q2-fy26
```

Run retrieval metrics:

```powershell
python backend\eval\run_eval.py --assert-ndcg=0.75
```

Profile retrieval latency:

```powershell
python backend\tests\test_latency.py
```

The positive rows in `backend/eval/eval_dataset.json` currently use placeholder `TODO_QDRANT_CHUNK_*` IDs. Replace those with real chunk IDs from M2 ingestion before using the metrics as a gate.

## M2 Contracts

Qdrant collection: `document_chunks`

Mandatory payload fields:

- `project_id`
- `file_id`
- `page_number`
- `section_header`
- `chunk_index`
- `raw_text`
- `context_summary`
- `is_table`
- `bounding_box`
- `table_html`

Redis BM25 key:

- `bm25:{project_id}`
- pickle payload with `corpus: list[str]` and `chunk_ids: list[str]`

`backend.retrieval.bm25_index.write_bm25_index()` is provided for ingestion code.
