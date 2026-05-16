from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from statistics import mean
from typing import Any

from backend.api.health import get_retrieval_health

from .query_logger import read_query_logs


_active_queries = 0


def mark_query_started() -> None:
    global _active_queries
    _active_queries += 1


def mark_query_finished() -> None:
    global _active_queries
    _active_queries = max(0, _active_queries - 1)


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


class DashboardData:
    def __init__(self, log_path: str | None = None) -> None:
        self.log_path = log_path

    def _window(self, delta: timedelta) -> list[dict[str, Any]]:
        cutoff = datetime.now(UTC) - delta
        return [
            row for row in read_query_logs(self.log_path)
            if row.get("timestamp") and _parse_ts(row["timestamp"]) >= cutoff
        ]

    def get_live_metrics(self) -> dict[str, Any]:
        one_minute = self._window(timedelta(minutes=1))
        one_hour = self._window(timedelta(hours=1))
        latencies = [int(row.get("retrieval_ms", 0)) for row in one_minute]
        errors = [row for row in one_hour if row.get("error")]
        p99 = max(latencies) if latencies else 0
        error_rate = len(errors) / len(one_hour) if one_hour else 0.0
        health = "healthy"
        if p99 > 1000 or error_rate > 0.05:
            health = "critical"
        elif p99 > 500:
            health = "degraded"

        gates = Counter(row.get("gate_fired") for row in one_hour if row.get("gate_fired"))
        top_queries = Counter(row.get("query_vector_hash") for row in one_hour).most_common(10)
        retrieval_health = get_retrieval_health()
        return {
            "queries_per_minute": len(one_minute),
            "active_queries": _active_queries,
            "avg_latency_ms": round(mean(latencies), 2) if latencies else 0,
            "refusal_rate_1h": round(sum(1 for row in one_hour if row.get("gate_fired")) / len(one_hour), 4) if one_hour else 0.0,
            "gate1_fire_rate": round(gates.get("L1", 0) / len(one_hour), 4) if one_hour else 0.0,
            "gate2_fire_rate": round(gates.get("L2", 0) / len(one_hour), 4) if one_hour else 0.0,
            "top_queries": [{"query_hash": query_hash, "count": count} for query_hash, count in top_queries],
            "retrieval_health": health,
            "model_status": "loaded" if retrieval_health.get("model_loaded") else "loading",
            "qdrant_status": {
                "state": retrieval_health.get("qdrant"),
                "chunks": retrieval_health.get("chunks", 0),
            },
            "bm25_status": retrieval_health.get("bm25"),
        }

    def get_historical_metrics(self, hours: int = 24) -> list[dict[str, Any]]:
        rows = self._window(timedelta(hours=hours))
        buckets: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            ts = _parse_ts(row["timestamp"]).replace(minute=0, second=0, microsecond=0).isoformat()
            buckets.setdefault(ts, []).append(row)
        series = []
        for timestamp, bucket in sorted(buckets.items()):
            latencies = [int(row.get("retrieval_ms", 0)) for row in bucket]
            gates = Counter(row.get("gate_fired") for row in bucket if row.get("gate_fired"))
            series.append(
                {
                    "timestamp": timestamp,
                    "queries": len(bucket),
                    "avg_latency": round(mean(latencies), 2) if latencies else 0,
                    "refusal_rate": round(sum(1 for row in bucket if row.get("gate_fired")) / len(bucket), 4),
                    "top_gate": gates.most_common(1)[0][0] if gates else None,
                }
            )
        return series
