// ──────────────────────────────────────────────
// Networking layer — all API calls live here
// No component ever calls fetch() directly
// ──────────────────────────────────────────────

import type { ProjectRecord, ChatRequest } from "@/types";

const API_BASE = "/api";
// File uploads bypass the Next.js proxy (10 MB body limit) and go direct to FastAPI
const BACKEND_DIRECT = "http://127.0.0.1:8000";

// ── Auth Helpers ────────────────────────────────
function getHeaders(extraHeaders: Record<string, string> = {}) {
  const headers: Record<string, string> = { ...extraHeaders };
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }
  return headers;
}

export async function login(email: string, password: string) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error("Login failed");
  return res.json();
}

export async function register(email: string, password: string) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error("Registration failed");
  return res.json();
}

// ── Health ──────────────────────────────────────
export async function checkHealth(): Promise<{ status: string; version: string }> {
  const res = await fetch(`${API_BASE}/health`, { headers: getHeaders() });
  if (!res.ok) throw new Error("Backend offline");
  return res.json();
}

// ── Projects ────────────────────────────────────
export async function fetchProjects(): Promise<ProjectRecord[]> {
  const res = await fetch(`${API_BASE}/projects`, { headers: getHeaders() });
  if (!res.ok) throw new Error("Failed to fetch projects");
  const projects = await res.json();
  return projects.map((project: ProjectRecord) => ({
    ...project,
    file_ids: project.file_ids || [],
  }));
}

export async function createProject(
  name: string,
  systemPrompt?: string
): Promise<ProjectRecord> {
  const res = await fetch(`${API_BASE}/projects`, {
    method: "POST",
    headers: getHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ name, system_prompt: systemPrompt || "" }),
  });
  if (!res.ok) {
    let detail = `Failed to create project (${res.status})`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // Keep the status-based message when the backend returns no JSON body.
    }
    throw new Error(detail);
  }
  const project = await res.json();
  return {
    ...project,
    file_ids: project.file_ids || [],
  };
}

export async function deleteProject(projectId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/projects/${projectId}`, {
    method: "DELETE",
    headers: getHeaders()
  });
  if (!res.ok) throw new Error("Failed to delete project");
}

export async function deleteFile(projectId: string, fileId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/files/${fileId}`, {
    method: "DELETE",
    headers: getHeaders()
  });
  if (!res.ok) throw new Error("Failed to delete file");
}

// ── File Upload ─────────────────────────────────
export async function uploadFile(
  projectId: string,
  file: File
): Promise<{ file_id: string; status: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${BACKEND_DIRECT}/api/projects/${projectId}/files`, {
    method: "POST",
    headers: getHeaders(),
    body: formData,
  });
  if (!res.ok) {
    let detail = `File upload failed (${res.status})`;
    try {
      const body = await res.json();
      detail = body.detail || detail;
    } catch {
      // Keep the status-based message when the backend returns no JSON body.
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function fetchFileStatus(
  fileId: string
): Promise<{ status: string; original_name: string }> {
  const res = await fetch(`${API_BASE}/files/${fileId}/status`, { headers: getHeaders() });
  if (!res.ok) throw new Error("Failed to fetch file status");
  return res.json();
}

export async function fetchIngestionStatus(
  projectId: string
): Promise<{ overall_status: string; files: any[] }> {
  const res = await fetch(`${API_BASE}/projects/${projectId}/status`, { headers: getHeaders() });
  if (!res.ok) throw new Error("Failed to fetch status");
  return res.json();
}

// ── Chat SSE Stream ─────────────────────────────
export async function openChatStream(
  request: ChatRequest,
  onEvent: (event: Record<string, unknown>) => void,
  onError: (error: Error) => void,
  onDone: () => void
): Promise<AbortController> {
  const controller = new AbortController();

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: getHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify(request),
      signal: controller.signal,
    });

    if (!res.ok) {
      onError(new Error(`Chat failed: ${res.status}`));
      onDone();
      return controller;
    }

    const reader = res.body?.getReader();
    if (!reader) {
      onError(new Error("No readable stream"));
      onDone();
      return controller;
    }

    const decoder = new TextDecoder();
    let buffer = "";

    const processStream = async () => {
      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            const trimmed = line.trim();
            if (trimmed.startsWith("data: ")) {
              const json = trimmed.slice(6);
              if (json === "[DONE]") continue;
              try {
                const event = JSON.parse(json);
                onEvent(event);
              } catch {
                // Skip malformed JSON
              }
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          onError(err as Error);
        }
      } finally {
        onDone();
      }
    };

    processStream();
  } catch (err) {
    if ((err as Error).name !== "AbortError") {
      onError(err as Error);
    }
    onDone();
  }

  return controller;
}

export async function fetchConversations() {
  const res = await fetch(`${API_BASE}/chat/conversations`, { headers: getHeaders() });
  if (!res.ok) throw new Error("Failed to fetch conversations");
  return res.json();
}

// ── Conversation History ────────────────────────
export async function fetchConversationHistory(conversationId: string) {
  const res = await fetch(`${API_BASE}/chat/history/${conversationId}`, { headers: getHeaders() });
  if (!res.ok) throw new Error("Failed to fetch history");
  return res.json();
}

// ── Retrieval Debug ─────────────────────────────
export async function fetchRetrievalDebug(runId: string) {
  const res = await fetch(`${API_BASE}/retrieval/debug?run_id=${runId}`, { headers: getHeaders() });
  if (!res.ok) throw new Error("Failed to fetch debug info");
  return res.json();
}

// ── File Download URL ───────────────────────────
export function getFileDownloadUrl(fileId: string): string {
  return `${API_BASE}/files/${fileId}/download`;
}

// ── File Sections (Table of Contents) ───────────
export async function fetchFileSections(
  fileId: string
): Promise<{ file_id: string; file_name: string; sections: { id: string; title: string; page: number }[] }> {
  const res = await fetch(`${API_BASE}/files/${fileId}/sections`, { headers: getHeaders() });
  if (!res.ok) throw new Error("Failed to fetch file sections");
  return res.json();
}

// ── File Content (Full document chunks) ─────────
export async function fetchFileContent(
  fileId: string
): Promise<{ file_id: string; file_name: string; chunks: { chunk_id: string; chunk_index: number; raw_text: string; table_html: string; is_table: boolean; section_header: string; page_number: number }[] }> {
  const res = await fetch(`${API_BASE}/files/${fileId}/content`, { headers: getHeaders() });
  if (!res.ok) throw new Error("Failed to fetch file content");
  return res.json();
}


// ── Chunk Lookup (resolve any chunk_id to full metadata) ─────────────────
export async function lookupChunk(
  chunkId: string,
  projectId?: string
): Promise<{
  chunk_id: string;
  file_id: string;
  section_header: string;
  page_number: number;
  raw_text: string;
  table_html: string;
  is_table: boolean;
} | null> {
  const params = new URLSearchParams({ chunk_id: chunkId });
  if (projectId) params.append("project_id", projectId);
  const res = await fetch(`${API_BASE}/chunks/lookup?${params}`, { headers: getHeaders() });
  if (!res.ok) return null;
  return res.json();
}
