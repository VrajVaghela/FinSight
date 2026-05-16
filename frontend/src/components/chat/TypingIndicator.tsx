"use client";

import { useEffect, useState } from "react";
import { Sparkles, FileSearch } from "lucide-react";

const processingTexts = [
  "Analyzing context...",
  "Searching documents...",
  "Generating insights...",
  "Processing query..."
];

export default function TypingIndicator() {
  const [textIndex, setTextIndex] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setTextIndex((prev) => (prev + 1) % processingTexts.length);
    }, 2500);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ maxWidth: 720, marginRight: "auto" }}>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        <div
          style={{
            width: 32,
            height: 32,
            background: "rgba(34,197,94,0.1)",
            borderRadius: 8,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
            border: "1px solid rgba(34,197,94,0.2)",
          }}
          className="animate-pulse-soft"
        >
          <Sparkles size={16} color="#22c55e" />
        </div>
        <div
          style={{
            display: "flex",
            gap: 12,
            padding: "12px 20px",
            background: "linear-gradient(90deg, rgba(25,25,25,0.8) 0%, rgba(20,20,20,0.8) 100%)",
            border: "1px solid #2a2a2a",
            borderRadius: "4px 20px 20px 20px",
            alignItems: "center",
          }}
        >
          <div style={{ display: "flex", gap: 4 }}>
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: "#22c55e",
                  animation: `typing-dot 1.4s ease-in-out ${i * 0.2}s infinite`,
                }}
              />
            ))}
          </div>
          <span
            key={textIndex}
            className="animate-fade-in"
            style={{
              fontSize: 13,
              fontWeight: 500,
              color: "#888",
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            {processingTexts[textIndex]}
          </span>
        </div>
      </div>
    </div>
  );
}
