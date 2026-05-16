"use client";

interface CitationBadgeProps {
  chunkId: string;
  index: number | string;
  page?: number;
  score?: number;
  onClick?: (chunkId: string) => void;
}

export default function CitationBadge({ chunkId, index, page, score, onClick }: CitationBadgeProps) {
  return (
    <span
      onClick={(e) => {
        e.preventDefault();
        e.stopPropagation();
        onClick?.(chunkId);
      }}
      title={`Chunk: ${chunkId}${page ? ` · Page ${page}` : ""}${score ? ` · Score ${score.toFixed(3)}` : ""}`}
      className="citation-badge hover-lift"
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        minWidth: 22,
        height: 22,
        padding: "0 6px",
        borderRadius: 6,
        background: "rgba(167,139,250,0.1)",
        border: "1px solid rgba(167,139,250,0.2)",
        color: "#a78bfa",
        fontSize: 10,
        fontWeight: 700,
        fontFamily: "'JetBrains Mono', monospace",
        cursor: "pointer",
        margin: "0 4px",
      }}
    >
      {index}
    </span>
  );
}
