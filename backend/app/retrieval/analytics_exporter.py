from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from statistics import mean
from typing import Any

from .query_logger import read_query_logs


def _parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _percentile(values: list[int], pct: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * pct)))
    return int(ordered[index])


class AnalyticsExporter:
    def __init__(self, log_path: str | None = None) -> None:
        self.log_path = log_path

    def _logs(self) -> list[dict[str, Any]]:
        return read_query_logs(self.log_path)

    def _filter_project(self, logs: list[dict[str, Any]], project_id: str | None) -> list[dict[str, Any]]:
        if not project_id:
            return logs
        return [row for row in logs if row.get("project_id") == project_id]

    def export_daily_summary(self, date: str, project_id: str | None = None) -> dict[str, Any]:
        logs = self._filter_project(self._logs(), project_id)
        rows = [row for row in logs if row.get("timestamp", "").startswith(date)]
        latencies = [int(row.get("retrieval_ms", 0)) for row in rows]
        gate_reasons = Counter(row.get("gate_fired") for row in rows if row.get("gate_fired"))
        top_queries = Counter(row.get("query_text", "") for row in rows).most_common(10)
        return {
            "date": date,
            "project_id": project_id,
            "total_queries": len(rows),
            "refusal_rate": round(sum(1 for row in rows if row.get("gate_fired")) / len(rows), 4) if rows else 0.0,
            "latency": {
                "avg": round(mean(latencies), 2) if latencies else 0,
                "p50": _percentile(latencies, 0.50),
                "p95": _percentile(latencies, 0.95),
                "p99": _percentile(latencies, 0.99),
            },
            "top_queries": [{"query": query, "count": count} for query, count in top_queries],
            "top_gate_reasons": [{"reason": reason, "count": count} for reason, count in gate_reasons.most_common()],
        }

    def export_retrieval_quality(self, project_id: str, days: int = 7) -> dict[str, Any]:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        rows = [
            row for row in self._filter_project(self._logs(), project_id)
            if row.get("timestamp") and _parse_ts(row["timestamp"]) >= cutoff
        ]
        hybrid = sum(1 for row in rows if row.get("bm25_hit_count", 0) and row.get("dense_hit_count", 0))
        bm25_only = sum(1 for row in rows if row.get("bm25_hit_count", 0) and not row.get("dense_hit_count", 0))
        dense_only = sum(1 for row in rows if row.get("dense_hit_count", 0) and not row.get("bm25_hit_count", 0))
        total = len(rows) or 1
        return {
            "project_id": project_id,
            "days": days,
            "queries": len(rows),
            "ndcg_trend": [],
            "bm25_vs_dense_contribution": {
                "hybrid": round(hybrid / total, 4),
                "bm25_only": round(bm25_only / total, 4),
                "dense_only": round(dense_only / total, 4),
            },
            "reranker_improvement_percentage": None,
            "note": "NDCG trend requires scheduled run_eval output with real relevance judgements.",
        }

    def export_for_dashboard(self, project_id: str | None = None) -> dict[str, Any]:
        today = datetime.now(UTC).date().isoformat()
        summary = self.export_daily_summary(today, project_id)
        rows = self._filter_project(self._logs(), project_id)
        method_total = len(rows) or 1
        bm25_only = sum(1 for row in rows if row.get("bm25_hit_count", 0) and not row.get("dense_hit_count", 0))
        dense_only = sum(1 for row in rows if row.get("dense_hit_count", 0) and not row.get("bm25_hit_count", 0))
        hybrid = sum(1 for row in rows if row.get("bm25_hit_count", 0) and row.get("dense_hit_count", 0))
        return {
            "total_queries_today": summary["total_queries"],
            "refusal_rate": summary["refusal_rate"],
            "avg_latency_ms": summary["latency"]["avg"],
            "top_gate_reasons": summary["top_gate_reasons"],
            "retrieval_method_split": {
                "bm25_only": round(bm25_only / method_total, 4),
                "dense_only": round(dense_only / method_total, 4),
                "hybrid": round(hybrid / method_total, 4),
            },
        }
