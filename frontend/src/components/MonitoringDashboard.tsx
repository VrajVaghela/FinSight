"use client";

import { useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  PieChart, Pie, LineChart, Line, Area, AreaChart,
} from "recharts";
import {
  Monitor, CircleCheck, Clock, ShieldOff,
  Layers, RefreshCw, TrendingUp, TrendingDown,
  Activity,
} from "lucide-react";

// ── Mock Data ─────────────────────────────────────
const kpiCards = [
  { label: "Total Queries", value: "114", icon: Monitor, color: "#3b82f6", trend: "+23%", trendUp: true },
  { label: "Answer Rate", value: "87%", icon: CircleCheck, color: "#22c55e", trend: "+2.1%", trendUp: true },
  { label: "Avg Latency", value: "156ms", icon: Clock, color: "#a78bfa", trend: "-18ms", trendUp: true },
  { label: "Refusal Rate", value: "9%", icon: ShieldOff, color: "#f59e0b", trend: "+1%", trendUp: false },
];

const queryVolumeData = [
  { day: "Mon", queries: 12, answered: 10 },
  { day: "Tue", queries: 18, answered: 15 },
  { day: "Wed", queries: 8, answered: 7 },
  { day: "Thu", queries: 24, answered: 20 },
  { day: "Fri", queries: 32, answered: 28 },
  { day: "Sat", queries: 6, answered: 5 },
  { day: "Sun", queries: 14, answered: 12 },
];

const answerDistribution = [
  { name: "Answered", value: 87, color: "#22c55e" },
  { name: "Refused", value: 9, color: "#f59e0b" },
  { name: "Error", value: 4, color: "#ef4444" },
];

const latencyData = [
  { time: "00:00", latency: 120 },
  { time: "04:00", latency: 115 },
  { time: "08:00", latency: 145 },
  { time: "12:00", latency: 180 },
  { time: "16:00", latency: 160 },
  { time: "20:00", latency: 140 },
  { time: "Now", latency: 135 },
];

const retrievalMethods = [
  { method: "BM25", precision: 0.72, recall: 0.68, color: "#3b82f6" },
  { method: "Vector", precision: 0.81, recall: 0.79, color: "#3b82f6" },
  { method: "Hybrid", precision: 0.89, recall: 0.87, color: "#a78bfa" },
  { method: "Reranked", precision: 0.94, recall: 0.91, color: "#22c55e", best: true },
];

const pipelineStages = [
  { stage: "Query Rewrite", latency: 23, color: "#3b82f6", maxLatency: 600 },
  { stage: "BM25 Retrieval", latency: 12, color: "#a78bfa", maxLatency: 600 },
  { stage: "Vector Search", latency: 38, color: "#06b6d4", maxLatency: 600 },
  { stage: "RRF Merge", latency: 4, color: "#6b7280", maxLatency: 600 },
  { stage: "Cross-Encoder Rerank", latency: 58, color: "#f59e0b", maxLatency: 600 },
  { stage: "LLM Generation", latency: 450, color: "#22c55e", maxLatency: 600 },
];

const ragasScores = [
  { label: "Faithfulness", value: 0.91, target: 0.85, color: "#22c55e" },
  { label: "Answer Relevancy", value: 0.87, target: 0.80, color: "#3b82f6" },
  { label: "Contextual Precision", value: 0.82, target: 0.75, color: "#a78bfa" },
];

