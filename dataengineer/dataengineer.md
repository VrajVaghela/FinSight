# FinSight AI — Member 2: Data Engineer & Ingestion Lead
### Implementation Plan | Architecture | Data Flow | Integration Guide

> **Owns:** PDF parsing → structural/late chunking → enrichment → metadata → dual indexing → async pipeline  
> **Endpoints:** `POST /api/projects/{id}/files` · `GET /api/projects/{id}/status`  
> **Feeds:** Member 1 (Retrieval), Member 4 (Citations/PAL), Member 3 (Infrastructure), Member 5 (Frontend)

---

## 1. Your Role in the Big Picture

You are **Layer 7 — the foundation**. Every downstream component depends entirely on what you produce. Bad chunks = bad retrieval. Missing bounding boxes = broken citations. Wrong `project_id` = cross-project contamination.

```
PDF Upload
    ↓
[YOU] Docling Parser → Structural Chunker → Contextual Enricher
    → Metadata Extractor → Gemini Embeddings → Dual Indexer (Qdrant + BM25)
    ↓                          ↓
Member 1 reads Qdrant      Member 4 reads bounding boxes & table KV
Member 3 triggers you      Member 5 polls your status endpoint
```

---

## 2. Component Architecture

### Internal Modules (all inside `backend/ingestion/`)

| Module | Class | Single Responsibility |
|---|---|---|
| `docling_parser.py` | `DoclingParser` | PDF → structured document object via Docling SDK |
| `chunker.py` | `StructuralChunker` | Document → heading-anchored, table-aware chunks |
| `enricher.py` | `ContextualEnricher` | Chunks → LLM-prepended context summaries |
| `metadata_extractor.py` | `MetadataExtractor` | Chunks → bounding boxes, page numbers, indices, UUIDs |
| `dual_indexer.py` | `DualIndexer` | Chunks → Qdrant (dense, via Gemini embeddings) + BM25 (sparse) |
| `celery_worker.py` | `ingest_document` | Async Celery task wrapping the full pipeline |
| `pipeline.py` | `run_ingestion()` | Orchestrator — calls all above in sequence |

---

## 3. Data Flow

### What data looks like at each stage

```
Raw PDF bytes
    ↓ DoclingParser
DoclingDocument  (layout tree: headings, text blocks, tables with bounding boxes)
    ↓ StructuralChunker
List of RawChunks  (raw_text, chunk_type, table_html if table)
    ↓ ContextualEnricher
List of EnrichedChunks  (+ context_summary prepended to text, table_kv extracted via SLM)
    ↓ MetadataExtractor
List of FinalChunks  (+ chunk_id, chunk_index, project_id, file_id, page_number, bounding_box)
    ↓ DualIndexer (with Late Chunking)
  → Qdrant: Gemini `gemini-embedding-001` 3072-dim vector + full payload
  → BM25: raw_text tokenized, index persisted to disk by project_id
    ↓
PostgreSQL: status = "ready", page_count = N
```

### Key Design Rules (Non-Negotiable)

- **No fixed-token splitting.** Chunks follow heading boundaries.
- **Each table = one chunk.** Never split a table.
- **Gemini Embeddings for Vectors:** Embed `enriched_text` with `RETRIEVAL_DOCUMENT` at 3072 dimensions for Qdrant.
- **`enriched_text` goes to embeddings.** `raw_text` alone goes to BM25.
- **Every chunk must have `project_id`** in its Qdrant payload — enables project isolation.

---

## 4. Control Flow

### Upload to Ready (Full Sequence)

1. Member 3 saves PDF to disk, creates `files` record (status = `"pending"`).
2. Member 3 dispatches: `ingest_document.delay(file_id, project_id, file_path)`.
3. YOUR Celery worker picks up the task; Status → `"processing"`.
4. `DoclingParser` parses PDF (DocLayNet layout + TableFormer tables).
5. `StructuralChunker` walks element tree:
   - Heading H1/H2 → new chunk boundary.
   - Table → isolated chunk, serialized to HTML.
   - Paragraph → appended to current chunk.
