"use client";

import { useCallback, useState, useEffect } from "react";
import Link from "next/link";
import { UploadCloud, File, CheckCircle, AlertCircle, Loader } from "lucide-react";
import { useIngestionStatus } from "@/hooks/useIngestionStatus";
import { uploadFile } from "@/lib/api";

interface FileUploadZoneProps {
  projectId: string;
}

type UploadState = "idle" | "uploading" | "processing" | "ready" | "error";

export default function FileUploadZone({ projectId }: FileUploadZoneProps) {
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [fileName, setFileName] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");

  const { status: ingestionStatus, startPolling } = useIngestionStatus();

  useEffect(() => {
    if (ingestionStatus === "ready") setUploadState("ready");
    else if (ingestionStatus === "failed") {
      setUploadState("error");
      setErrorMsg("Ingestion failed");
    }
  }, [ingestionStatus]);

  const handleFile = useCallback(
    async (file: File) => {
      if (!file.name.endsWith(".pdf")) {
        setUploadState("error");
        setErrorMsg("Only PDF files are supported");
        return;
      }
      setFileName(file.name);
      setUploadState("uploading");
      setErrorMsg("");
      try {
        const response = await uploadFile(projectId, file);
        startPolling(response.file_id);
        setUploadState("processing");
      } catch (err) {
        setUploadState("error");
        setErrorMsg(err instanceof Error ? err.message : "Upload failed");
      }
    },
    [projectId, startPolling]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const statusConfig = {
    idle: { icon: UploadCloud, color: "#555", label: "Drop PDF here or click to browse" },
    uploading: { icon: Loader, color: "#3b82f6", label: `Uploading ${fileName}...` },
    processing: { icon: Loader, color: "#a78bfa", label: `Processing ${fileName}...` },
    ready: { icon: CheckCircle, color: "#22c55e", label: `${fileName} ready` },
    error: { icon: AlertCircle, color: "#ef4444", label: errorMsg || "Error" },
  };

  const status = statusConfig[uploadState];

  return (
    <div
      className={`animate-fade-up ${dragOver ? "drop-zone-active" : ""}`}
      onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      onClick={() => {
        if (uploadState === "idle" || uploadState === "error") {
          const input = document.createElement("input");
          input.type = "file";
          input.accept = ".pdf";
          input.onchange = (e) => {
            const file = (e.target as HTMLInputElement).files?.[0];
            if (file) handleFile(file);
          };
          input.click();
        }
      }}
      style={{
        width: "100%",
        maxWidth: 480,
        padding: 48,
        border: `2px dashed ${dragOver ? "#22c55e" : "#2a2a2a"}`,
        borderRadius: 20,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        cursor: uploadState === "idle" || uploadState === "error" ? "pointer" : "default",
        transition: "all 0.3s cubic-bezier(0.16,1,0.3,1)",
        background: dragOver ? "rgba(34,197,94,0.03)" : "transparent",
      }}
    >
      <status.icon
        style={{
          width: 32,
          height: 32,
          color: status.color,
          marginBottom: 16,
          ...(uploadState === "uploading" || uploadState === "processing"
            ? { animation: "spin 1s linear infinite" }
            : {}),
        }}
      />
      <p style={{ fontSize: 14, fontWeight: 600, color: "#aaa", marginBottom: 8, textAlign: "center" }}>
        {status.label}
      </p>
      <p style={{ fontSize: 12, color: "#444", textAlign: "center" }}>
        {uploadState === "idle" ? "Supports PDF files up to 50MB" : ""}
      </p>

      {uploadState === "ready" && (
        <Link
          href={`/projects/${projectId}/chat`}
          style={{
            marginTop: 16,
            padding: "8px 16px",
            background: "#22c55e",
            border: "none",
            borderRadius: 8,
            color: "#fff",
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
            textDecoration: "none",
          }}
        >
          Start Chatting
        </Link>
      )}

      {uploadState === "error" && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            setUploadState("idle");
            setErrorMsg("");
          }}
          style={{
            marginTop: 16,
            padding: "8px 16px",
            background: "#222",
            border: "1px solid #333",
            borderRadius: 8,
            color: "#aaa",
            fontSize: 12,
            fontWeight: 600,
            cursor: "pointer",
          }}
        >
          Try Again
        </button>
      )}
    </div>
  );
}
