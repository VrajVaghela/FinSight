# HNSW Tuning

Status: tuner implemented; live sweep pending Qdrant data and eval relevance IDs.

## Baseline

- `m=16`
- `ef_construct=128`
- `ef_search=64`

## Methodology

Run a sweep across:

- `ef_search=16`
- `ef_search=32`
- `ef_search=64`
- `ef_search=128`
- `ef_search=256`

For each setting, measure:

- p50 latency
- p95 latency
- p99 latency
- recall@10 against `backend/eval/eval_dataset.json`

Select the lowest-latency setting with recall@10 >= 0.95.

## Results

| ef_search | p50 ms | p95 ms | p99 ms | recall@10 |
| ---: | ---: | ---: | ---: | ---: |
| 16 | pending | pending | pending | pending |
| 32 | pending | pending | pending | pending |
| 64 | pending | pending | pending | pending |
| 128 | pending | pending | pending | pending |
| 256 | pending | pending | pending | pending |

## Run Command

```powershell
python -m backend.retrieval.hnsw_tuner
```

Re-tune after document count changes by more than 20%.
