"use client";

import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { DataTableData } from "@/types";

interface DataTableWidgetProps {
  data: DataTableData;
}

export default function DataTableWidget({ data: tableData }: DataTableWidgetProps) {
  const title = tableData.caption;
  const columns = tableData.headers;
  const rows = tableData.rows.map(row =>
    Object.fromEntries(columns.map((col, i) => [col, row[i]]))
  );
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  const sorted = [...rows].sort((a, b) => {
    if (!sortCol) return 0;
    const av = a[sortCol] ?? "";
    const bv = b[sortCol] ?? "";
    const cmp = typeof av === "number" && typeof bv === "number" ? av - bv : String(av).localeCompare(String(bv));
    return sortDir === "asc" ? cmp : -cmp;
  });

  const toggleSort = (col: string) => {
    if (sortCol === col) setSortDir(sortDir === "asc" ? "desc" : "asc");
    else { setSortCol(col); setSortDir("asc"); }
  };

  return (
    <div
      className="animate-fade-up"
      style={{
        background: "#151515",
        border: "1px solid #2a2a2a",
        borderRadius: 14,
        overflow: "hidden",
      }}
    >
      <div style={{ padding: "16px 20px", borderBottom: "1px solid #2a2a2a" }}>
        <p style={{ fontSize: 12, fontWeight: 700, color: "#aaa" }}>{title}</p>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col}
                  onClick={() => toggleSort(col)}
                  style={{
                    padding: "10px 16px",
                    textAlign: "left",
                    fontSize: 10,
                    fontWeight: 700,
                    color: "#555",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    borderBottom: "1px solid #222",
                    cursor: "pointer",
                    userSelect: "none",
                    fontFamily: "'JetBrains Mono', monospace",
                    whiteSpace: "nowrap",
                  }}
                >
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
                    {col}
                    {sortCol === col && (
                      sortDir === "asc"
                        ? <ChevronUp style={{ width: 10, height: 10 }} />
                        : <ChevronDown style={{ width: 10, height: 10 }} />
                    )}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, i) => (
              <tr
                key={i}
                style={{
                  borderBottom: i < sorted.length - 1 ? "1px solid #1e1e1e" : "none",
                  transition: "background 0.1s ease",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "#191919"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
              >
                {columns.map((col) => (
                  <td
                    key={col}
                    style={{
                      padding: "10px 16px",
                      fontSize: 12,
                      color: "#aaa",
                      fontFamily: typeof row[col] === "number" ? "'JetBrains Mono', monospace" : "inherit",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {row[col]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
