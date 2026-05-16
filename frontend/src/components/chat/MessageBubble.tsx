"use client";

import { Sparkles } from "lucide-react";
import CitationBadge from "./CitationBadge";
import DiffSuggestionWidget from "./DiffSuggestionWidget";
import type { ChatMessage } from "@/types";

interface MessageBubbleProps {
  role: "user" | "assistant" | "refusal";
  content: string;
  timestamp?: string;
  citations?: Array<{ chunkId: string; page?: number; score?: number }>;
  isStreaming?: boolean;
  diffSuggestion?: ChatMessage["diffSuggestion"];
  onCitationClick?: (chunkId: string) => void;
}

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import dynamic from "next/dynamic";

const MermaidDiagram = dynamic(() => import("./MermaidDiagram"), { ssr: false });

// ... existing imports ...

export default function MessageBubble({
  role,
  content,
  timestamp,
  citations,
  isStreaming,
  diffSuggestion,
  onCitationClick,
}: MessageBubbleProps) {
  // Convert [pX:cY] or plain pX:cY to [pX:cY](cite:pX:cY) so ReactMarkdown parses it as a link
  const processContent = (text: string) => {
    let processed = text;
    // Replace standalone pX:cY with [pX:cY](cite:pX:cY) case-insensitively
    processed = processed.replace(/(?<!cite:|\[)(p\d+:c\d+)(?!\]|\))/gi, "[$1](cite:$1)");
    // Replace [pX:cY] without a link to [pX:cY](cite:pX:cY)
    processed = processed.replace(/\[(p\d+:c\d+)\](?!\()/gi, "[$1](cite:$1)");
    
    // Hide inline GenUI JSON blocks that have been parsed already
    processed = processed.replace(/```json\s*\{\s*"component"[\s\S]*?```/gi, "");
    
    return processed;
  };

  if (role === "user") {
    return (
      <div className="animate-fade-up" style={{ maxWidth: 640, marginLeft: "auto" }}>
        <div
          style={{
            background: "#fafafa",
            color: "#0a0a0a",
            padding: "14px 18px",
            borderRadius: "20px 20px 4px 20px",
            fontSize: 14,
            lineHeight: 1.65,
            fontWeight: 500,
          }}
        >
          {content}
        </div>
        {timestamp && (
          <p style={{
            fontSize: 10,
            color: "#444",
            marginTop: 6,
            textAlign: "right",
            fontFamily: "'JetBrains Mono', monospace",
            fontWeight: 500,
          }}>
            {timestamp}
          </p>
        )}
      </div>
    );
  }

  if (role === "refusal") {
    return (
      <div className="animate-fade-up" style={{ maxWidth: 720, marginRight: "auto" }}>
        <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
          <div
            style={{
              width: 32,
              height: 32,
              background: "rgba(239,68,68,0.1)",
              borderRadius: 8,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              flexShrink: 0,
            }}
          >
            <Sparkles style={{ width: 14, height: 14, color: "#ef4444" }} />
          </div>
          <div
            style={{
              padding: "14px 18px",
              background: "rgba(239,68,68,0.04)",
              border: "1px solid rgba(239,68,68,0.12)",
              borderRadius: "4px 20px 20px 20px",
              fontSize: 14,
              lineHeight: 1.65,
              color: "#fca5a5",
            }}
          >
            {content}
          </div>
        </div>
      </div>
    );
  }

  // Assistant
  return (
    <div className="animate-fade-up" style={{ maxWidth: 720, marginRight: "auto" }}>
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
          }}
        >
          <Sparkles style={{ width: 14, height: 14, color: "#22c55e" }} />
        </div>
        <div style={{ flex: 1 }}>
          <div
            style={{
              padding: "14px 18px",
              background: "#191919",
              border: "1px solid #2a2a2a",
              borderRadius: "4px 20px 20px 20px",
            }}
          >
            <div className="prose prose-invert prose-sm max-w-none">
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  a: ({ node, href, children, ...props }) => {
                    // Check if the link itself or its text contains a chunk coordinate
                    const chunkMatch = href?.match(/p\d+:c\d+/i) || children?.toString().match(/p\d+:c\d+/i);
                    const isCitationHref = href?.startsWith("cite:") || chunkMatch;
                    
                    if (isCitationHref) {
                      let chunkId = href;
                      if (href?.startsWith("cite:")) {
                        chunkId = href.replace("cite:", "");
                      } else if (chunkMatch) {
                        chunkId = chunkMatch[0];
                      }
                      // Clean up any remaining artifacts like leading '#' or '/'
                      chunkId = chunkId?.replace(/^[#/]+/, "")?.toLowerCase() || "";
                      
                      return <CitationBadge chunkId={chunkId} index={children?.toString() || chunkId} onClick={onCitationClick} />;
                    }
                    
                    return (
                      <a 
                        href={href} 
                        {...props}
                        onClick={(e) => {
                          // Aggressively prevent default to stop page resets
                          e.preventDefault();
                          if (href && (href.startsWith('http') || href.startsWith('mailto'))) {
                            window.open(href, '_blank', 'noopener,noreferrer');
                          }
                        }}
                      >
                        {children}
                      </a>
                    );
                  },
                  table: ({ node, ...props }) => (
                    <div className="overflow-x-auto my-4">
                      <table className="min-w-full divide-y divide-[#333] border border-[#333] rounded-md" {...props} />
                    </div>
                  ),
                  th: ({ node, ...props }) => <th className="px-3 py-2 bg-[#222] text-left text-xs font-medium text-gray-300 uppercase tracking-wider border-b border-[#333]" {...props} />,
                  td: ({ node, ...props }) => <td className="px-3 py-2 text-sm text-gray-300 border-b border-[#333]" {...props} />,
                  code: ({ node, className, children, ...props }: any) => {
                    const match = /language-(\w+)/.exec(className || "");
                    if (match && match[1] === "mermaid") {
                      return <MermaidDiagram chart={String(children).replace(/\n$/, "")} />;
                    }
                    return (
                      <code className={className} {...props}>
                        {children}
                      </code>
                    );
                  },
                }}
              >
                {processContent(content)}
              </ReactMarkdown>
            </div>
            {isStreaming && (
              <span
                className="animate-pulse-soft"
                style={{
                  display: "inline-block",
                  width: 2,
                  height: 16,
                  background: "#22c55e",
                  marginLeft: 2,
                  verticalAlign: "middle",
                  borderRadius: 1,
                }}
              />
            )}
          </div>

          {/* Citations */}
          {citations && citations.length > 0 && (
            <div className="animate-fade-in" style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
              {citations.map((cite, i) => (
                <CitationBadge
                  key={cite.chunkId}
                  chunkId={cite.chunkId}
                  index={(cite as any).source_number || `[cite:${i + 1}]`}
                  page={cite.page}
                  score={cite.score}
                  onClick={onCitationClick}
                />
              ))}
            </div>
          )}

          {/* Diff Suggestion */}
          {diffSuggestion && (
            <div style={{ marginTop: 12 }}>
              <DiffSuggestionWidget diff={diffSuggestion} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
