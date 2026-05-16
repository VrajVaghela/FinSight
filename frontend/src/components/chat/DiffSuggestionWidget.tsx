"use client";

import { useState } from "react";
import { FileCode, Check, Copy, ChevronDown, ChevronUp } from "lucide-react";
import type { DiffSuggestion } from "@/types";

interface DiffSuggestionWidgetProps {
  diff: DiffSuggestion;
}

export default function DiffSuggestionWidget({ diff }: DiffSuggestionWidgetProps) {
  const [expanded, setExpanded] = useState(true);
  const [applied, setApplied] = useState(false);

  return (
    <div
      className="animate-fade-up"
      style={{
        background: "#0c0c0c",
        border: "1px solid #2a2a2a",
        borderRadius: 14,
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "10px 16px",
          borderBottom: "1px solid #1e1e1e",
          background: "#111",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <FileCode style={{ width: 14, height: 14, color: "#a78bfa" }} />
          <span style={{
            fontSize: 12,
            fontWeight: 700,
            color: "#ccc",
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            {diff.filename}
          </span>
          <span style={{
            fontSize: 9,
            fontWeight: 700,
            color: "#555",
            background: "#1a1a1a",
            padding: "2px 6px",
            borderRadius: 4,
            textTransform: "uppercase",
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            {diff.language}
          </span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
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
            onClick={() => setApplied(true)}
            disabled={applied}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
              padding: "5px 10px",
              borderRadius: 6,
              border: "1px solid",
              borderColor: applied ? "rgba(34,197,94,0.3)" : "#333",
              background: applied ? "rgba(34,197,94,0.08)" : "#191919",
              color: applied ? "#22c55e" : "#aaa",
              fontSize: 11,
              fontWeight: 700,
              cursor: applied ? "default" : "pointer",
              transition: "all 0.2s ease",
              fontFamily: "'JetBrains Mono', monospace",
            }}
          >
            <Check style={{ width: 12, height: 12 }} />
            {applied ? "Applied" : "Apply"}
          </button>
        </div>
      </div>

      {/* Diff content */}
      {expanded && (
        <div style={{ overflow: "auto", maxHeight: 360 }}>
          {diff.hunks.map((hunk, hi) => (
            <div key={hi}>
              {/* Hunk header */}
              <div style={{
                padding: "4px 16px",
                fontSize: 10,
                color: "#555",
                background: "#0f0f0f",
                borderTop: hi > 0 ? "1px solid #1e1e1e" : "none",
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                @@ -{hunk.oldStart} +{hunk.newStart} @@
              </div>

              {/* Lines */}
              {hunk.lines.map((line, li) => {
                const isAdd = line.type === "add";
                const isRemove = line.type === "remove";
                return (
                  <div
                    key={li}
                    style={{
                      display: "flex",
                      alignItems: "stretch",
                      fontSize: 12,
                      fontFamily: "'JetBrains Mono', monospace",
                      lineHeight: "20px",
                      background: isAdd
                        ? "rgba(34,197,94,0.06)"
                        : isRemove
                        ? "rgba(239,68,68,0.06)"
                        : "transparent",
                      borderLeft: `3px solid ${
                        isAdd ? "#22c55e" : isRemove ? "#ef4444" : "transparent"
                      }`,
                    }}
                  >
                    {/* Gutter */}
                    <span
                      style={{
                        width: 32,
                        textAlign: "center",
                        color: isAdd ? "#22c55e" : isRemove ? "#ef4444" : "#333",
                        flexShrink: 0,
                        fontWeight: 700,
                        userSelect: "none",
                        padding: "0 4px",
                      }}
                    >
                      {isAdd ? "+" : isRemove ? "−" : " "}
                    </span>
                    {/* Code */}
                    <span
                      style={{
                        flex: 1,
                        padding: "0 16px 0 8px",
                        color: isAdd
                          ? "#86efac"
                          : isRemove
                          ? "#fca5a5"
                          : "#888",
                        whiteSpace: "pre",
                      }}
                    >
                      {line.content}
                    </span>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
