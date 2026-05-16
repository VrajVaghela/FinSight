// ──────────────────────────────────────────────
// Core Entity Types — shared between hooks & components
// ──────────────────────────────────────────────

export interface ProjectRecord {
  id: string;
  name: string;
  system_prompt: string | null;
  owner_id?: string;
  created_at: string;
  file_count?: number;
  file_ids?: string[];
  status: "pending" | "processing" | "ready" | "failed";
  documents?: DocumentRecord[];
  conversations?: ConversationRecord[];
  context?: string;
}

export interface DocumentRecord {
  id: string;
  name: string;
  size: number;
  status: "uploading" | "processing" | "ready" | "failed";
  pages?: number;
  uploaded_at: string;
}

export interface ConversationRecord {
  id: string;
  title: string;
  project_id: string | null; // null = standalone chat
  created_at: string;
  last_message_at: string;
  message_count: number;
}

export interface ChatMessage {
  role: "user" | "assistant" | "refusal";
  content: string;
  timestamp?: string;
  citations?: Array<{ chunkId: string; page?: number; score?: number }>;
  diffSuggestion?: DiffSuggestion;
  uiComponent?: UIComponent; // Keep for backward compatibility with mocks
  uiComponents?: UIComponent[];
  palResult?: PALResult;
}

export interface DiffSuggestion {
  filename: string;
  language: string;
  hunks: DiffHunk[];
}

export interface DiffHunk {
  oldStart: number;
  newStart: number;
  lines: DiffLine[];
}

export interface DiffLine {
  type: "add" | "remove" | "context";
  content: string;
}

export interface BoundingBox {
  x: number;
  y: number;
  w: number;
  h: number;
  page: number;
}

export interface Citation {
  chunk_id: string;
  page: number;
  score: number;
  section_header: string | null;
  text_snippet: string;
  bounding_box: BoundingBox | null;
}

export interface RetrievedChunk {
  id: string;
  text_snippet: string;
  page_number: number;
  section_header: string;
  bm25_score: number;
  vector_score: number;
  rrf_score: number;
  rerank_score: number | null;
  bounding_box: BoundingBox | null;
  is_table: boolean;
}

export interface PALResult {
  code: string;
  result: string;
  label: string;
}

export interface UIComponent {
  component: "BarChart" | "LineChart" | "DataTable" | "PDFOverlay" | "CodeBlock" | "ComparisonChart";
  data: BarChartData | DataTableData | PDFOverlayData | CodeBlockData | ComparisonChartData;
}

export interface ComparisonChartData {
  title: string;
  description?: string;
  data: { category: string; [key: string]: string | number }[];
  metrics: { key: string; color: string; name: string }[];
}

export interface BarChartData {
  title: string;
  unit: string;
  labels: string[];
  datasets: { label: string; values: number[] }[];
}

export interface DataTableData {
  caption: string;
  headers: string[];
  rows: (string | number)[][];
}

export interface PDFOverlayData {
  file_id: string;
  highlights: BoundingBox[];
}

export interface CodeBlockData {
  language: string;
  code: string;
  result: string;
  label: string;
}

export interface Message {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  retrieved_chunks: RetrievedChunk[];
  ui_component: UIComponent | null;
  pal_result: PALResult | null;
  timestamp: string;
  run_id: string | null;
  refusal?: { reason: string; message: string } | null;
}

// ──────────────────────────────────────────────
// SSE Event Shapes
// ──────────────────────────────────────────────

export interface SSEChunkEvent {
  type: "chunk";
  delta: string;
  citations: { chunk_id: string; page: number; score: number }[];
}

export interface SSERetrievalDebugEvent {
  type: "retrieval_debug";
  run_id: string;
  chunks: RetrievedChunk[];
  query_rewritten: string;
}

export interface SSEUIComponentEvent {
  type: "ui_component";
  component: string;
  data: Record<string, unknown>;
}

export interface SSEPALEvent {
  type: "pal_execution";
  code: string;
  result: string;
  label: string;
}

export interface SSERefusalEvent {
  type: "refusal";
  reason: string;
  message: string;
}

export interface SSEDoneEvent {
  type: "done";
  conversation_id: string;
  run_id: string;
  total_tokens: number;
  cached_tokens: number;
  latency_ms: number;
}

export type SSEEvent =
  | SSEChunkEvent
  | SSERetrievalDebugEvent
  | SSEUIComponentEvent
  | SSEPALEvent
  | SSERefusalEvent
  | SSEDoneEvent;

// ──────────────────────────────────────────────
// Chat Request
// ──────────────────────────────────────────────

export interface ChatRequest {
  project_id: string;
  conversation_id: string | null;
  message: string;
  language: string;
  voice: boolean;
  debug_mode: boolean;
}

// ──────────────────────────────────────────────
// Metrics
// ──────────────────────────────────────────────

export interface QueryMetric {
  latency_ms: number;
  total_tokens: number;
  cached_tokens: number;
  timestamp: number;
  wasRefusal: boolean;
}
