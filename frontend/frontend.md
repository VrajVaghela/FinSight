# FinSight AI — Member 5: Frontend, UI/UX & Evaluation Lead
## Detailed Step-by-Step Implementation Plan

---

# SECTION 1 — YOUR ROLE AND OWNERSHIP

You are the final integration surface of the entire system. Everything other members build
becomes visible only through what you build. The judges evaluate what they see and interact with —
which means your decisions directly determine the score.

**You own six distinct subsystems:**

1. The complete Next.js 16 frontend application — layout, routing, navigation
2. The SSE stream consumer — the engine that drives all real-time UI updates
3. The Generative UI router — which dynamically mounts BarChart, DataTable, PDFOverlay,
   CodeBlock, or PlainText based on the backend's JSON payload
4. The PDF viewer with bounding box highlighting — your "wow factor" feature
5. The Retrieval Debug Panel — surfaces raw retrieval internals for judges
6. The RAGAS evaluation script — the only quantitative proof that the system works

You are also the **integration contract owner**. You define the TypeScript schemas
and SSE event shapes that all other members must honour. Establish these schemas
with the full team on Day 1 before anyone writes a single line of backend code.

---

# SECTION 2 — SYSTEM ARCHITECTURE (YOUR LAYER)

## 2.1 Where You Sit in the Full Stack

```
┌────────────────────────────────────────────────────────────────────────┐
│                        MEMBER 5 DOMAIN                                 │
│                                                                        │
│   Browser (Next.js 16 / React)                                         │
│                                                                        │
│   ┌──────────────┐   ┌──────────────────────┐   ┌──────────────────┐  │
│   │   Project    │   │   Chat Interface     │   │  Debug Panel     │  │
│   │   Sidebar    │   │   (SSE consumer)     │   │  (Collapsible)   │  │
│   │   & Nav      │   │   Voice Controls     │   │  Chunk scores    │  │
│   └──────┬───────┘   └──────────┬───────────┘   └────────┬─────────┘  │
│          │                      │                         │            │
│   ┌──────▼──────────────────────▼─────────────────────────▼────────┐  │
│   │                 Generative UI Router                            │  │
│   │   Reads component field in JSON → mounts correct widget        │  │
│   │   BarChart | DataTable | PDFOverlay | CodeBlock | PlainText     │  │
│   └──────────────────────────┬──────────────────────────────────────┘  │
│                              │                                          │
│   ┌──────────────────────────▼──────────────────────────────────────┐  │
│   │         PDF Viewer + Bounding Box Highlight Canvas              │  │
│   │         react-pdf renders pages / canvas layer draws boxes      │  │
│   └─────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│   ┌─────────────────────────────────────────────────────────────────┐  │
│   │   Monitoring Dashboard (RAGAS scores, latency, refusal rate)    │  │
│   └─────────────────────────────────────────────────────────────────┘  │
└────────────────────────────┬───────────────────────────────────────────┘
                             │ HTTP REST + SSE Stream + WebSocket
┌────────────────────────────▼───────────────────────────────────────────┐
│                      FastAPI Backend (Members 1-4)                     │
│                                                                        │
│  /api/projects         → Member 3 (Backend)                           │
│  /api/projects/{id}/files → Member 2 (Ingestion)                      │
│  /api/projects/{id}/status → Member 2 (Ingestion)                     │
│  /api/chat             → Members 1+3+4 (Retrieval + Generation)       │
│  /api/retrieval/debug  → Member 1 (Retrieval visibility)              │
│  /api/files/{id}/download → Member 3 (File serving)                   │
│  /ws/voice             → Member 3 (WebSocket voice)                   │
└────────────────────────────────────────────────────────────────────────┘
```

## 2.2 Internal Frontend Architecture

Your frontend has three distinct layers inside it:

**Layer 1 — Networking Layer**
All API calls, SSE stream parsing, and WebSocket management live here. This layer is
completely separated from the UI. It exposes typed data to the UI through custom React hooks.
No component ever calls fetch() directly.

**Layer 2 — State and Logic Layer**
Custom hooks own all application state: current project, current conversation, streaming
message state, voice state, language detection result, debug chunks, and metrics. Components
read state from hooks and call hook functions. Hooks never contain JSX.

**Layer 3 — Presentation Layer**
React components that only render. They receive data as props and call callbacks.
The Generative UI router lives here — it reads the component type from props
and mounts the correct widget. No API calls, no state management in this layer.

---

# SECTION 3 — DATA FLOWS

## 3.1 Ingestion Flow (Your Perspective)

This is what happens on your side when a user uploads a PDF.

```
User drops PDF onto FileUploadZone
         │
         ▼
Your frontend sends multipart/form-data POST to /api/projects/{id}/files
         │
         ▼
Backend returns { file_id: string, status: "pending" }
         │
         ▼
Your useIngestionStatus hook begins polling /api/projects/{id}/status
every 2 seconds
         │
         ├──► status = "pending"    → show grey spinner "Queued..."
         ├──► status = "processing" → show blue pulse "Parsing with Docling..."
         ├──► status = "ready"      → show green check "X pages indexed, ready"
         └──► status = "failed"     → show red X "Ingestion failed"
                   │
                   ▼ (on "ready")
         Store file_id in project state → enables PDF viewer
         Stop polling interval
```

**What you need from Member 2:** The status endpoint must return `page_count` when
status is "ready". This tells your UI how many pages to offer in the PDF navigator.

## 3.2 Query Flow — SSE Stream (Your Most Critical Flow)

This is the heartbeat of your entire UI. Every feature branches off this flow.

