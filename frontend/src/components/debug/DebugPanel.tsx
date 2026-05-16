"use client";

import { X, Search, Zap, ArrowRight } from "lucide-react";

interface DebugPanelProps {
  data: Record<string, unknown>;
  onClose: () => void;
}

export default function DebugPanel({ data, onClose }: DebugPanelProps) {
  const debug = (data || {}) as Record<string, unknown>;
  const chunks = (debug.chunks as Array<{
    id: string;
    text: string;
    bm25: number;
    vector: number;
    rrf: number;
  }>) || [];
  const queryRewrite = (debug.query_rewrite as string) || "";
  const refusalGate = (debug.refusal_gate as { level: number; reason: string }) || null;

  return (
    <div
      style={{
        width: 360,
        height: "100%",
        background: "#111",
        borderLeft: "1px solid #1e1e1e",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "16px 20px",
          borderBottom: "1px solid #1e1e1e",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Zap style={{ width: 14, height: 14, color: "#f59e0b" }} />
          <span style={{ fontSize: 13, fontWeight: 700, color: "#fafafa" }}>
            Retrieval Debug
          </span>
        </div>
        <button
          onClick={onClose}
          style={{
            width: 28,
            height: 28,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            borderRadius: 6,
            border: "none",
            background: "transparent",
            color: "#555",
            cursor: "pointer",
          }}
        >
          <X style={{ width: 14, height: 14 }} />
        </button>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "auto", padding: 20 }}>
        {/* Query Rewrite */}
        {queryRewrite && (
          <div style={{ marginBottom: 24 }}>
            <p
              style={{
                fontSize: 10,
                fontWeight: 700,
                color: "#555",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                marginBottom: 8,
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              Query Rewrite
            </p>
            <div
              style={{
                padding: "12px 14px",
                background: "#191919",
                border: "1px solid #2a2a2a",
                borderRadius: 10,
                display: "flex",
                alignItems: "flex-start",
                gap: 8,
              }}
            >
              <Search style={{ width: 12, height: 12, color: "#a78bfa", marginTop: 2, flexShrink: 0 }} />
              <p style={{ fontSize: 12, color: "#aaa", lineHeight: 1.5 }}>{queryRewrite}</p>
            </div>
          </div>
        )}

        {/* Refusal Gate */}
        {refusalGate && (
          <div style={{ marginBottom: 24 }}>
            <p
              style={{
                fontSize: 10,
                fontWeight: 700,
                color: "#555",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                marginBottom: 8,
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              Refusal Gate
            </p>
            <div
              style={{
                padding: "12px 14px",
                background: refusalGate.level > 2 ? "rgba(239,68,68,0.06)" : "rgba(34,197,94,0.06)",
                border: `1px solid ${refusalGate.level > 2 ? "rgba(239,68,68,0.15)" : "rgba(34,197,94,0.15)"}`,
                borderRadius: 10,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: refusalGate.level > 2 ? "#ef4444" : "#22c55e" }}>
                  Level {refusalGate.level}
                </span>
              </div>
              <p style={{ fontSize: 11, color: "#888", lineHeight: 1.4 }}>{refusalGate.reason}</p>
            </div>
          </div>
        )}

        {/* Chunks */}
        {chunks.length > 0 && (
          <div>
            <p
              style={{
                fontSize: 10,
                fontWeight: 700,
                color: "#555",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                marginBottom: 12,
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              Retrieved Chunks ({chunks.length})
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {chunks.map((chunk, i) => (
                <div
                  key={chunk.id}
                  className="animate-fade-up"
                  style={{
                    padding: "14px",
                    background: "#191919",
                    border: "1px solid #2a2a2a",
                    borderRadius: 10,
                    animationDelay: `${i * 50}ms`,
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                    <span style={{ fontSize: 10, fontWeight: 700, color: "#a78bfa", fontFamily: "'JetBrains Mono', monospace" }}>
                      {chunk.id}
                    </span>
                    <span style={{ fontSize: 10, fontWeight: 700, color: "#22c55e", fontFamily: "'JetBrains Mono', monospace" }}>
                      RRF: {chunk.rrf?.toFixed(4)}
                    </span>
                  </div>
                  <p style={{ fontSize: 11, color: "#888", lineHeight: 1.5, marginBottom: 10 }}>
                    {chunk.text?.slice(0, 120)}...
                  </p>
                  {/* Score Bars */}
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    {[
                      { label: "BM25", value: chunk.bm25, color: "#3b82f6" },
                      { label: "Vector", value: chunk.vector, color: "#a78bfa" },
                    ].map((score) => (
                      <div key={score.label} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                        <span style={{ fontSize: 9, color: "#555", width: 40, fontFamily: "'JetBrains Mono', monospace" }}>
                          {score.label}
                        </span>
                        <div style={{ flex: 1, height: 3, background: "#222", borderRadius: 99, overflow: "hidden" }}>
                          <div
                            className="score-bar-fill"
                            style={{
                              width: `${Math.min((score.value || 0) * 100, 100)}%`,
                              height: "100%",
                              background: score.color,
                              borderRadius: 99,
                            }}
                          />
                        </div>
                        <span style={{ fontSize: 9, color: "#666", fontFamily: "'JetBrains Mono', monospace", width: 32, textAlign: "right" }}>
                          {score.value?.toFixed(2)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
