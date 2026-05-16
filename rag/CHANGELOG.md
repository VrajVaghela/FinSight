# Changelog

## Phase 1 - Foundation

- Created retrieval backend package.
- Added shared dataclasses.
- Implemented Qdrant collection helper and dense search with mandatory `project_id` filter.
- Added health/debug foundation.

## Phase 2 - Reranking, Gates & Eval

- Added async CrossEncoder reranker.
- Added Gate 2 reranker threshold.
- Added calibration and eval scripts.
- Added 52-row eval dataset scaffold.
- Added debug endpoint live rerun and stored trace support.

## Phase 3 - Integration & Demo Prep

- Added M3/M4/M5 integration contract tests.
- Added 25-query adversarial suite.
- Added RAGAS export and bridge.
- Added concurrency, memory, and T1-T5 acceptance harnesses.
- Added demo script and performance notes.

## Phase 4 - Production Hardening

- Added non-blocking query logger with vector hashing.
- Added analytics exporter and dashboard data aggregation.
- Added analytics REST endpoints and metrics WebSocket.
- Added dynamic threshold adjustment and threshold effectiveness reporting.
- Added HNSW tuning scaffold and capacity load test.
- Added operations runbook and final architecture documentation.

## Pending Live Metrics

- Gate 2 calibrated threshold.
- NDCG@10 and RAGAS contextual precision.
- HNSW recall/latency sweep.
- 50-concurrent load results.
- M3/M4/M5 live sign-off.
