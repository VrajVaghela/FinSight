# Capacity Planning

Status: load-test harness implemented; live capacity numbers pending ingestion and calibrated deployment.

## Single-Instance Targets

- Normal operation: p99 < 500ms.
- Sustained 50 concurrent users: p99 < 1000ms, error rate < 1%.
- 100 concurrent spike: no crash; all requests eventually complete.
- Recovery: p99 returns below 500ms within 60 seconds.

## Expected Bottleneck

The reranker is expected to be CPU-bound because CrossEncoder inference dominates latency after BM25 and Qdrant finish.

## Scaling Recommendations

- Add API workers when CPU is saturated by reranking.
- Add Qdrant replicas when vector search latency rises or collection size grows significantly.
- Keep Redis close to the API service; BM25 index lookup should remain memory-speed.
- Use model cache volume on every API instance.

## Resource Guide

- API: 2+ CPU cores minimum, 4+ recommended for concurrent reranking.
- RAM: 4GB minimum, 8GB recommended with CrossEncoder loaded.
- Disk: persistent model cache volume for Hugging Face and Torch.

## Degradation Path

Under overload, the system should degrade by increasing latency and returning deterministic refusals where gates fire. It should not crash or generate ungrounded answers.
