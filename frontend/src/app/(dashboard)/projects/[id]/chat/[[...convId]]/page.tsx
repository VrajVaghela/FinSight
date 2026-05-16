"use client";

import { use, useState, useRef } from "react";
import Header from "@/components/Header";
import ChatContainer from "@/components/ChatContainer";
import DebugPanel from "@/components/debug/DebugPanel";
import DocumentExplorer from "@/components/DocumentExplorer";

type DebugChunk = {
  chunk_id: string;
  text_snippet: string;
  text: string;
  file_id: string;
  page_number?: number;
  section_header: string;
  score: number;
  table_html?: string;
};

export default function ChatPage({
  params,
}: {
  params: Promise<{ id: string; convId?: string[] }>;
}) {
  const { id, convId } = use(params);
  const conversationId = convId?.[0];
  const [debugOpen, setDebugOpen] = useState(false);
  const [debugData, setDebugData] = useState<Record<string, unknown> | null>(null);

  // Keep latest chunks in a ref — available even if state hasn't flushed yet
  const latestChunksRef = useRef<DebugChunk[]>([]);

  // Citation that was clicked — either an inline pX:cY or a real chunk UUID
  const [activeCitation, setActiveCitation] = useState<string | null>(null);

  const chunks = debugData?.chunks as DebugChunk[] | undefined;

  const handleDebugUpdate = (data: Record<string, unknown>) => {
    setDebugData(data);
    if (data.chunks) {
      latestChunksRef.current = data.chunks as DebugChunk[];
    }
  };

  // Build debugChunks array for DocumentExplorer's fast-path fallback
  const explorerDebugChunks = (chunks?.length ? chunks : latestChunksRef.current)?.map(
    (c) => ({
      chunk_id: c.chunk_id,
      text_snippet: c.text_snippet || c.text || "",
      page_number: c.page_number || 0,
      section_header: c.section_header || "",
      score: c.score || 0,
    })
  );

  return (
    <>
      <Header
        projectName={`Project ${id}`}
        onToggleDebug={() => setDebugOpen(!debugOpen)}
        debugOpen={debugOpen}
      />
      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Chat Area */}
        <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 400 }}>
          <ChatContainer
            key={conversationId || "new"}
            projectId={id}
            conversationId={conversationId}
            onDebugUpdate={handleDebugUpdate}
            onCitationClick={(chunkId) => setActiveCitation(chunkId)}
          />
        </div>

        {/* Document Explorer — self-fetches chunk data via backend when not in debugChunks */}
        {activeCitation && (
          <DocumentExplorer
            chunkId={activeCitation}
            projectId={id}
            debugChunks={explorerDebugChunks}
            onClose={() => setActiveCitation(null)}
          />
        )}

        {/* Debug Panel */}
        {debugOpen && debugData && (
          <div className="animate-slide-right" style={{ borderLeft: "1px solid #2a2a2a" }}>
            <DebugPanel data={debugData} onClose={() => setDebugOpen(false)} />
          </div>
        )}
      </div>
    </>
  );
}