```
User types message and presses Send (or speaks via voice)
         │
         ▼
Language detection runs on the input text (client-side heuristic)
         │
         ▼
Your ChatContainer assembles a ChatRequest payload:
  { project_id, conversation_id, message, language, voice, debug_mode }
         │
         ▼
POST /api/chat — response opens as a streaming SSE connection
         │
         ▼
Your useSSEStream hook begins reading the stream line by line.
Each line starting with "data: " is parsed as a JSON event.
The event's "type" field routes it to the correct handler:
         │
         ├──► type = "retrieval_debug"
         │         → Store top-k chunks in debugChunks state
         │         → Store query_rewritten in debug state
         │         → Debug Panel updates immediately
         │
         ├──► type = "chunk"
         │         → Append delta string to streamingText
         │         → Merge any new citations into citationMap
         │         → MessageBubble re-renders with updated text
         │
         ├──► type = "pal_execution"
         │         → Store PAL result (code + result + label)
         │         → CodeBlockWidget will render when message finalises
         │
         ├──► type = "ui_component"
         │         → Store { component, data } in uiComponent state
         │         → GenUIRouter will mount the correct widget
         │
         ├──► type = "refusal"
         │         → Set refusal state with reason and level
         │         → Render amber refusal banner instead of streaming text
         │         → Debug Panel shows which gate level fired
         │
         └──► type = "done"
                   → Finalize conversation_id (may be new if first message)
                   → Store run_id (links to /api/retrieval/debug if needed)
                   → Record metrics (latency_ms, tokens) to MetricsStore
                   → Set isStreaming = false
                   → Commit completed message to conversation history
```

## 3.3 Citation Click Flow

This flow links the text response back to the physical PDF page.

```
User clicks a [p7] citation badge in the message
         │
         ▼
CitationBadge onClick fires with the full Citation object
  (contains: chunk_id, page, bounding_box {x, y, w, h}, score)
         │
         ▼
ChatContainer receives the citation and updates two pieces of state:
  1. currentPage  → set to citation.page
  2. highlights   → set to [citation.bounding_box]
         │
         ▼
PDFViewer receives updated currentPage → renders that page
         │
         ▼
PDFHighlighter receives updated highlights array
         │
         ▼
Coordinate transformation runs:
  PDF coordinate origin is BOTTOM-LEFT (y increases upward)
  Canvas coordinate origin is TOP-LEFT (y increases downward)
  Transform: canvas_y = pageHeight - (pdf_y + pdf_h)
  Scale: multiply by (rendered_pixel_width / 595) and (rendered_pixel_height / 842)
         │
         ▼
Yellow semi-transparent rectangle drawn over exact source paragraph or table cell
```

**Critical dependency on Member 2:** Every chunk in Qdrant MUST have bounding_box
stored as {x, y, w, h} in PDF points. Without this data, the highlight feature
cannot work. Verify this schema with Member 2 before they write ingestion code.

## 3.4 Voice Flow

```
User clicks microphone button
         │
         ▼
Check if Web Speech API is available in browser
         │
         ├──► Available (Chrome/Edge) → Use Web Speech API directly
         │         Browser handles STT locally
         │         Language hint passed from detected language state
         │         On final result → transcript placed into input field
         │         → same send flow as typed text
         │
         └──► Not available → Fallback to WebSocket + Whisper
                   Open WebSocket to /ws/voice
                   Request microphone permission
                   MediaRecorder captures audio in 40ms chunks
                   Each chunk sent as binary ArrayBuffer over WebSocket
                   Server runs Whisper STT
                   Server sends back { type: "transcript", text: "..." }
                   Transcript placed into input field → same send flow
                         │
                         ▼ (if voice mode is on, TTS is also enabled)
                   After SSE "done" event, send completed answer text to TTS
                   Receive audio stream → play through AudioPlayer component
                   If user speaks during playback → barge-in signal from server
                   Immediately stop audio playback, clear queue, begin new transcript
```

---

# SECTION 4 — CONTROL FLOW (USER JOURNEYS)

## 4.1 First-Time User Journey

```
Land on / → redirect to /projects
    → ProjectList page shows "No projects yet"
    → User clicks "New Project" button
    → Modal: enter project name, optional system prompt
    → POST /api/projects → ProjectRecord returned
    → Sidebar adds new project entry
    → Navigate to /projects/{id}
    → Project page shows file upload zone
    → User uploads Adani PDF
    → Ingestion status polling starts
    → When ready → "Start Chatting" button appears
    → Navigate to /projects/{id}/chat
    → New conversation begins
```

## 4.2 Returning User Journey

```
Land on /projects
    → Sidebar shows existing projects
    → Each project expands to show past conversations
    → User clicks a past conversation
    → Navigate to /projects/{id}/chat/{convId}
    → Load conversation history from GET /api/chat/history/{convId}
    → Render all past messages including citations and UI components
    → Input ready for new message
```

## 4.3 Debug Mode Toggle Flow

```
Header has a "Debug" toggle button
    → ON:  debug_mode = true sent in all ChatRequests
            "retrieval_debug" SSE events are emitted by backend
            Debug Panel slides open on the right
            Each new query updates the panel with fresh chunks + scores

    → OFF: debug_mode = false
            "retrieval_debug" events not emitted (saves bandwidth)
            Debug Panel collapses
```

---

# SECTION 5 — COMPONENT ARCHITECTURE

## 5.1 Page Structure

```
app/(dashboard)/layout.tsx
│
├── Sidebar.tsx
│     ├── ProjectList.tsx     (maps over projects from useProjects hook)
│     │     └── ProjectItem.tsx   (expandable, shows conversations)
│     │           └── ConversationItem.tsx
│     └── NewProjectButton.tsx
│
└── [page content area]
      │
      ├── /projects/page.tsx          → ProjectDashboard
      │
      └── /projects/[id]/chat/[convId]/page.tsx
            │
            └── ChatPage.tsx
                  ├── Header.tsx         (project name, status badge, debug toggle)
                  ├── PDFViewer.tsx      (left panel, collapsible)
                  │     ├── react-pdf Document + Page
                  │     ├── PDFHighlighter.tsx  (canvas overlay for bboxes)
                  │     └── PDFNavigation.tsx   (page controls)
                  ├── ChatContainer.tsx   (centre panel — orchestrates everything)
                  │     ├── MessageList.tsx
                  │     │     └── MessageBubble.tsx (x N messages)
                  │     │           ├── CitationBadge.tsx  (x N citations)
                  │     │           └── GenUIRouter.tsx    (if ui_component present)
                  │     │                 ├── BarChartWidget.tsx
                  │     │                 ├── DataTableWidget.tsx
                  │     │                 ├── PDFOverlayWidget.tsx
                  │     │                 └── CodeBlockWidget.tsx
                  │     ├── TypingIndicator.tsx
                  │     └── InputBar.tsx
                  │           ├── TextInput
                  │           ├── VoiceController.tsx
                  │           │     └── WaveformIndicator.tsx
                  │           └── SendButton
                  └── DebugPanel.tsx     (right panel, collapsible)
                        ├── QueryRewriteDisplay.tsx
                        └── ChunkCard.tsx  (x top-k)
                              └── ScoreBar.tsx (BM25, Vector, RRF, Rerank)
```

