# RAGAS Tuning Notes

Status: tooling implemented; live ablation pending M2 ingestion and real relevance IDs.

## Required Ablation

Run the same 10-query subset with:

- `RRF_K=30`
- `RRF_K=60`
- `RRF_K=90`

Record `ndcg@10` and contextual precision for each setting.

| RRF k | NDCG@10 | Contextual Precision | Notes |
| --- | ---: | ---: | --- |
| 30 | pending | pending | Run after ingestion |
| 60 | pending | pending | Current default |
| 90 | pending | pending | Run after ingestion |

## Decision Rule

- If contextual precision is below `0.75`, tune `RRF_K` first.
- If relevant chunks are missing from the reranker candidate set, increase `RETRIEVAL_TOP_K` from `150` to `200`.
- If RAGAS faithfulness is below `0.85` but retrieved chunks contain the answer, hand off to M4 because generation quality owns faithfulness.
