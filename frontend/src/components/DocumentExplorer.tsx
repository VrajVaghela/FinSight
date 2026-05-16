"use client";

import { useState, useRef, useEffect } from "react";
import { FileText, Layout, X, ChevronRight, BookOpen, Loader2, AlertCircle } from "lucide-react";
import { fetchFileSections, getFileDownloadUrl, fetchFileContent, lookupChunk } from "@/lib/api";

interface DocumentExplorerProps {
  chunkId?: string;
  chunkData?: {
    chunk_id: string;
    text: string;
    file_id: string;
    page_number?: number;
    table_html?: string;
    section_header?: string;
  };
  onClose?: () => void;
  projectId?: string;
  debugChunks?: Array<{
    chunk_id: string;
    text_snippet: string;
    page_number: number;
    section_header: string;
    score: number;
  }>;
}

interface TOCItem {
  id: string;
  title: string;
  page: number;
  sectionHeader: string;
  active?: boolean;
}

interface ResolvedChunk {
  chunk_id: string;
  file_id: string;
  section_header: string;
  page_number: number;
  text: string;
  table_html?: string;
}

export default function DocumentExplorer({
  chunkId,
  chunkData: chunkDataProp,
  onClose,
  projectId,
  debugChunks,
}: DocumentExplorerProps) {
  const [splitView, setSplitView] = useState(false);
  const [width, setWidth] = useState(480);
  const isDragging = useRef(false);
  const [tocItems, setTocItems] = useState<TOCItem[]>([]);
  const [tocLoading, setTocLoading] = useState(false);
  const [fileName, setFileName] = useState<string>("");
  const [allChunks, setAllChunks] = useState<any[]>([]);
  const [contentLoading, setContentLoading] = useState(false);
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupError, setLookupError] = useState<string | null>(null);
  const [resolvedChunk, setResolvedChunk] = useState<ResolvedChunk | null>(null);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const contentContainerRef = useRef<HTMLDivElement>(null);

  // ─── Step 1: Resolve chunk_id → full metadata (file_id, section_header, etc.) ─
  useEffect(() => {
    if (!chunkId) {
      setResolvedChunk(null);
      setLookupError(null);
      return;
    }

    // Fast path A: prop already has file_id
    if (chunkDataProp?.file_id) {
      setResolvedChunk({
        chunk_id: chunkDataProp.chunk_id,
        file_id: chunkDataProp.file_id,
        section_header: chunkDataProp.section_header || "",
        page_number: chunkDataProp.page_number || 1,
        text: chunkDataProp.text || "",
        table_html: chunkDataProp.table_html,
      });
      return;
    }

    // Fast path B: look in debugChunks (same session, but missing file_id)
    // We still need file_id so we must hit the backend, but we can pre-populate text
    const debugMatch = debugChunks?.find((c) => c.chunk_id === chunkId);

    // Hit the backend to get file_id (chunk_id format is pX:cY which IS in Qdrant)
    setLookupLoading(true);
    setLookupError(null);
    setResolvedChunk(null);

    lookupChunk(chunkId, projectId)
      .then((data) => {
        if (data) {
          setResolvedChunk({
            chunk_id: data.chunk_id,
            file_id: data.file_id,
            section_header: data.section_header || debugMatch?.section_header || "",
            page_number: data.page_number || debugMatch?.page_number || 1,
            text: data.raw_text || debugMatch?.text_snippet || "",
            table_html: data.table_html || "",
          });
        } else {
          setLookupError("Chunk not found in the document index.");
        }
      })
      .catch((err) => {
        console.error("[DocumentExplorer] chunk lookup failed:", err);
        setLookupError("Failed to load document. Check that the file has been ingested.");
      })
      .finally(() => setLookupLoading(false));

  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chunkId, chunkDataProp?.file_id]);

  // ─── Step 2: Load TOC from file_id ──────────────────────────────────────────
  useEffect(() => {
    const fileId = resolvedChunk?.file_id;
    if (!fileId) { setTocItems([]); return; }

    const activeSH = resolvedChunk?.section_header?.trim() || "";
    setTocLoading(true);

    fetchFileSections(fileId)
      .then((data) => {
        setFileName(data.file_name || "");
        const items: TOCItem[] = data.sections.map((s) => ({
          id: s.id,
          title: s.title,
          page: s.page,
          sectionHeader: s.title.trim(),
          active: activeSH ? s.title.trim() === activeSH : s.id === resolvedChunk?.chunk_id,
        }));
        setTocItems(items);

        // Non-PDF: load all chunks for inline rendering
        if (data.file_name && !data.file_name.toLowerCase().endsWith(".pdf")) {
          setContentLoading(true);
          fetchFileContent(fileId)
            .then((res) => {
              setAllChunks(res.chunks);
              setTimeout(() => {
                document.getElementById(`chunk-${resolvedChunk?.chunk_id}`)
                  ?.scrollIntoView({ behavior: "smooth", block: "center" });
              }, 150);
            })
            .catch(console.error)
            .finally(() => setContentLoading(false));
        }
      })
      .catch(() => {
        // Fallback TOC from debugChunks
        if (debugChunks?.length) {
          const seen = new Map<string, TOCItem>();
          debugChunks.forEach((c) => {
            const header = c.section_header?.trim();
            if (header && !seen.has(header)) {
              seen.set(header, {
                id: c.chunk_id,
                title: header,
                page: c.page_number,
                sectionHeader: header,
                active: activeSH ? header === activeSH : c.chunk_id === resolvedChunk?.chunk_id,
              });
            }
          });
          setTocItems(Array.from(seen.values()).sort((a, b) => a.page - b.page));
        }
      })
      .finally(() => setTocLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resolvedChunk?.file_id]);

  // ─── Step 3: Sync active TOC item when resolvedChunk changes ────────────────
  useEffect(() => {
    if (!resolvedChunk) return;
    const activeSH = resolvedChunk.section_header?.trim() || "";
    setTocItems((prev) =>
      prev.map((item) => ({
        ...item,
        active: activeSH
          ? item.sectionHeader === activeSH
          : item.id === resolvedChunk.chunk_id,
      }))
    );
    if (resolvedChunk.chunk_id && allChunks.length > 0) {
      setTimeout(() => {
        document.getElementById(`chunk-${resolvedChunk.chunk_id}`)
          ?.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 50);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resolvedChunk?.chunk_id]);

  // ─── Resize ───────────────────────────────────────────────────────────────────
  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!isDragging.current) return;
      const w = window.innerWidth - e.clientX;
      if (w > 300 && w < 800) setWidth(w);
    };
    const onUp = () => { isDragging.current = false; document.body.style.cursor = "default"; };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
    return () => { document.removeEventListener("mousemove", onMove); document.removeEventListener("mouseup", onUp); };
  }, []);

  // ─── TOC click ────────────────────────────────────────────────────────────────
  const handleTOCClick = (item: TOCItem) => {
    setTocItems((prev) => prev.map((t) => ({ ...t, active: t.sectionHeader === item.sectionHeader })));
    if (fileName && !fileName.toLowerCase().endsWith(".pdf")) {
      let el = document.getElementById(`chunk-${item.id}`);
      if (!el) {
        const match = allChunks.find((c) => (c.section_header || "").trim() === item.sectionHeader);
        if (match) el = document.getElementById(`chunk-${match.chunk_id}`);
      }
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
        el.style.transition = "background 0.2s ease";
        el.style.background = "rgba(167,139,250,0.35)";
        setTimeout(() => { if (el) el.style.background = ""; }, 900);
      }
    }
  };

  const parsedPageMatch = chunkId?.match(/^p(\d+):/i) || resolvedChunk?.chunk_id?.match(/^p(\d+):/i);
  const parsedPage = parsedPageMatch ? parseInt(parsedPageMatch[1], 10) : null;
  const pdfPage = parsedPage || resolvedChunk?.page_number || 1;
  const fileId = resolvedChunk?.file_id;
  const pdfUrl = fileId ? `${getFileDownloadUrl(fileId)}#page=${pdfPage}` : null;
  const isPDF = !fileName || fileName.toLowerCase().endsWith(".pdf");

  return (
    <div
      style={{ width, height: "100%", borderLeft: "1px solid #2a2a2a", background: "#0a0a0a", display: "flex", flexDirection: "column", position: "relative" }}
      className="animate-slide-left"
    >
      {/* Resizer */}
      <div
        onMouseDown={(e) => { e.preventDefault(); isDragging.current = true; document.body.style.cursor = "col-resize"; }}
        style={{ position: "absolute", left: -4, top: 0, bottom: 0, width: 8, cursor: "col-resize", zIndex: 10 }}
      />

      {/* Header */}
      <div style={{ padding: "16px 20px", borderBottom: "1px solid #2a2a2a", display: "flex", justifyContent: "space-between", alignItems: "center", background: "#111" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1, overflow: "hidden" }}>
          <FileText size={16} color="#a78bfa" />
          <h3 style={{ fontSize: 14, fontWeight: 600, color: "#fafafa", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: width - 120 }}>
            {fileName || (resolvedChunk ? `Chunk ${resolvedChunk.chunk_id}` : "Document Explorer")}
          </h3>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => setSplitView(!splitView)} title="Toggle Split View"
            style={{ background: splitView ? "rgba(167,139,250,0.15)" : "transparent", border: "1px solid", borderColor: splitView ? "#a78bfa" : "#333", padding: 6, borderRadius: 6, color: splitView ? "#a78bfa" : "#888", cursor: "pointer", transition: "all 0.2s ease" }}>
            <Layout size={14} />
          </button>
          {onClose && (
            <button onClick={onClose} title="Close"
              style={{ background: "transparent", border: "1px solid #333", padding: 6, borderRadius: 6, color: "#888", cursor: "pointer", transition: "all 0.2s ease" }}
              className="hover:text-red-400 hover:border-red-400">
              <X size={14} />
            </button>
          )}
        </div>
      </div>

      <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>
        {/* Document Viewer */}
        <div style={{ flex: 1, background: "#151515", display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {/* Info bar */}
          <div style={{ padding: "8px 16px 0" }}>
            <div style={{ background: "#222", borderRadius: 4, padding: "4px 12px", display: "inline-flex", fontSize: 11, color: "#aaa", gap: 8, alignItems: "center" }}>
              {lookupLoading ? (
                <><Loader2 size={10} className="animate-spin" /><span>Resolving chunk…</span></>
              ) : resolvedChunk ? (
                <>
                  <span>{resolvedChunk.chunk_id}</span>
                  <span style={{ color: "#555" }}>·</span>
                  <span>Page {resolvedChunk.page_number}</span>
                  {resolvedChunk.section_header && <>
                    <span style={{ color: "#555" }}>·</span>
                    <span style={{ color: "#a78bfa", maxWidth: 180, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{resolvedChunk.section_header}</span>
                  </>}
                </>
              ) : lookupError ? (
                <><AlertCircle size={10} color="#ef4444" /><span style={{ color: "#ef4444" }}>{lookupError}</span></>
              ) : (
                "Click a citation to open the source document"
              )}
            </div>
          </div>

          <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: 16, overflow: "hidden" }}>
            {lookupLoading ? (
              <div style={{ flex: 1, display: "flex", justifyContent: "center", alignItems: "center" }}>
                <Loader2 size={24} className="animate-spin" color="#a78bfa" />
              </div>
            ) : lookupError ? (
              <div style={{ flex: 1, display: "flex", justifyContent: "center", alignItems: "center", flexDirection: "column", gap: 12, color: "#555" }}>
                <AlertCircle size={32} color="#444" />
                <span style={{ fontSize: 13 }}>{lookupError}</span>
                <span style={{ fontSize: 11, color: "#444" }}>Make sure the document has been fully ingested.</span>
              </div>
            ) : pdfUrl && !splitView && isPDF ? (
              <iframe ref={iframeRef} src={pdfUrl}
                style={{ flex: 1, width: "100%", border: "none", borderRadius: 8, background: "#fff", boxShadow: "0 4px 20px rgba(0,0,0,0.5)" }}
                title="PDF Document Viewer" />
            ) : (
              <div ref={contentContainerRef}
                style={{ flex: 1, background: "#fff", borderRadius: 8, padding: 24, boxShadow: "0 4px 20px rgba(0,0,0,0.5)", overflow: "auto" }}>
                {contentLoading ? (
                  <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: "100%" }}>
                    <Loader2 size={24} className="animate-spin" color="#a78bfa" />
                  </div>
                ) : allChunks.length > 0 ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                    {allChunks.map((chunk) => {
                      const isActive = chunk.chunk_id === resolvedChunk?.chunk_id;
                      const activeSH = tocItems.find((t) => t.active)?.sectionHeader;
                      const isSection = activeSH && (chunk.section_header || "").trim() === activeSH;
                      return (
                        <div key={chunk.chunk_id} id={`chunk-${chunk.chunk_id}`}
                          style={{
                            color: "#333", fontSize: 14, lineHeight: 1.6, whiteSpace: "pre-wrap",
                            padding: "12px", borderRadius: "8px",
                            background: isActive ? "rgba(167,139,250,0.15)" : isSection ? "rgba(167,139,250,0.06)" : "transparent",
                            borderLeft: isActive ? "4px solid #a78bfa" : isSection ? "4px solid rgba(167,139,250,0.35)" : "4px solid transparent",
                            transition: "all 0.3s ease",
                          }}>
                          {chunk.table_html
                            ? <div className="markdown-body" dangerouslySetInnerHTML={{ __html: chunk.table_html }} style={{ overflowX: "auto" }} />
                            : chunk.raw_text}
                        </div>
                      );
                    })}
                  </div>
                ) : resolvedChunk ? (
                  <div style={{ color: "#333", fontSize: 14, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                    {resolvedChunk.table_html
                      ? <div className="markdown-body" dangerouslySetInnerHTML={{ __html: resolvedChunk.table_html }} style={{ overflowX: "auto" }} />
                      : resolvedChunk.text}
                  </div>
                ) : (
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#999", flexDirection: "column", gap: 12 }}>
                    <FileText size={32} color="#ddd" />
                    <span style={{ fontSize: 13, textAlign: "center" }}>Click a citation badge in the chat to view the source chunk here.</span>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Split view */}
          {splitView && resolvedChunk && (
            <div style={{ flex: 1, display: "flex", flexDirection: "column", padding: 16, borderTop: "2px dashed #333", background: "#111" }}>
              <div style={{ background: "#222", borderRadius: 4, padding: "4px 12px", marginBottom: 12, alignSelf: "flex-start", fontSize: 11, color: "#aaa" }}>
                Chunk {resolvedChunk.chunk_id}
              </div>
              <div style={{ flex: 1, background: "#fff", borderRadius: 8, padding: 24, overflow: "auto" }}>
                <div style={{ color: "#333", fontSize: 14, lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
                  {resolvedChunk.table_html
                    ? <div className="markdown-body" dangerouslySetInnerHTML={{ __html: resolvedChunk.table_html }} style={{ overflowX: "auto" }} />
                    : resolvedChunk.text}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* TOC */}
        <div style={{ width: splitView ? 0 : 200, opacity: splitView ? 0 : 1, borderLeft: "1px solid #2a2a2a", background: "#111", overflowY: "auto", transition: "all 0.3s ease", flexShrink: 0 }}>
          <div style={{ padding: "12px 16px" }}>
            <p style={{ fontSize: 10, fontWeight: 700, color: "#666", textTransform: "uppercase", marginBottom: 12, display: "flex", alignItems: "center", gap: 6 }}>
              <BookOpen size={10} /> Table of Contents
            </p>
            {tocLoading ? (
              <div style={{ display: "flex", alignItems: "center", gap: 6, padding: 8 }}>
                <Loader2 size={12} className="animate-spin" color="#a78bfa" />
                <span style={{ fontSize: 11, color: "#666" }}>Loading…</span>
              </div>
            ) : tocItems.length === 0 ? (
              <p style={{ fontSize: 11, color: "#555", fontStyle: "italic", padding: "8px 4px" }}>
                {lookupLoading ? "Resolving document…" : resolvedChunk ? "No sections found." : "No document selected."}
              </p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                {tocItems.map((item) => (
                  <button key={item.id} onClick={() => handleTOCClick(item)}
                    style={{
                      display: "flex", alignItems: "center", gap: 6, padding: "7px 8px",
                      background: item.active ? "rgba(34,197,94,0.1)" : "transparent",
                      border: "none", borderRadius: 6, cursor: "pointer", textAlign: "left",
                      color: item.active ? "#22c55e" : "#888",
                      marginLeft: item.title.match(/^\d+\.\d+/) ? 12 : 0,
                      transition: "all 0.15s ease",
                    }}>
                    <ChevronRight size={10} style={{ flexShrink: 0, opacity: item.active ? 1 : 0.4 }} />
                    <span style={{ fontSize: 12, fontWeight: item.active ? 600 : 500, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {item.title}
                    </span>
                    <span style={{ fontSize: 10, color: item.active ? "#22c55e" : "#555", flexShrink: 0, fontFamily: "'JetBrains Mono', monospace" }}>
                      p{item.page}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