## 5.2 Key Component Responsibilities

**ChatContainer** is your most important component. It owns:
- Calling useSSEStream to send messages and receive events
- Maintaining the local conversation message list
- Propagating citation click events to the PDF viewer
- Passing debug chunks to the Debug Panel
- Deciding which UI component to pass to GenUIRouter

**GenUIRouter** has a single job: read the `component` field from the UIComponent
object and mount the correct widget. It uses dynamic imports to avoid loading
charting libraries on initial page load. This is a pure routing component with
no logic of its own.

**PDFHighlighter** sits as an absolutely positioned overlay div on top of the react-pdf
Page component. It converts bounding box coordinates from PDF point space to pixel
space, then renders semi-transparent yellow rectangles. It re-renders every time
the highlights array changes.

**DebugPanel** is collapsible. It shows three sections: the rewritten query (from
QueryRewriter — Member 3), the top-k chunks each with their score breakdown, and
the refusal gate status. Each ChunkCard has an expandable full-text view.

---

# SECTION 6 — DATA SCHEMAS (Shapes, No Code)

These are the agreed contracts between your frontend and the backend.
Share this document with all team members on Day 1.

## 6.1 Core Entity Shapes

**ProjectRecord** — returned by GET /api/projects and POST /api/projects
```
id              : UUID string
name            : string
system_prompt   : string or null
owner_id        : string
created_at      : ISO 8601 timestamp string
file_ids        : array of UUID strings
status          : one of "pending" | "processing" | "ready" | "failed"
```

**Message** — the unit of conversation history
```
id              : UUID string
conversation_id : UUID string
role            : "user" or "assistant"
content         : string (assistant text contains [chunk_id] markers)
citations       : array of Citation objects
retrieved_chunks: array of RetrievedChunk objects
ui_component    : UIComponent object or null
pal_result      : PALResult object or null
timestamp       : ISO 8601 timestamp string
run_id          : UUID string linking to /api/retrieval/debug (nullable)
```

**Citation** — an individual source reference
```
chunk_id        : string (UUID of the chunk in Qdrant)
page            : integer (1-indexed page number)
score           : float (final score used to rank this citation)
section_header  : string or null (e.g. "EBITDA Analysis")
text_snippet    : string (first 200 chars of chunk, for tooltip)
bounding_box    : BoundingBox object or null
```

**BoundingBox** — physical location of text in the PDF
```
x               : float (left edge in PDF points, origin = bottom-left)
y               : float (bottom edge in PDF points)
w               : float (width in PDF points)
h               : float (height in PDF points)
page            : integer (which page this box is on)
```
NOTE: PDF points are relative to 595 × 842 pt page (A4). Confirm this scale
factor with Member 2. If the document uses a different page size (e.g. US Letter
or widescreen slide format), the coordinate transform must account for it.

**RetrievedChunk** — a chunk as returned in the debug view
```
id              : string
text_snippet    : string (full chunk text for debug panel)
page_number     : integer
section_header  : string
bm25_score      : float (0.0 to 1.0 normalised)
vector_score    : float (0.0 to 1.0 cosine similarity)
rrf_score       : float (Reciprocal Rank Fusion merged score)
rerank_score    : float or null (cross-encoder score if reranker ran)
bounding_box    : BoundingBox or null
is_table        : boolean
```

## 6.2 SSE Event Shapes

Every event on the stream has a "type" field. Your SSE parser reads this field
and routes to the correct handler. There are exactly 6 event types:

**chunk** — a piece of the streaming answer
```
type       : "chunk"
delta      : string (new text to append to current answer)
citations  : array of { chunk_id, page, score } (partial, may be empty)
```

**retrieval_debug** — the raw retrieval results (only if debug_mode = true)
```
type             : "retrieval_debug"
run_id           : UUID string
chunks           : array of RetrievedChunk
query_rewritten  : string (the query after Member 3's QueryRewriter ran)
```

**ui_component** — instruction to mount a visual widget
```
type       : "ui_component"
component  : one of "BarChart" | "LineChart" | "DataTable" | "PDFOverlay" | "CodeBlock"
data       : object whose shape depends on component type (see below)
```

**pal_execution** — a numeric calculation was routed through PAL
```
type       : "pal_execution"
code       : string (the Python code that was generated and executed)
result     : string (the computed result, e.g. "2347.8")
label      : string (e.g. "Calculated: ₹2,347.8 Cr EBITDA")
```

**refusal** — no relevant evidence found; generation was blocked
```
type       : "refusal"
reason     : one of "level_1_threshold" | "level_2_reranker" | "level_3_grader" | "level_4_postgen"
message    : "Not found in the document." (hardcoded — never varies)
```

**done** — stream is complete
```
type             : "done"
conversation_id  : UUID string (use this to update your URL if it was a new conversation)
run_id           : UUID string (use with /api/retrieval/debug for post-hoc inspection)
total_tokens     : integer
cached_tokens    : integer (tokens served from Anthropic prompt cache)
latency_ms       : integer (total end-to-end time)
```

## 6.3 UIComponent Data Shapes (by component type)

**BarChart data shape:**
```
title      : string (e.g. "Revenue by Segment, H1-FY26")
unit       : string (e.g. "₹ Crore")
labels     : array of strings (x-axis categories)
datasets   : array of { label: string, values: array of numbers }
```