export default function MonitoringDashboard() {
  return (
    <div className="animate-fade-up" style={{ maxWidth: 1100, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, color: "#fafafa", letterSpacing: "-0.03em" }}>
            RAG Analytics
          </h1>
          <p style={{ fontSize: 13, color: "#555", marginTop: 4 }}>
            System performance and retrieval quality metrics
          </p>
        </div>
        <button
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            padding: "8px 14px",
            background: "#191919",
            border: "1px solid #2a2a2a",
            borderRadius: 8,
            color: "#888",
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          <RefreshCw style={{ width: 12, height: 12 }} />
          Refresh
        </button>
      </div>

      {/* ── KPI Cards ────────────────────────────── */}
      <div className="stagger-children" style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
        {kpiCards.map((card) => (
          <div
            key={card.label}
            className="hover-lift animate-fade-up"
            style={{
              padding: "18px 20px",
              background: "#151515",
              border: "1px solid #2a2a2a",
              borderRadius: 14,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 14 }}>
              <div style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                background: `${card.color}15`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}>
                <card.icon style={{ width: 16, height: 16, color: card.color }} />
              </div>
            </div>
            <div style={{ fontSize: 32, fontWeight: 900, color: "#fafafa", fontFamily: "'JetBrains Mono', monospace", letterSpacing: "-0.03em", marginBottom: 4 }}>
              {card.value}
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ fontSize: 12, color: "#666" }}>{card.label}</span>
              <span style={{
                fontSize: 10,
                fontWeight: 700,
                color: card.trendUp ? "#22c55e" : "#ef4444",
                background: card.trendUp ? "rgba(34,197,94,0.08)" : "rgba(239,68,68,0.08)",
                padding: "2px 8px",
                borderRadius: 6,
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                {card.trend} this week
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* ── Row: Query Volume + Answer Distribution ── */}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 12, marginBottom: 12 }}>
        {/* Query Volume */}
        <div className="animate-fade-up" style={{ padding: 20, background: "#151515", border: "1px solid #2a2a2a", borderRadius: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 16 }}>
            <Activity style={{ width: 14, height: 14, color: "#a78bfa" }} />
            <span style={{ fontSize: 14, fontWeight: 700, color: "#e5e5e5" }}>Query Volume (7 days)</span>
          </div>
          <div style={{ width: "100%", height: 220 }}>
            <ResponsiveContainer>
              <BarChart data={queryVolumeData} barGap={4} barSize={16}>
                <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fill: "#555", fontSize: 11, fontFamily: "'JetBrains Mono', monospace" }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: "#444", fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} />
                <Tooltip contentStyle={{ background: "#1a1a1a", border: "1px solid #333", borderRadius: 8, fontSize: 12, color: "#fafafa" }} />
                <Bar dataKey="queries" radius={[4, 4, 0, 0]} fill="#3b82f6" opacity={0.8} />
                <Bar dataKey="answered" radius={[4, 4, 0, 0]} fill="#22c55e" opacity={0.8} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Answer Distribution Donut */}
        <div className="animate-fade-up" style={{ padding: 20, background: "#151515", border: "1px solid #2a2a2a", borderRadius: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <CircleCheck style={{ width: 14, height: 14, color: "#22c55e" }} />
            <span style={{ fontSize: 14, fontWeight: 700, color: "#e5e5e5" }}>Answer Distribution</span>
          </div>
          <div style={{ width: "100%", height: 180 }}>
            <ResponsiveContainer>
              <PieChart>
                <Pie
                  data={answerDistribution}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={75}
                  dataKey="value"
                  strokeWidth={0}
                >
                  {answerDistribution.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6, marginTop: 4 }}>
            {answerDistribution.map((item) => (
              <div key={item.name} style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <div style={{ width: 8, height: 8, borderRadius: "50%", background: item.color }} />
                  <span style={{ fontSize: 12, color: "#999" }}>{item.name}</span>
                </div>
                <span style={{ fontSize: 12, fontWeight: 700, color: "#fafafa", fontFamily: "'JetBrains Mono', monospace" }}>
                  {item.value}%
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ── End-to-End Latency Line Chart ──────── */}
      <div className="animate-fade-up" style={{ padding: 20, background: "#151515", border: "1px solid #2a2a2a", borderRadius: 14, marginBottom: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Clock style={{ width: 14, height: 14, color: "#06b6d4" }} />
            <span style={{ fontSize: 14, fontWeight: 700, color: "#e5e5e5" }}>End-to-End Latency (24h)</span>
          </div>
          <span style={{
            fontSize: 11,
            fontWeight: 700,
            color: "#22c55e",
            background: "rgba(34,197,94,0.08)",
            padding: "4px 10px",
            borderRadius: 6,
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            Avg: 156ms
          </span>
        </div>
        <div style={{ width: "100%", height: 180 }}>
          <ResponsiveContainer>
            <AreaChart data={latencyData}>
              <defs>
                <linearGradient id="latencyGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#06b6d4" stopOpacity={0.2} />
                  <stop offset="100%" stopColor="#06b6d4" stopOpacity={0} />
                </linearGradient>
              </defs>
              <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fill: "#555", fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} />
              <YAxis axisLine={false} tickLine={false} tick={{ fill: "#444", fontSize: 10, fontFamily: "'JetBrains Mono', monospace" }} unit="ms" />
              <Tooltip contentStyle={{ background: "#1a1a1a", border: "1px solid #333", borderRadius: 8, fontSize: 12, color: "#fafafa" }} />
              <Area type="monotone" dataKey="latency" stroke="#06b6d4" strokeWidth={2} fill="url(#latencyGrad)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* ── Retrieval Method Comparison ────────── */}
      <div className="animate-fade-up" style={{ padding: 24, background: "#151515", border: "1px solid #2a2a2a", borderRadius: 14, marginBottom: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Layers style={{ width: 14, height: 14, color: "#a78bfa" }} />
            <span style={{ fontSize: 14, fontWeight: 700, color: "#e5e5e5" }}>Retrieval Method Comparison</span>
          </div>
          <span style={{
            fontSize: 10,
            fontWeight: 700,
            color: "#22c55e",
            background: "rgba(34,197,94,0.08)",
            border: "1px solid rgba(34,197,94,0.15)",
            padding: "4px 10px",
            borderRadius: 6,
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            +14% from Reranker
          </span>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {retrievalMethods.map((method) => (
            <div key={method.method}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 13, fontWeight: 700, color: "#e5e5e5", minWidth: 80 }}>{method.method}</span>
                  {method.best && (
                    <span style={{
                      fontSize: 9,
                      fontWeight: 800,
                      color: "#22c55e",
                      background: "rgba(34,197,94,0.08)",
                      padding: "2px 8px",
                      borderRadius: 4,
                      fontFamily: "'JetBrains Mono', monospace",
                    }}>
                      Best
                    </span>
                  )}
                </div>
                <span style={{ fontSize: 11, fontWeight: 700, color: "#22c55e", fontFamily: "'JetBrains Mono', monospace" }}>
                  P: {method.precision.toFixed(2)}  R: {method.recall.toFixed(2)}
                </span>
              </div>
              <div style={{ display: "flex", gap: 2 }}>
                {/* Precision bar */}
                <div style={{ flex: 1, height: 6, background: "#222", borderRadius: 99, overflow: "hidden" }}>
                  <div className="score-bar-fill" style={{
                    width: `${method.precision * 100}%`,
                    height: "100%",
                    background: method.best ? "#22c55e" : "#3b82f6",
                    borderRadius: 99,
                  }} />
                </div>
                {/* Recall bar */}
                <div style={{ flex: 1, height: 6, background: "#222", borderRadius: 99, overflow: "hidden" }}>
                  <div className="score-bar-fill" style={{
                    width: `${method.recall * 100}%`,
                    height: "100%",
                    background: "#a78bfa",
                    borderRadius: 99,
                  }} />
                </div>
              </div>
            </div>
          ))}
        </div>
        <div style={{ display: "flex", gap: 16, marginTop: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#3b82f6" }} />
            <span style={{ fontSize: 11, color: "#666" }}>Precision</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: "#a78bfa" }} />
            <span style={{ fontSize: 11, color: "#666" }}>Recall</span>
          </div>
        </div>
      </div>

      {/* ── Pipeline Stage Latencies ──────────── */}
      <div className="animate-fade-up" style={{ padding: 24, background: "#151515", border: "1px solid #2a2a2a", borderRadius: 14, marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 20 }}>
          <Layers style={{ width: 14, height: 14, color: "#22c55e" }} />
          <span style={{ fontSize: 14, fontWeight: 700, color: "#e5e5e5" }}>Pipeline Stage Latencies</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {pipelineStages.map((stage) => (
            <div key={stage.stage} style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <span style={{ fontSize: 12, color: "#999", width: 170, flexShrink: 0 }}>{stage.stage}</span>
              <div style={{ flex: 1, height: 8, background: "#222", borderRadius: 99, overflow: "hidden", position: "relative" }}>
                <div
                  className="score-bar-fill"
                  style={{
                    width: `${(stage.latency / stage.maxLatency) * 100}%`,
                    height: "100%",
                    background: stage.color,
                    borderRadius: 99,
                  }}
                />
              </div>
              <span style={{
                fontSize: 11,
                fontWeight: 700,
                color: "#888",
                fontFamily: "'JetBrains Mono', monospace",
                width: 48,
                textAlign: "right",
                flexShrink: 0,
              }}>
                {stage.latency}ms
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* ── RAGAS Evaluation Scores ──────────── */}
      <div className="stagger-children" style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 12 }}>
        {ragasScores.map((score) => {
          const pct = Math.min(score.value * 100, 100);
          const circumference = 2 * Math.PI * 42;
          const offset = circumference - (pct / 100) * circumference;
          return (
            <div
              key={score.label}
              className="hover-lift animate-fade-up"
              style={{
                padding: 24,
                background: "#151515",
                border: "1px solid #2a2a2a",
                borderRadius: 14,
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
              }}
            >
              <div style={{ position: "relative", width: 96, height: 96, marginBottom: 16 }}>
                <svg width="96" height="96" style={{ transform: "rotate(-90deg)" }}>
                  <circle cx="48" cy="48" r="42" stroke="#222" strokeWidth="4" fill="none" />
                  <circle
                    cx="48" cy="48" r="42"
                    stroke={score.color}
                    strokeWidth="4"
                    fill="none"
                    strokeLinecap="round"
                    strokeDasharray={circumference}
                    strokeDashoffset={offset}
                    style={{ transition: "stroke-dashoffset 1.5s cubic-bezier(0.16,1,0.3,1)" }}
                  />
                </svg>
                <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <span style={{ fontSize: 20, fontWeight: 900, color: "#fafafa", fontFamily: "'JetBrains Mono', monospace" }}>
                    {score.value.toFixed(2)}
                  </span>
                </div>
              </div>
              <p style={{ fontSize: 13, fontWeight: 700, color: "#ccc", marginBottom: 4 }}>{score.label}</p>
              <p style={{ fontSize: 10, color: "#555", fontFamily: "'JetBrains Mono', monospace" }}>Target: {score.target}</p>
            </div>
          );
        })}
      </div>

      {/* ── Golden Dataset Evaluation Extension ──────────── */}
      <div className="animate-fade-up" style={{ padding: 24, background: "#151515", border: "1px solid #2a2a2a", borderRadius: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 20 }}>
          <ShieldOff style={{ width: 14, height: 14, color: "#f59e0b" }} />
          <span style={{ fontSize: 14, fontWeight: 700, color: "#e5e5e5" }}>Golden Dataset Evaluation (RAGAS Extension)</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {[
            { scenario: "Large-Document Scoping (Deep Appendix Routing)", precision: 0.92, recall: 0.88, latency: "450ms" },
            { scenario: "Cross-Document Reasoning (Report Comparison)", precision: 0.85, recall: 0.81, latency: "820ms" }
          ].map((test, idx) => (
             <div key={idx} style={{ background: "#111", border: "1px solid #222", borderRadius: 8, padding: 16 }}>
               <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                 <h4 style={{ fontSize: 13, fontWeight: 600, color: "#fafafa" }}>{test.scenario}</h4>
                 <span style={{ fontSize: 11, color: "#888", fontFamily: "'JetBrains Mono', monospace" }}>Avg Latency: <span style={{ color: "#a78bfa" }}>{test.latency}</span></span>
               </div>
               <div style={{ display: "flex", gap: 24 }}>
                 <div style={{ flex: 1 }}>
                   <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                     <span style={{ fontSize: 11, color: "#666" }}>Precision</span>
                     <span style={{ fontSize: 11, color: "#22c55e", fontFamily: "'JetBrains Mono', monospace" }}>{test.precision}</span>
                   </div>
                   <div style={{ height: 6, background: "#222", borderRadius: 99, overflow: "hidden" }}>
                     <div style={{ width: `${test.precision * 100}%`, height: "100%", background: "#22c55e", borderRadius: 99 }} />
                   </div>
                 </div>
                 <div style={{ flex: 1 }}>
                   <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                     <span style={{ fontSize: 11, color: "#666" }}>Recall</span>
                     <span style={{ fontSize: 11, color: "#3b82f6", fontFamily: "'JetBrains Mono', monospace" }}>{test.recall}</span>
                   </div>
                   <div style={{ height: 6, background: "#222", borderRadius: 99, overflow: "hidden" }}>
                     <div style={{ width: `${test.recall * 100}%`, height: "100%", background: "#3b82f6", borderRadius: 99 }} />
                   </div>
                 </div>
               </div>
             </div>
          ))}
        </div>
      </div>
    </div>
  );
}