6. `ContextualEnricher` calls Gemini 2.5 Flash Lite:
   - Builds prompt with doc title, date, section name.
   - Gets 50-100 token summary.
   - For tables: Extracts JSON key-value pairs (`table_kv`) for the PAL engine.
7. `MetadataExtractor` maps each chunk back to Docling source elements:
   - Extracts `page_number` and assigns a sequential `chunk_index`.
   - Computes union `bounding_box` across all elements.
   - Tags with `project_id`, `file_id`.
8. `DualIndexer` (parallel):
   - Embeds `enriched_text` → Gemini `gemini-embedding-001` (`RETRIEVAL_DOCUMENT`) → Qdrant.
   - Tokenizes `raw_text` → BM25Okapi index → persist to `/data/bm25_indexes/{project_id}.pkl`.
9. Status → `"ready"`, `page_count` written to PostgreSQL.

### Status Polling (Member 5 Frontend)

```
GET /api/projects/{id}/status
    ↓
Read files.docling_status from PostgreSQL
    ↓
Return: { status, page_count, chunk_count, error_message }
```

---

## 5. Data Schemas

### 5.1 FinalChunk — Your Core Output Object

| Field | Type | Description |
|---|---|---|
| `chunk_id` | UUID string | Primary key — same as Qdrant point ID |
| `chunk_index` | int | Sequential order of chunk in doc (vital for context stitching) |
| `project_id` | UUID string | For isolation — MUST be on every chunk |
| `file_id` | UUID string | Which file this chunk came from |
| `page_number` | int (1-indexed) | Page of first element in chunk |
| `section_header` | string | Nearest H1/H2 ancestor text |
| `raw_text` | string | Original chunk text (used by BM25 + shown in UI) |
| `context_summary` | string | LLM-generated 50-100 token prefix |
| `enriched_text` | string | `context_summary` + `"\n\n"` + `raw_text` |
| `bounding_box` | `{x, y, w, h}` | Normalized 0.0–1.0 page coordinates |
| `token_count` | int | tiktoken count of `raw_text` |
| `is_table` | bool | True if chunk is a table |
| `table_html` | string or null | HTML serialization of table |
| `table_kv` | dict or null | Key-value pairs extracted from table (for PAL) |

### 5.2 Qdrant Collection: `document_chunks`

- **Vector:** 3072 dimensions, Cosine distance.
- **Payload:** All FinalChunk fields stored as-is.
- **Payload Indexes (must create):** `project_id` (keyword), `file_id` (keyword), `is_table` (bool).
- **Point ID:** `chunk_id` (UUID).

> Without payload indexes, every query does a full scan. Create them at collection setup time.

### 5.3 BM25 Index Format

- **Storage:** `/data/bm25_indexes/{project_id}.pkl`
- **Contents:** Serialized dict with the BM25Okapi index object, a parallel list of `chunk_ids`, and a parallel list of `raw_texts`
- **Scoping:** Separate file per project → natural project isolation for BM25

### 5.4 PostgreSQL Tables You Write To

- **`files` table** — you update `docling_status`, `page_count`, `ingested_at`, `error_message`
- **`projects` table** — you only read this (to get doc title/date for enrichment prompts)

### 5.5 Status Values Contract

`"pending"` → `"processing"` → `"ready"` or `"failed"`

On `"failed"`: `error_message` field must be human-readable, not a raw stack trace.

---

## 6. Checkpoint-Wise Plan

### Checkpoint 1 — Hours 0–6 | Parser + Basic Qdrant Write

**Goal:** Docling works. One chunk in Qdrant. Prove the pipeline breathes.

- Set up `uv` environment.
- `DoclingParser` wrapping Docling SDK — test on Adani PDF.
- Create Qdrant collection with payload indexes.
- Write one chunk to Qdrant manually.

**Team Signal:** Tell Member 1 — Qdrant is live, collection is ready.