**DataTable data shape:**
```
caption    : string (table title)
headers    : array of strings (column names)
rows       : array of arrays (each inner array is one row of string or number values)
```

**PDFOverlay data shape:**
```
file_id    : UUID string (which file to open)
highlights : array of BoundingBox objects (boxes to highlight)
```

**CodeBlock data shape (PAL result):**
```
language   : "python"
code       : string (the generated Python)
result     : string (the computed output)
label      : string (human-readable badge, e.g. "Calculated: 23.4% CAGR")
```

## 6.4 ChatRequest Shape (what you send)

```
project_id       : UUID string (which project's vector index to query)
conversation_id  : UUID string or null (null = start new conversation)
message          : string (the user's query text)
language         : ISO 639-1 string (e.g. "en", "hi", "gu") — detected client-side
voice            : boolean (true = TTS response expected)
debug_mode       : boolean (true = retrieval_debug events will be emitted)
```

---

# SECTION 7 — API ENDPOINTS YOU CONSUME

All calls go through your Next.js rewrite proxy, which forwards to FastAPI.
This avoids CORS issues and lets you change the backend URL in one place.

```
GET    /api/health
       → Use on app load to verify backend is up
       → Show "Backend offline" banner if this fails
       → Response: { status: "ok", version: string }

POST   /api/projects
       → Create a new project workspace
       → Body: { name, system_prompt? }
       → Response: full ProjectRecord

GET    /api/projects
       → List all projects for the current user
       → Response: array of ProjectRecord

POST   /api/projects/{id}/files
       → Upload a PDF for ingestion
       → Body: multipart/form-data with "file" field
       → Response: { file_id, status: "pending" }

GET    /api/projects/{id}/status
       → Poll ingestion progress
       → Response: { status, page_count? }
       → Poll every 2 seconds, stop when status is "ready" or "failed"

POST   /api/chat
       → The main chat endpoint — opens SSE stream
       → Body: ChatRequest (see 6.4 above)
       → Response: SSE stream (text/event-stream)
       → Important: do NOT use EventSource API — use fetch() with ReadableStream
         because you need to send a POST body, which EventSource cannot do

GET    /api/chat/history/{conversation_id}
       → Load full conversation history on returning to a conversation
       → Response: ConversationHistory with all Messages

GET    /api/retrieval/debug?run_id={uuid}
       → Fetch detailed debug info for a past query
       → Response: RetrievalDebugPayload with all chunks and scores
       → Use this when user wants to inspect a previous answer

GET    /api/files/{file_id}/download
       → Serve the PDF binary to your react-pdf viewer
       → Response: application/pdf binary
       → Important: Do NOT try to load the PDF from Qdrant directly.
         Always proxy through this endpoint.

WS     /ws/voice
       → WebSocket for real-time voice (fallback from Web Speech API)
       → Send: binary audio chunks (ArrayBuffer, 40ms intervals)
       → Receive: JSON messages of types "transcript", "rag_response", "interrupted"
```

---

# SECTION 8 — INTEGRATION AGREEMENTS WITH OTHER MEMBERS

Lock these down on Day 1 before anyone writes implementation code.

## With Member 1 (Lead RAG Architect — Retrieval)

You need from them:
- The `run_id` field present in every SSE "done" event
- The `rrf_score`, `bm25_score`, `vector_score` all normalised to 0.0–1.0 range
- The `rerank_score` field populated when reranker ran, null when it was skipped
- The "refusal" event's `reason` field using exactly these string values:
  `level_1_threshold`, `level_2_reranker`, `level_3_grader`, `level_4_postgen`
- Confirmed: does the debug endpoint work without debug_mode? (for post-hoc inspection)

You give to them:
- Confirmation of how the debug panel displays scores (so they format the numbers correctly)
- The `run_id` linking scheme so they know you'll use it in the debug endpoint

## With Member 2 (Data Engineer — Ingestion)

This is your most critical integration. Get this right first.

You need from them:
- Every chunk in Qdrant MUST have `bounding_box: { x, y, w, h }` in the payload
- The coordinate system: confirm it is PDF points (595 × 842 base) not pixels
- Confirm A4 vs. US Letter vs. slide format for the Adani PDF (affects your scale factors)
- The `section_header` field populated with the nearest heading above each chunk
- The `is_table` boolean and `table_html` field for table chunks
- The `page_number` is 1-indexed (not 0-indexed)

You give to them:
- The exact BoundingBox schema shape (x, y, w, h, page) so they store it correctly
- Confirmation that `page_number` must be 1-indexed for react-pdf compatibility

## With Member 3 (Backend Engineer — Infrastructure)

You need from them:
- CORS headers on FastAPI allowing `http://localhost:3000`
- SSE events formatted as `data: {json}\n\n` (double newline between events)
- The `query_rewritten` field in the "retrieval_debug" event
- The `/api/files/{id}/download` endpoint with correct `Content-Type: application/pdf` header
- WebSocket at `/ws/voice` supporting binary audio chunks and returning JSON messages
- The "done" event includes both `conversation_id` and `run_id`
- Anthropic prompt cache hit/miss reflected in `cached_tokens` field of "done" event

You give to them:
- The complete ChatRequest shape so they build the endpoint to exactly that schema
- The SSE event type list so they implement all 6 events
- Confirmation of which port the frontend runs on for CORS setup

## With Member 4 (Reasoning & Citations)

You need from them:
- Citation markers injected into generated text using format `[chunk_id]`
  where chunk_id is a UUID string — agree this exact regex pattern: `\[[\w-]+\]`
- The "pal_execution" SSE event fired BEFORE the "chunk" events for numeric queries
- The `bounding_box` field populated in every Citation object returned in "chunk" events
- Confirm: does every sentence get a citation marker, or only when a fact is cited?

You give to them:
- The CitationBadge rendering logic so they know how the [chunk_id] markers will appear
- Confirmation that your parser uses the `\[[\w-]+\]` pattern so they don't change the format

---

# SECTION 9 — CHECKPOINT-BY-CHECKPOINT PLAN

