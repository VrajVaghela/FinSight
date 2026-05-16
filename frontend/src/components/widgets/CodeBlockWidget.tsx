"use client";

import { useState } from "react";
import { Copy, Check, ChevronDown, ChevronUp } from "lucide-react";
import type { CodeBlockData } from "@/types";

interface CodeBlockWidgetProps {
  data: CodeBlockData;
}

export default function CodeBlockWidget({ data }: CodeBlockWidgetProps) {
  const { language, code, result } = data;
  const [copied, setCopied] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      className="animate-fade-up"
      style={{
        background: "#0a0a0a",
        border: "1px solid #2a2a2a",
        borderRadius: 14,
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          padding: "10px 16px",
          borderBottom: "1px solid #1e1e1e",
        }}
      >
        <span
          style={{
            fontSize: 10,
            fontWeight: 700,
            color: "#a78bfa",
            textTransform: "uppercase",
            fontFamily: "'JetBrains Mono', monospace",
            letterSpacing: "0.06em",
          }}
        >
          {language}
        </span>
        <div style={{ display: "flex", gap: 4 }}>
          <button
            onClick={() => setExpanded(!expanded)}
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
            {expanded ? <ChevronUp style={{ width: 14, height: 14 }} /> : <ChevronDown style={{ width: 14, height: 14 }} />}
          </button>
          <button
            onClick={handleCopy}
            style={{
              width: 28,
              height: 28,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: 6,
              border: "none",
              background: "transparent",
              color: copied ? "#22c55e" : "#555",
              cursor: "pointer",
            }}
          >
            {copied ? <Check style={{ width: 14, height: 14 }} /> : <Copy style={{ width: 14, height: 14 }} />}
          </button>
        </div>
      </div>

      {/* Code */}
      <pre
        style={{
          padding: 16,
          fontSize: 12,
          lineHeight: 1.6,
          color: "#d4d4d4",
          overflow: "auto",
          maxHeight: expanded ? "none" : 160,
          fontFamily: "'JetBrains Mono', monospace",
          margin: 0,
        }}
      >
        {code}
      </pre>

      {/* Result */}
      {result && (
        <div
          style={{
            padding: "12px 16px",
            borderTop: "1px solid #1e1e1e",
            background: "rgba(34,197,94,0.03)",
          }}
        >
          <p style={{ fontSize: 10, fontWeight: 700, color: "#22c55e", marginBottom: 4, fontFamily: "'JetBrains Mono', monospace" }}>
            OUTPUT
          </p>
          <p style={{ fontSize: 12, color: "#aaa", fontFamily: "'JetBrains Mono', monospace" }}>
            {result}
          </p>
        </div>
      )}
    </div>
  );
}