---

### Checkpoint 2 — Hours 6–10 | Full Chunker + Metadata + Table KV

**Goal:** Metadata complete. Async pipeline running. Tables ready for PAL.

- Complete `StructuralChunker` and `MetadataExtractor` (`chunk_index`, bounding boxes).
- Call SLM on tables to extract `table_kv` (Crucial unblocker for Member 4).
- Wire up `celery_worker.py` and `/api/projects/{id}/status` endpoint.

**Team Signal:** Member 4 can start building PAL on your structured table data.

---

### Checkpoint 3 — Hours 10–14 | Contextual Enrichment + Late Chunking

**Goal:** Contextual prepending and semantic Late Chunking live. BM25 indexed.

- `ContextualEnricher` — SLM generates summaries per chunk.
- Update `DualIndexer` — embed enriched chunks with Gemini before Qdrant upsert.
- BM25 index built and persisted to disk per `project_id`.

**Team Signal:** Member 1 has everything needed for hybrid RRF retrieval.

---

### Checkpoint 4 — Hours 18–24 | Multi-File + Project Isolation

**Goal:** Multiple PDFs per project work. Zero cross-project contamination proven.

- Re-ingestion: delete old Qdrant points for `file_id` before re-indexing.
- BM25: rebuild index for project when new file added.
- Run isolation test with Member 1.

---

### Checkpoint 5 — Hours 36–40 | Stability + Error Handling

**Goal:** All failure paths handled gracefully.

- Password-protected PDF → `failed` with clear message
- Empty/corrupt PDF → `failed`
- Gemini API timeout during enrichment → degrade gracefully (skip summary, don't crash)
- Re-ingestion idempotency verified

---

## 7. Integration Contracts

### → Member 1 (Retrieval)

- Qdrant collection `document_chunks` is the source of truth.
- Every chunk has `project_id`, `chunk_index`, `raw_text`, `context_summary` in payload.
- BM25 index at `/data/bm25_indexes/{project_id}.pkl` — dict with `index`, `chunk_ids`, `raw_texts`.

### → Member 4 (Citations & PAL)

- `bounding_box` format: `{x, y, w, h}` floats, normalized 0.0–1.0.
- `table_kv` is populated early in pipeline so your PAL engine has numbers to calculate.

### → Member 3 (Backend/Infrastructure)

- Celery task name: `ingestion.ingest_document`, params: `file_id`, `project_id`, `file_path`.
- Required Env Vars: `GEMINI_API_KEY`, `QDRANT_HOST`, `QDRANT_PORT`, `REDIS_URL`, `DATABASE_URL`, `BM25_INDEX_DIR`, `PDF_UPLOAD_DIR`.

### → Member 5 (Frontend)

- Status endpoint response includes: `status`, `page_count`, `chunk_count`, `error_message`.
- Bounding boxes are ready to be used by React-PDF overlay.

---

## 8. Error Handling Summary

| Scenario | Behavior |
|---|---|
| Password-protected PDF | Catch Docling error → status `failed` with message |
| Scanned PDF (no text) | Docling OCR fallback → slower but proceeds |
| Corrupt/empty PDF | Catch exception → status `failed` |
| Gemini API down (enrichment) | Retry 3× with backoff → if still failing, store chunk without summary |
| Qdrant unreachable | Celery retry after 30s, max 2 retries → then `failed` |
| Same file re-uploaded | Delete old Qdrant points for `file_id` → rebuild BM25 → re-index |

---

## First 30-Minute Checklist

- [ ] Install dependencies via `uv`
- [ ] Verify Qdrant and Redis running via Docker
- [ ] Test Docling on Adani PDF — confirm no parse error
- [ ] Create Qdrant collection with payload indexes
- [ ] Confirm `project_id` UUID format with Member 3
- [ ] Confirm `table_kv` structure requirements with Member 4

---

*FinSight AI · Member 2 — Data Engineer & Ingestion Lead · May 2026*
