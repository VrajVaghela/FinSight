"use client";

import React, { useEffect, useRef, useState } from "react";
import mermaid from "mermaid";

export default function MermaidDiagram({ chart }: { chart: string }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [svgContent, setSvgContent] = useState<string>("");
  const [error, setError] = useState<string>("");

  useEffect(() => {
    mermaid.initialize({
      startOnLoad: false,
      theme: "dark",
      securityLevel: "loose",
      fontFamily: "'JetBrains Mono', monospace",
    });

    const renderChart = async () => {
      if (!containerRef.current || !chart) return;
      try {
        const id = `mermaid-${Math.random().toString(36).substr(2, 9)}`;
        const { svg } = await mermaid.render(id, chart);
        setSvgContent(svg);
        setError("");
      } catch (err: any) {
        console.error("Mermaid parsing error:", err);
        setError(err?.message || "Failed to render flowchart/diagram");
      }
    };

    renderChart();
  }, [chart]);

  return (
    <div className="my-4 animate-fade-up">
      {error ? (
        <div className="p-4 bg-red-900/20 border border-red-500/30 rounded-md text-red-400 text-sm font-mono overflow-auto whitespace-pre-wrap">
          {error}
        </div>
      ) : (
        <div
          ref={containerRef}
          className="flex justify-center p-4 bg-[#111] rounded-lg border border-[#333] overflow-auto"
          dangerouslySetInnerHTML={{ __html: svgContent }}
        />
      )}
    </div>
  );
}