Each checkpoint has: what you build, what you validate, and what you need from others.

---

## CHECKPOINT 0 — Project Setup (Hours 0 to 2)

**What you build:**
Set up the Next.js 16 application with Turbopack enabled in next.config.ts.
Configure the rewrite proxy so all /api/* requests forward to the FastAPI backend URL
from environment variables. Set up Tailwind CSS with a dark-first custom colour palette.
Install core dependencies: recharts for charts, react-pdf for the PDF viewer,
lucide-react for icons, clsx and tailwind-merge for conditional styling.
Create the complete directory structure — all folders and empty files — before
writing any real logic. This prevents merge conflicts with other members.

**What you validate:**
The dev server starts on port 3000 with Turbopack. The /api/health rewrite works
and returns the backend health response. No type errors on an empty TypeScript project.

**Integration actions:**
Confirm the backend port (default 8000) with Member 3.
Share the directory structure with the team so no one creates conflicting files.

---

## CHECKPOINT 1 — Layout Shell and Project Sidebar (Hours 2 to 6)

**What you build:**
The root dashboard layout — a two-column flex container. Left column (280px fixed)
is the sidebar. Right column (flex-1) is the main content area. The sidebar shows
the list of projects, each expandable to show conversations. A "New Project" button
opens a modal with a name field and optional system prompt field.
The useProjects hook handles all project CRUD: fetch list on mount, create project
via POST, update local state optimistically. Routing uses Next.js App Router.
Navigating to /projects/{id} and /projects/{id}/chat/{convId} must both work.
Add a health check banner in the layout that shows "Backend offline" if GET /api/health fails.

**What you validate:**
Can create a project (even if backend is mocked). Sidebar shows it. Clicking it
navigates correctly. Conversation tree expands. Mobile layout is acceptable.

**Integration actions:**
The GET /api/projects endpoint must be live from Member 3 by end of this checkpoint.
If it isn't ready, mock with hardcoded data and add a TODO comment.

---

## CHECKPOINT 2 — File Upload and Ingestion Progress (Hours 6 to 10)

**What you build:**
The FileUploadZone component — a drag-and-drop area that also accepts file picker.
Validates that only PDF files are accepted (check MIME type and extension).
Shows a file preview with name and size before uploading.
On upload, sends multipart/form-data POST to /api/projects/{id}/files.
The useIngestionStatus hook polls /api/projects/{id}/status every 2 seconds.
Four distinct visual states: queued (grey spinner), processing (blue animated pulse
with "Parsing with Docling..." text), ready (green check with page count), failed
(red X with "Contact support" message). Stop polling when status reaches ready or failed.
When ready, store the file_id in project state and show a "Start Chatting" button.

**What you validate:**
Upload the Adani PDF. Status progresses through all states.
When ready, page_count is displayed correctly (e.g. "42 pages indexed").

**Integration actions:**
Member 2 must confirm the status endpoint returns `page_count` on "ready".
Member 3 must confirm the file upload endpoint is multipart (not base64 JSON).

---

## CHECKPOINT 3 — Core SSE Stream Hook (Hours 10 to 16)

**This is the most important checkpoint. Do not move forward until this is solid.**

**What you build:**
The useSSEStream hook. This hook opens a streaming fetch POST to /api/chat
and reads the response body as a ReadableStream. It processes the stream
line by line, accumulating a buffer for partial lines. For each complete line
starting with "data: ", it strips the prefix, parses the JSON, and routes
the event to the correct state updater based on the `type` field.

State managed by this hook:
- `streamingText` — the answer being built character by character
- `citations` — deduplicated citation list, added from chunk events
- `debugChunks` — array of retrieved chunks from retrieval_debug event
- `queryRewritten` — the rewritten query from retrieval_debug event
- `uiComponent` — the UIComponent object from ui_component event
- `palResult` — the PAL code and result from pal_execution event
- `refusal` — the refusal event object if a gate fired
- `runId` — the run_id from done event (for debug link)
- `doneMetrics` — latency, tokens from done event
- `isStreaming` — boolean, true while stream is open

The hook also handles errors: network failures, JSON parse errors (log and skip),
stream interruption. It resets all state at the start of each new sendMessage call.
The citation deduplication logic must check chunk_id uniqueness before appending.

**Why fetch() not EventSource:** EventSource cannot send POST bodies. You must use
fetch() with response.body.getReader() to read the stream incrementally.

**What you validate:**
Send a real question against the backend (with the Adani PDF ingested).
Verify that streamingText updates incrementally (not all at once).
Verify that citations accumulate correctly.
Verify that "done" fires last and isStreaming becomes false.
Open the browser network tab — confirm the request stays open and bytes
arrive over time (not one big payload).

**Integration actions:**
Member 3's SSE format must use `data: {json}\n\n` (standard SSE).
If events arrive without the double newline, your buffer logic breaks.
Test this together before moving on.

---

## CHECKPOINT 4 — Message Rendering and Citation System (Hours 16 to 20)

**What you build:**
The MessageList and MessageBubble components. MessageBubble renders differently
based on message role and content. For user messages: dark background, right-aligned.
For assistant messages: the content string contains `[chunk_id]` markers injected
by Member 4's CitationQueryEngine. Your renderer splits the content on these
markers using a regex, maps each chunk_id to its full Citation object (using the
citationMap from the stream), and replaces each marker with a clickable CitationBadge.

CitationBadge shows the page number (e.g. "p7"), has a tooltip with the score,
and fires the onCitationClick callback with the full Citation object when clicked.

For refusal messages: render an amber-bordered panel with the exact text
"Not found in the document." — do NOT render this as normal text. This visual
distinction signals to judges that refusal logic is working.

For messages with a PAL result: render the CodeBlockWidget below the text.
For messages with a UI component: render the GenUIRouter output below the text.

The TypingIndicator shows "FinSight is thinking..." with an animated ellipsis
while isStreaming is true but no text has arrived yet (waiting for first chunk).

**What you validate:**
All 5 acceptance test questions rendered correctly.
The refusal question (CEO email) shows the amber panel — not a grey bubble.
Citations appear as badges inline within the text — not in a separate section.
Clicking a badge triggers the citation click callback (PDF integration in CP6).

**Integration actions:**
Confirm with Member 4 the exact citation marker format: `[chunk_id]` where
chunk_id is a UUID. Ask them to test with at least one query that produces
multiple citations so you can verify deduplication.

---

## CHECKPOINT 5 — Generative UI Router and Widgets (Hours 20 to 26)

**What you build:**
The GenUIRouter component and all four widget types.

BarChartWidget: wraps Recharts BarChart in a dark-styled container. Uses the
`datasets` array to render one Bar per dataset. X-axis from `labels` array.
Shows the `title` above the chart and `unit` below. Colours cycle through
a predefined palette (blue, green, amber, red).

DataTableWidget: a sortable HTML table. Click column headers to sort ascending/descending.
Row striping for readability. Caption above the table. Scroll horizontally on overflow.

PDFOverlayWidget: receives file_id and highlights array. Triggers the PDF viewer
to navigate to the first highlighted page and apply the boxes. This widget is
essentially a side-effect trigger — it may render a "Source highlighted in PDF viewer"
message rather than displaying content itself.

CodeBlockWidget: shows the PAL result. A header bar with "⚡ Calculated: [label]" badge.
An expandable section with the Python code and its output. The expand/collapse
state is local to the component.

GenUIRouter uses Next.js dynamic() imports with ssr: false for all chart components.
This prevents the "window is not defined" error during server-side rendering and
reduces the initial JavaScript bundle size.

**What you validate:**
Ask a revenue question → BarChart renders with correct axis labels and values.
Ask a segment comparison question → DataTable renders with sortable columns.
Ask a numeric question → CodeBlock renders with expandable Python.
Verify all charts are readable in dark mode.

**Integration actions:**
Ask Member 4 to confirm the UIComponent data shapes before they write generation
prompts. The `labels` and `datasets` structure for BarChart must match exactly.
Share the widget component list so the backend knows which component names are valid.

---

## CHECKPOINT 6 — PDF Viewer and Bounding Box Overlay (Hours 26 to 32)

**This is your visual "wow factor" feature. It will be the most memorable moment in the demo.**

**What you build:**
The PDFViewer component wraps react-pdf's Document and Page components.
It loads the PDF from /api/files/{file_id}/download via the proxy (never directly).
The PDFNavigation component shows current page / total pages, previous/next buttons,
and a direct page number input.

The PDFHighlighter component is an absolutely-positioned div placed directly
over the react-pdf Page component. It has pointer-events: none so it doesn't
interfere with text selection. For each BoundingBox in the highlights array, it
computes the pixel-space rectangle using the coordinate transformation described
in Section 3.3 above and renders a yellow semi-transparent div.

The critical transformation: PDF coordinate origin is bottom-left, y increases upward.
Canvas coordinate origin is top-left, y increases downward. The transform is:
  canvas_y = pageHeight_pixels - (pdf_y + pdf_h) * scaleY
  canvas_x = pdf_x * scaleX
  canvas_w = pdf_w * scaleX
  canvas_h = pdf_h * scaleY

Scale factors depend on the rendered width passed to react-pdf's Page component.
For A4 (595 pt wide), if rendered at 700px width: scaleX = 700 / 595 ≈ 1.176.

The highlight box uses an animated pulse border (CSS animation) to draw attention.
A "Jump to page" button in the citation badge scroll the PDF to that page.

Split-pane layout: the ChatContainer and PDFViewer live side-by-side in a resizable
split pane. A drag handle between them lets users adjust the ratio. Default is 55%
chat / 45% PDF. On screens narrower than 1200px, collapse the PDF into a tab.

**What you validate:**
Upload the Adani PDF. Navigate to page 7. Ask a question that retrieves a chunk
from page 7. Click the [p7] citation badge. Verify PDF scrolls to page 7 and
a yellow box appears over the correct paragraph or table cell.
Test with a table chunk — the box should cover the whole table, not just one row.

**Integration actions:**
Member 2 must confirm bounding boxes are stored and returned in Qdrant payload.
Before this checkpoint, run a test query via the debug endpoint and manually check
that `bounding_box` is non-null in the RetrievedChunk objects.
If bounding boxes are missing, this feature cannot be demo'd — escalate immediately.

---

## CHECKPOINT 7 — Retrieval Debug Panel (Hours 32 to 36)

**What you build:**
The DebugPanel component, toggled by a button in the Header.
When open, it slides in from the right (280px wide, full height).
Three sections:

Section 1 — Query Rewrite: Shows the original user query, then an arrow, then the
rewritten standalone query. This demonstrates Member 3's QueryRewriter to judges.

Section 2 — Retrieved Chunks: A scrollable list of ChunkCard components. Each card shows:
  - Rank number (#1, #2, etc.)
  - Page number (p3)
  - TABLE badge if is_table is true
  - First 200 characters of text snippet (expandable to full text)
  - Four ScoreBars: BM25, Vector, RRF, and Rerank (if available)

Section 3 — Refusal Gate Status: If a refusal event fired, shows which gate level
triggered and what the threshold was. If no refusal, shows "All gates passed."

ScoreBar renders a labelled horizontal progress bar. The bar fill percentage is
the score value multiplied by 100. Colour coding: BM25 = orange, Vector = blue,
RRF = green, Rerank = purple. The numeric value is shown to 3 decimal places.

**What you validate:**
Ask any question. Toggle Debug Panel open. Confirm chunks appear with all four scores.
Ask the CEO email question. Confirm the refusal gate shows "Level 1: score threshold" with the actual threshold value.
Ask a follow-up question. Confirm the query rewrite section shows the original and rewritten queries are different.

**Integration actions:**
The retrieval_debug event must only fire when debug_mode is true in the ChatRequest.
Confirm this behaviour with Member 1 — sending debug_mode: false should not emit
retrieval_debug events (saves bandwidth in production).

---

## CHECKPOINT 8 — Voice Interface (Hours 36 to 42)

**What you build:**
The VoiceController component and useVoice hook.

The mic button in InputBar has three states:
- Idle: microphone icon, blue ring
- Listening: animated waveform (WaveformIndicator), red ring, pulsing
- Processing: spinner, grey ring

The WaveformIndicator is a row of 12 thin vertical bars that animate with staggered
sine-wave heights using CSS keyframes. No JavaScript animation — pure CSS.

Voice strategy: try Web Speech API first (available in Chrome/Edge). Pass the
detected language code as a hint. On final result, place transcript in the input
field and auto-submit. On error or if API is unavailable, fall back to WebSocket.

WebSocket fallback: connect to /ws/voice. Request microphone permission.
Use MediaRecorder with audio/webm MIME type and 40ms timeslice. Send each
ondataavailable chunk as a binary ArrayBuffer over the WebSocket. On receiving
{ type: "transcript", text } from server, place text in input and submit.

Barge-in handling: if a TTS audio response is playing and the user clicks the mic,
immediately stop the AudioPlayer and clear the audio queue. If the server sends
{ type: "interrupted" }, do the same.

TTS playback: after a query completes (SSE "done" event), if voice mode is enabled,
send the final answer text to the TTS endpoint and play the returned audio stream.
AudioPlayer component handles this with a simple HTML audio element.

**What you validate:**
Click mic in Chrome → speak "What are the major business segments?" → transcript
appears in input → query fires → answer streams → TTS speaks the answer.
Test fallback: disable Web Speech API (Firefox) → mic still works via WebSocket.

**Integration actions:**
Member 3 must confirm the WebSocket URL is /ws/voice and the message format
for transcripts is { type: "transcript", text: "..." }.

---

## CHECKPOINT 9 — Multilingual Support (Hours 42 to 46)

**What you build:**
The useLanguageDetect hook using script/character range detection.
The logic checks the input text for Unicode ranges:
Devanagari (U+0900–U+097F) → "hi" (Hindi)
Gujarati (U+0A80–U+0AFF) → "gu"
Arabic (U+0600–U+06FF) → "ar"
Chinese CJK (U+4E00–U+9FFF) → "zh"
Hiragana (U+3040–U+309F) → "ja"
Default → "en" (English)

This detected language code is sent in the ChatRequest's `language` field.
The backend uses it as a hint for Whisper STT and instructs the LLM to respond
in the same language.

A small language indicator badge appears in the input bar: [EN], [HI], [GU], etc.
It updates in real time as the user types. Clicking it opens a manual override picker.

The supported language list you display in settings: English, Hindi, Gujarati,
Tamil, Bengali, Arabic, Spanish, French, German, Chinese, Japanese.

**What you validate:**
Type a Hindi sentence → badge shows [HI] → send → response comes back in Hindi.
Type an English sentence → badge shows [EN] → response in English.

**Integration actions:**
Member 3 passes the language field to Whisper and to the generation prompt.
The LLM system prompt must include "Respond in the same language as the user's query."
Confirm this is implemented before testing multilingual.

---

## CHECKPOINT 10 — Monitoring Dashboard (Hours 46 to 50)

**What you build:**
The MonitoringDashboard page at /projects/{id}/monitoring (accessible from Header).
A MetricsStore singleton (module-level, in-memory) accumulates data from every
SSE "done" event. No backend needed for the MVP — all metrics are client-side.

MetricCards show:
- Average query latency (ms) with a trend arrow
- Total queries in this session
- Refusal rate (refusals / total queries as percentage)
- Cache hit rate (cached_tokens / total_tokens as percentage)
- Total tokens consumed (useful for cost estimation)

The RAGTriadChart uses Recharts RadarChart to show three axes:
Faithfulness, Contextual Precision, Answer Relevancy. These are populated
from the RAGAS evaluation script results (hardcoded after you run evaluation,
or loaded from a JSON file the script produces).

A recent queries timeline (LineChart) shows latency over the last 50 queries.
Spikes indicate slow queries — useful for debugging.

**What you validate:**
Run 10 queries. Dashboard shows correct averages. Refusal rate updates after the CEO
email question. Cache hit rate increases on repeated questions (once prompt caching is live).

---

## CHECKPOINT 11 — RAGAS Evaluation Script (Hours 50 to 56)

**What you build:**
A Python script at apps/api/scripts/evaluate.py.
This is a standalone script that you run once against a live FinSight AI instance.

The script contains a Golden Dataset of 50+ question-answer pairs derived from
the Adani Q2-FY26 PDF. You must construct this dataset manually by reading the
actual PDF and writing down ground truth answers. This is a prerequisite — do
it during earlier checkpoints in spare time.

Dataset categories:
- 10 grounded fact questions (segments, entities, descriptions)
- 10 numeric questions (exact values with correct units and page citations)
- 10 cross-section reasoning questions (EBITDA drivers, multi-page synthesis)
- 5 negative control questions (must all return "Not found in the document.")
- 10 conversational follow-up pairs (evaluated as question chains)
- 5 table-specific questions (data that only exists in table form)

The script sends each question to /api/chat via streaming fetch, collects:
- The final answer text
- The retrieved context chunks (from retrieval_debug events)
- The conversation_id (for follow-up pairs)

After all questions are answered, it constructs a HuggingFace Dataset object
and runs three RAGAS metrics:
1. Faithfulness: does the answer only use information from retrieved context?
2. Answer Relevancy: is the answer relevant to the question asked?
3. Contextual Precision: are the retrieved chunks actually useful for the answer?

Hard checks run separately (not through RAGAS):
- All 5 negative control questions must return exactly "Not found in the document."
- String equality check — any variation fails the test.

Output: a JSON report file with per-question scores and aggregate metrics.
Target thresholds: Faithfulness > 0.85, Answer Relevancy > 0.80, Contextual Precision > 0.75.

**Building the Golden Dataset (start this at Checkpoint 2):**
Download the Adani Q2-FY26 PDF. Read it carefully. For each category above,
write questions that a financial analyst would ask, along with the ground truth answer
copied verbatim from the document. For numeric questions, include the unit, the period,
and the page number. For negative controls, ask for information that genuinely does
not exist in the document (email, phone, personal information, future guidance not stated).

**What you validate:**
Run the script end-to-end. All 5 negative controls pass. RAGAS scores meet thresholds.
If faithfulness < 0.85, report to Member 1 (chunking or retrieval issue).
If contextual precision < 0.75, the reranker threshold may need tuning.

---

## CHECKPOINT 12 — Demo Preparation (Hours 56 to 60)

**What you build:**
The 3-minute demo walkthrough. Rehearse this at least twice before the deadline.
The acceptance test script that runs all 5 tests sequentially.

**Demo script (time-coded):**

00:00 – 00:30: Upload PDF
Show the drag-and-drop upload. Watch the status badge: Queued → Processing → Ready.
Say: "FinSight AI just ran Docling's TableFormer over 42 pages, preserving every
table structure. One command, one minute."

00:30 – 01:00: Grounded Fact + Citation Highlight
Ask Test 1 (business segments). Answer streams. Citations appear as [p3] [p4] badges.
Click the [p3] badge. PDF viewer scrolls to page 3. Yellow highlight appears
over the exact paragraph. Say: "Every answer is traceable. Click any citation —
see the exact source highlighted in the document."

01:00 – 01:30: Numeric Precision (PAL)
Ask Test 2 (consolidated total income). CodeBlock widget appears with "⚡ Calculated" badge.
Expand it to show the Python code. Say: "We never trust the LLM with arithmetic.
PAL generates and executes verified Python. This number is guaranteed correct."

01:30 – 01:50: Negative Control (Refusal)
Ask Test 4 (CEO email). Amber panel appears: "Not found in the document."
Say: "Four-level refusal gating. If the evidence isn't in the document, we refuse.
We never fabricate. The answer is always honest." 

01:50 – 02:20: Conversational Follow-up + Debug Panel
Ask Test 5 part 1 (airport performance). Then part 2 (passenger and cargo).
Open Debug Panel. Show query_rewritten is different from part 2 raw text.
Say: "Query rewriting converts follow-ups into standalone queries. The retrieval
pipeline never sees the conversation — it only sees the reformulated question."

02:20 – 02:45: Score Breakdown
Point to the ScoreBars in the Debug Panel.
Say: "Full transparency. BM25 for exact keyword matching, dense vectors for
semantic meaning, RRF for fusion, cross-encoder reranking for precision.
Every number is exposed."

02:45 – 03:00: RAGAS Score
Show the Monitoring Dashboard with RAGAS Faithfulness: 0.91.
Say: "RAGAS-evaluated on a 50-question golden dataset.
FinSight AI — the only financial AI you can audit."

---

# SECTION 10 — COMMON FAILURES AND HOW TO PREVENT THEM

**SSE stream stops mid-response**
Cause: server closes connection too early or network proxy has a timeout.
Prevention: add a 15-second keep-alive ping event (type "ping") from the backend.
Your client ignores unknown event types, so this is safe.

**PDF bounding boxes render in wrong position**
Cause: Y-axis is inverted between PDF and canvas space.
Prevention: test the coordinate transform on page 1 with a known chunk.
Before the demo, visually verify at least one highlight is in the right place.

**Citation markers [chunk_id] not found in citationMap**
Cause: Member 4 uses a different marker format than what you parse.
Prevention: agree the exact regex on Day 1. Test with a mocked SSE stream
containing a [chunk_id] marker before the real backend is ready.

**react-pdf CORS error when loading PDF**
Cause: trying to load PDF directly from Qdrant or an S3-style URL.
Prevention: always proxy through /api/files/{id}/download. Never use external URLs.

**GenUIRouter flickers or fails silently**
Cause: chart libraries are not dynamically imported, causing SSR issues.
Prevention: all chart components must use Next.js dynamic() with ssr: false.

**Voice WebSocket disconnects unexpectedly**
Cause: WebSocket idle timeout (common at 30–60 seconds on proxies).
Prevention: send a binary ping every 20 seconds. Implement auto-reconnect with
exponential backoff (1s, 2s, 4s, max 30s).

**RAGAS faithfulness below target**
Cause: LLM is adding information not in retrieved context.
This is a Member 1 / Member 4 issue, not yours. Report with which specific
questions failed and what the answer added that wasn't in the context.

**Monitoring dashboard shows no data**
Cause: "done" event not firing or MetricsStore not wired up.
Prevention: add a console log in the done event handler during development.
Verify MetricsStore.record() is called from the SSE router before the done event check.

---

# SECTION 11 — PRE-DEMO FINAL CHECKLIST

This is what you verify in the last 2 hours before the hackathon demo.

**Functional correctness:**
All 5 acceptance tests pass manually, in order, against the live Adani PDF
Test 4 (negative control) returns EXACTLY "Not found in the document." — string match
Refusal panel appears amber, not a grey text bubble
Citation badges appear inline with the text (not in a separate footer section)
Clicking a citation badge jumps PDF to correct page and highlights correct paragraph
BarChart renders when asking about revenue or segment performance
CodeBlock appears for numeric calculation questions
Debug Panel shows all four score bars (BM25, Vector, RRF, Rerank)
Test 5 (follow-up): Q2 correctly references Q1 context

**Technical:**
docker compose up builds and starts all services from scratch on a clean machine
No hardcoded API keys in committed code (all via .env)
The .env.example file exists with all required variable names (empty values)
RAGAS evaluation script runs end-to-end, faithfulness > 0.85
Voice works in Chrome (Web Speech API path)
All pages load in under 2 seconds on localhost

**Demo readiness:**
3-minute walkthrough rehearsed at least twice
PDF is pre-uploaded and project is in "ready" state at demo start (don't waste demo
time on ingestion — prepare the workspace in advance)
Debug Panel is closed at demo start (open it dramatically at the right moment)
RAGAS score is pre-computed and visible in the Monitoring Dashboard
Browser is in dark mode, font size is readable from a projector distance (minimum 16px body)
