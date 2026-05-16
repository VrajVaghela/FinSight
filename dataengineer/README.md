# FinSight AI — Data Engineering (Member 2)

This repository contains the backend data ingestion architecture for FinSight AI. It handles the asynchronous processing of financial PDFs into structured, semantically enriched chunks ready for RAG retrieval.

## Architecture

- **PDF Parsing:** Docling (DocLayNet + TableFormer)
- **Structural Chunking:** H1/H2 boundaries, isolated tables & images
- **Contextual Enrichment:** Gemini 2.5 Flash Lite (Context Summaries + Table KV extraction)
- **Enterprise Security:** Zero-Trust Regex PII Redaction (SSN, Phone, Email masking)
- **Image Handling:** Gemini Vision (Visual descriptions of charts/figures)
- **Dual Indexing:**
  - **Dense Vectors:** Gemini Embeddings (`gemini-embedding-001`, 3072-dim) → Qdrant *(Optional: Jina AI Late Chunking)*
  - **Sparse Vectors:** `rank_bm25` persisted per `project_id`
- **Orchestration:** FastAPI + Celery + PostgreSQL + Redis

## Operational Flow (The 7 Phases)

This backend implements a strict 7-phase pipeline to guarantee perfect data retrieval:

1. **The Front Door:** Fast API instantly accepts PDFs, queues them in Redis, and returns a "pending" status so the UI never freezes.
2. **Visual Reading:** `Docling` is used to map the visual layout of the PDF, preventing tables from being destroyed by standard top-to-bottom text scraping.
3. **Slicing the Document:** The `chunker` cuts the document intelligently at Heading boundaries (H1/H2) and perfectly isolates tables as HTML.
4. **Making Data Smart:** Gemini 2.5 Flash Lite is used to prepend 50-word context summaries to every chunk and extract key-value JSON pairs from tables to cure "AI Amnesia".
5. **Tagging and Tracking:** Every chunk is assigned strict metadata including `project_id` for security, `chunk_index` for ordering, and `bounding_box` coordinates for UI citations.
6. **The Dual Librarian:** Data is saved into Qdrant via Gemini Embeddings (for vector/meaning search) and into a local BM25 file (for exact keyword search).
7. **Closing the Loop:** Celery updates the PostgreSQL database status to `ready`, signaling the frontend that the document is ready for chat.

## Local Setup

1. **Environment Variables:** Create a `.env` file based on the provided setup.
   ```env
   DATABASE_URL=postgresql://admin:password123@localhost:5432/finsight
   REDIS_URL=redis://localhost:6379
   QDRANT_HOST=localhost
   QDRANT_PORT=6333
   GEMINI_API_KEY=your_key_here
   JINA_API_KEY=optional_for_late_chunking
   ENABLE_PII_REDACTION=true
   ```

2. **Start Infrastructure (Docker):**
   ```bash
   docker-compose up -d
   ```

3. **Install Dependencies:**
   ```bash
   uv pip install -r requirements.txt
   ```

4. **Start the API & Worker:**
   ```bash
   # Terminal 1: FastAPI
   uv run uvicorn backend.main:app --reload

   # Terminal 2: Celery Worker (Set to 5 concurrent tasks)
   uv run celery -A backend.celery_app worker --loglevel=info --pool=threads --concurrency=5
   ```

## Endpoints Exposed

- `POST /api/projects/{id}/files` — Upload a document to start processing.
- `GET /api/projects/{id}/status` — Poll the ingestion status (`pending` -> `processing` -> `ready`).
