# Retrieval Performance

Target: p50 < 350ms and p99 < 500ms under 10 concurrent retrieval requests.

## Latency Budget

- BM25 Redis search: about 20ms
- Qdrant dense search: about 80ms
- Parallel retrieval wall time: about 80ms
- RRF merge: about 5ms
- CrossEncoder rerank: about 250ms for 150 pairs on CPU
- Gates and debug assembly: about 1ms

Expected total: about 336ms p50.

## Profiling Command

Run after Qdrant, Redis, `GEMINI_API_KEY`, and the Adani eval project are available:

```powershell
python backend\tests\test_latency.py
```

## Mitigation Playbook

Apply mitigations in order if p99 exceeds 500ms.

1. Reduce `RETRIEVAL_TOP_K` from `150` to `100`.
2. Switch `RERANKER_MODEL` to `cross-encoder/ms-marco-MiniLM-L-2-v2`.
3. Tune Qdrant search parameters such as `ef_search=32`.
4. Verify Redis has `bm25:{project_id}` and M2's indexer is not missing BM25 data.

## Model Cache

Docker Compose mounts `model_cache` to:

- `/root/.cache/huggingface`
- `/root/.cache/torch`

This keeps the CrossEncoder model from downloading on every container start.

## Phase 3 Stress Commands

Run after ingestion and calibration:

```powershell
python backend\tests\test_concurrency.py
python backend\tests\test_memory.py
```

## Final Live Numbers

| Scenario | p50 | p95 | p99 | Status |
| --- | ---: | ---: | ---: | --- |
| 10 concurrent | pending | pending | pending | Run after ingestion |
| 20 concurrent | pending | pending | pending | Run after ingestion |
| 100 sequential memory | pending | pending | pending | Run after ingestion |

## Optimization History

No live optimizations have been applied yet. Default settings remain:

- `RETRIEVAL_TOP_K=150`
- `RRF_K=60`
- `RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2`
