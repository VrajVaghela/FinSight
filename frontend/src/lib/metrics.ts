// ──────────────────────────────────────────────
// Client-side metrics store (singleton)
// Accumulates data from SSE "done" events
// ──────────────────────────────────────────────

import type { QueryMetric } from "@/types";

class MetricsStore {
  private metrics: QueryMetric[] = [];
  private listeners: Set<() => void> = new Set();

  record(metric: QueryMetric) {
    this.metrics.push(metric);
    this.notify();
  }

  getAll(): QueryMetric[] {
    return [...this.metrics];
  }

  getAverageLatency(): number {
    if (this.metrics.length === 0) return 0;
    const sum = this.metrics.reduce((acc, m) => acc + m.latency_ms, 0);
    return Math.round(sum / this.metrics.length);
  }

  getTotalQueries(): number {
    return this.metrics.length;
  }

  getRefusalRate(): number {
    if (this.metrics.length === 0) return 0;
    const refusals = this.metrics.filter((m) => m.wasRefusal).length;
    return Math.round((refusals / this.metrics.length) * 100);
  }

  getCacheHitRate(): number {
    const totalTokens = this.metrics.reduce((acc, m) => acc + m.total_tokens, 0);
    const cachedTokens = this.metrics.reduce((acc, m) => acc + m.cached_tokens, 0);
    if (totalTokens === 0) return 0;
    return Math.round((cachedTokens / totalTokens) * 100);
  }

  getTotalTokens(): number {
    return this.metrics.reduce((acc, m) => acc + m.total_tokens, 0);
  }

  getLatest(n: number): QueryMetric[] {
    return this.metrics.slice(-n);
  }

  subscribe(listener: () => void) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notify() {
    this.listeners.forEach((fn) => fn());
  }
}

export const metricsStore = new MetricsStore();
