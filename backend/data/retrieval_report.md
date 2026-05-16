# Retrieval Layer Evaluation Report
**Date:** 2026-05-04 05:51:20
**Total Samples:** 10
**Top-K Evaluated:** 5

## Core Retrieval Metrics
| Metric | Value | Description |
| :--- | :--- | :--- |
| **Hit Rate / Recall@5** | **100.00%** | % of queries where the ground-truth chunk was retrieved. |
| **MRR (Mean Reciprocal Rank)** | **0.8700** | Measures ranking quality (closer to 1 is better). |
| **Precision@5** | **0.2000** | % of retrieved chunks that are relevant (synthetic estimate). |
| **Avg Latency** | **50.90 ms** | Time taken for embedding + VDB search. |

## Interpretation
- **Recall**: A Hit Rate of 100.0% indicates how well your embedding model and chunking strategy capture semantic intent.
- **MRR**: An MRR of 0.87 means the correct answer is found at rank **1.1** on average.
- **Action Items**: If Hit Rate is low, consider increasing chunk overlap or switching to a larger embedding model.
