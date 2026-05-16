import { useState } from "react";
import { Activity, CheckCircle2, AlertCircle } from "lucide-react";

interface RAGEvaluatorProps {
  query: string;
  answer: string;
  contexts: string[];
}

export default function RAGEvaluator({ query, answer, contexts }: RAGEvaluatorProps) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    faithfulness: number;
    answer_relevance: number;
    context_relevance: number;
    reasoning: string;
  } | null>(null);

  const handleEvaluate = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/evaluate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, answer, contexts }),
      });
      if (res.ok) {
        setResult(await res.json());
      }
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  if (!result && !loading) {
    return (
      <button
        onClick={handleEvaluate}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          background: "#222",
          border: "1px solid #333",
          padding: "4px 10px",
          borderRadius: 6,
          fontSize: 11,
          color: "#aaa",
          cursor: "pointer",
          marginTop: 8,
        }}
        className="hover:bg-[#333] hover:text-white transition-colors"
      >
        <Activity size={12} /> Evaluate RAG
      </button>
    );
  }

  if (loading) {
    return (
      <div style={{ marginTop: 8, fontSize: 11, color: "#888", display: "flex", alignItems: "center", gap: 6 }}>
        <span className="animate-pulse" style={{ display: "inline-block", width: 6, height: 6, borderRadius: "50%", background: "#22c55e" }} />
        Evaluating response with LLM-as-a-judge...
      </div>
    );
  }

  if (result) {
    return (
      <div style={{ marginTop: 12, padding: 12, background: "#1a1a1a", border: "1px solid #333", borderRadius: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8 }}>
          <CheckCircle2 size={14} color="#22c55e" />
          <span style={{ fontSize: 12, fontWeight: 600, color: "#eee" }}>RAG Evaluation Metrics</span>
        </div>
        <div style={{ display: "flex", gap: 16, marginBottom: 8 }}>
          <Metric label="Faithfulness" score={result.faithfulness} />
          <Metric label="Answer Rel." score={result.answer_relevance} />
          <Metric label="Context Rel." score={result.context_relevance} />
        </div>
        <p style={{ fontSize: 11, color: "#aaa", margin: 0, fontStyle: "italic" }}>
          "{result.reasoning}"
        </p>
      </div>
    );
  }

  return null;
}

function Metric({ label, score }: { label: string; score: number }) {
  const getColor = (s: number) => {
    if (s >= 0.8) return "#22c55e";
    if (s >= 0.5) return "#eab308";
    return "#ef4444";
  };
  
  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <span style={{ fontSize: 10, color: "#888", textTransform: "uppercase" }}>{label}</span>
      <span style={{ fontSize: 14, fontWeight: 600, color: getColor(score) }}>
        {(score * 100).toFixed(0)}%
      </span>
    </div>
  );
}
