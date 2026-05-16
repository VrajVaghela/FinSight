# FinSight AI — Backend Engineer & Infrastructure Lead
# Implementation Plan Part 3: Integration Contracts, Endpoints, Dockerfile & Checkpoints

---

## 12. INTEGRATION CONTRACTS — HOW YOU CONNECT WITH EACH MEMBER

### 12.1 Member 1 (RAG Architect) — You CALL Their Code

```python
# INTERFACE CONTRACT: retrieval_engine.py

# You import and call these classes from chat_service.py:

from retrieval_engine import HybridRetriever, RRFMerger, NeuralReranker, RefusalGate

# --- HybridRetriever ---
retriever = HybridRetriever(qdrant_client, bm25_index)
raw_results = await retriever.search(
    query=standalone_query,
    project_id=str(project_id),    # YOU enforce this filter
    top_k=150                       # Retrieve top 150 for reranking
)
# Returns: list[RetrievedChunk]
# RetrievedChunk = {chunk_id, raw_text, score, page_number,
#                   section_header, bounding_box, is_table, source: "bm25"|"dense"}

# --- RRFMerger ---
fused = RRFMerger.merge(raw_results, k=60)
# Returns: list[RetrievedChunk] sorted by RRF score

# --- RefusalGate (Levels 1-3) ---
gate = RefusalGate(llm_client=openai_client)

# Gate 1: Score threshold
gate1_result = gate.check_score_threshold(fused, threshold=0.5)
# Returns: GateResult(passed=bool, reason=str)

# Gate 2: Reranker threshold
reranked = NeuralReranker(model="cross-encoder/ms-marco-MiniLM-L-6-v2")
reranked_chunks = await reranker.rerank(standalone_query, fused[:150], top_k=10)
gate2_result = gate.check_reranker_threshold(reranked_chunks)

# Gate 3: LLM grader
gate3_result = await gate.llm_grade(standalone_query, reranked_chunks)
# Returns: GateResult(passed=bool, reason=str)
```

**What you provide to Member 1:**
- Qdrant client instance (from dependencies.py)
- Project ID for metadata filtering
- Query string (already rewritten by your QueryRewriter)

---

### 12.2 Member 2 (Data Engineer) — They Use YOUR Infrastructure

```python
# INTERFACE CONTRACT: ingestion_pipeline.py

# Member 2 uses YOUR Celery worker setup to run ingestion tasks.
# You provide the Celery app config and Redis broker.

# workers/celery_app.py (YOUR FILE):
from celery import Celery

celery_app = Celery(
    "finsight",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/1",
    include=["workers.ingestion_tasks"]  # Member 2 writes this module
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,  # For long-running PDF tasks
)

# Member 2 writes: workers/ingestion_tasks.py
# They import YOUR celery_app:
# from workers.celery_app import celery_app
# @celery_app.task(bind=True)
# def ingest_pdf(self, file_id: str, project_id: str, file_path: str): ...

# YOUR endpoint triggers their task:
# In api/files.py:
from workers.ingestion_tasks import ingest_pdf
task = ingest_pdf.delay(str(file_id), str(project_id), storage_path)
# Return task.id so frontend can poll status
```

**What you provide to Member 2:**
- Celery app configuration
- Redis broker connection
- File upload handling and storage path
- PostgreSQL File model (they update docling_status)
- `/api/projects/{id}/files` endpoint (upload) and `/api/projects/{id}/status` (polling)

---

### 12.3 Member 4 (PAL & Verification) — You CALL Their Code

```python
# INTERFACE CONTRACT: reasoning_engine.py & citation_engine.py & glean_verifier.py

# --- PAL Router ---
from reasoning_engine import PALRouter, CodeGenerator, SymbolicExecutor

pal_router = PALRouter(llm_client=openai_client)
query_type = await pal_router.classify(standalone_query)
# Returns: "calculation" | "narrative"

if query_type == "calculation":
    code_gen = CodeGenerator(llm_client=openai_client)
    code = await code_gen.generate(standalone_query, compressed_context)
    # Returns: str (Python code)

    executor = SymbolicExecutor()
    result = executor.run(code)
    # Returns: ExecutionResult(success=bool, output=str, error=str|None)
    # Has self-correction loop built in (max 3 retries)

# --- Citation Engine ---
from citation_engine import CitationQueryEngine, BoundingBoxMapper

citation_engine = CitationQueryEngine()
cited_response = citation_engine.add_citations(
    response_text=llm_response,
    source_chunks=reranked_chunks
)
# Returns: str with [Source 1, p5] inline citations

bbox_mapper = BoundingBoxMapper()
visual_citations = bbox_mapper.map(cited_response.citation_ids, reranked_chunks)
# Returns: list[{chunk_id, page, bounding_box: {x,y,w,h}}]

# --- GLEAN Verifier (Gate 4) ---
from glean_verifier import GLEANVerifier

verifier = GLEANVerifier(llm_client=openai_client)
verify_result = await verifier.verify(
    response=llm_response,
    retrieved_chunks=reranked_chunks,
    project_guidelines=project.system_prompt
)
# Returns: VerifyResult(passed=bool, violations=list[str], corrected_response=str|None)
```

---

### 12.4 Member 5 (Frontend) — They Call YOUR Endpoints

```
ENDPOINTS YOU EXPOSE TO FRONTEND:

POST   /api/projects                    → ProjectResponse
POST   /api/projects/{id}/files         → FileUploadResponse
GET    /api/projects/{id}/status        → ProjectStatusResponse
POST   /api/chat                        → SSE stream (text/event-stream)
GET    /api/chat/history/{conv_id}      → ConversationHistory
POST   /api/tts                         → audio/mpeg stream
WS     /ws/voice                        → bidirectional JSON+binary
GET    /api/health                      → {"status": "ok"}

SSE EVENT TYPES (frontend must handle all):
- event: chunk          → append delta text, store citations
- event: retrieval_debug → populate debug panel
- event: ui_component   → mount BarChart/Table/PDFOverlay/CodeBlock
- event: refusal         → show refusal message
- event: pal_execution  → show "Calculated" badge with code
- event: done           → finalize, show token stats

CORS: Allow origin http://localhost:3000 (dev) and frontend service (prod)
Auth: Bearer JWT token in Authorization header (or query param for WebSocket)
```

---

## 13. API ENDPOINTS IMPLEMENTATION

### 13.1 main.py

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import projects, chat, voice, health, files
from app.models.database import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()           # Create tables / run migrations
    # Initialize Qdrant collection if not exists
    yield
    # Shutdown: cleanup connections

app = FastAPI(
    title="FinSight AI",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
app.include_router(projects.router, prefix="/api", tags=["Projects"])
app.include_router(files.router, prefix="/api", tags=["Files"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(voice.router, tags=["Voice"])
```

### 13.2 chat.py (SSE Streaming Endpoint)

```python
# app/api/chat.py
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from app.models.schemas import ChatRequest
from app.services.chat_service import ChatService
from app.dependencies import get_chat_service, get_current_user

router = APIRouter()

@router.post("/chat")
async def chat_endpoint(
    req: ChatRequest,
    user_id: str = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service)
):
    async def event_generator():
        async for event in service.process_chat(
            project_id=req.project_id,
            conversation_id=req.conversation_id,
            message=req.message,
            user_id=user_id,
            language=req.language,
            voice=req.voice,
            debug=req.debug
        ):
            yield event

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )

@router.get("/chat/history/{conversation_id}")
async def get_history(
    conversation_id: str,
    user_id: str = Depends(get_current_user),
    service: ChatService = Depends(get_chat_service)
):
    return await service.get_conversation_history(conversation_id, user_id)
```

### 13.3 voice.py (WebSocket)

```python
# app/api/voice.py
import io
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.services.chat_service import ChatService
from app.core.voice_handler import VoiceHandler
from app.dependencies import verify_ws_token, get_chat_service_ws

router = APIRouter()

@router.websocket("/ws/voice")
async def voice_websocket(
    ws: WebSocket,
    project_id: str = Query(...),
    conversation_id: str = Query(None),
    token: str = Query(...)
):
    user_id = await verify_ws_token(token)
    if not user_id:
        await ws.close(code=4001, reason="Unauthorized")
        return

    await ws.accept()
    voice = VoiceHandler()
    audio_buffer = bytearray()

    try:
        while True:
            data = await ws.receive()

            if "bytes" in data:
                audio_buffer.extend(data["bytes"])
                # Check for silence / end-of-speech (VAD)
                if voice.detect_silence(audio_buffer):
                    # Transcribe
                    text = await voice.transcribe(bytes(audio_buffer))
                    audio_buffer.clear()
                    await ws.send_json({"type": "transcript", "text": text})

                    # Process through chat pipeline
                    chat_svc = await get_chat_service_ws()
                    async for event in chat_svc.process_chat(
                        project_id=project_id,
                        conversation_id=conversation_id,
                        message=text,
                        user_id=user_id,
                        voice=True
                    ):
                        # Send text events as JSON
                        await ws.send_text(event)

                    # Send TTS audio
                    tts_audio = await voice.synthesize(
                        chat_svc.last_response_text
                    )
                    await ws.send_bytes(tts_audio)

            elif "text" in data:
                msg = data["text"]
                if msg == '{"interrupted": true}':
                    voice.cancel_tts()
                    audio_buffer.clear()

    except WebSocketDisconnect:
        pass
```

---

## 14. MULTI-STAGE DOCKERFILE

```dockerfile
# backend/Dockerfile

# ---- Stage 1: Dependencies ----
FROM python:3.12-slim AS dependencies

RUN pip install uv
WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

# ---- Stage 2: Production ----
FROM python:3.12-slim AS production

# System deps for sentence-transformers, audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from dependencies stage
COPY --from=dependencies /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p /app/uploads

# Non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 15. ENVIRONMENT VARIABLES (.env)

```env
# LLM APIs
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=finsight
POSTGRES_USER=finsight
POSTGRES_PASSWORD=finsight_dev
DATABASE_URL=postgresql+asyncpg://finsight:finsight_dev@postgres:5432/finsight

# Redis
REDIS_URL=redis://redis:6379/0

# Qdrant
QDRANT_HOST=qdrant
QDRANT_PORT=6333

# App
JWT_SECRET=your-secret-key-change-in-prod
CORS_ORIGINS=http://localhost:3000
UPLOAD_DIR=/app/uploads

# Models
GENERATION_MODEL=gpt-4o
UTILITY_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-large
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2

# Feature flags
ENABLE_PROMPT_CACHING=true
ENABLE_SLM_COMPRESSION=true
ENABLE_VOICE=true
DEBUG_MODE=false
```

---

## 16. STEP-BY-STEP CHECKPOINTS (Mapped to Project Phases)

### PHASE 1 (Hours 0-6): Foundation

| # | Task | Depends On | Output | Checkpoint |
|---|------|-----------|--------|------------|
| 1.1 | Init repo: `uv init`, create pyproject.toml with all deps | Nothing | pyproject.toml, uv.lock | `uv sync` succeeds |
| 1.2 | Write docker-compose.yml (all 6 services) | Nothing | docker-compose.yml | `docker compose up -d postgres redis qdrant` all healthy |
| 1.3 | Create SQLAlchemy models (orm.py) + Alembic migration | 1.1 | models/, alembic/ | `alembic upgrade head` creates tables |
| 1.4 | Create Pydantic schemas (schemas.py) | Nothing | schemas.py | Import succeeds |
| 1.5 | Build FastAPI skeleton: main.py + health endpoint | 1.1 | main.py | `curl localhost:8000/api/health` → 200 |
| 1.6 | Build /api/projects CRUD endpoints | 1.3, 1.5 | projects.py | Can create/list projects via curl |
| 1.7 | Build /api/projects/{id}/files upload endpoint | 1.6 | files.py | PDF saved to /uploads, File record created |
| 1.8 | Set up Celery app + Redis broker | 1.2 | celery_app.py | Celery worker starts, connects to Redis |
| 1.9 | Wire Member 2's ingestion task trigger | 1.7, 1.8 | files.py calls ingest_pdf.delay() | Upload triggers Celery task (stub ok) |

**Phase 1 Checkpoint**: `docker compose up` starts all services; can upload PDF and see "pending" status.

---

### PHASE 2 (Hours 6-14): Chat Pipeline Core

| # | Task | Depends On | Output | Checkpoint |
|---|------|-----------|--------|------------|
| 2.1 | Implement QueryRewriter in memory_manager.py | Phase 1 | memory_manager.py | "Break that down" → standalone query |
| 2.2 | Implement ProjectMemory | 2.1 | memory_manager.py | System prompt loaded from DB |
| 2.3 | Build SSEFormatter (streaming.py) | Nothing | streaming.py | Can format all 6 event types |
| 2.4 | Build chat_service.py orchestrator (skeleton) | 2.1-2.3 | chat_service.py | Calls modules in sequence |
| 2.5 | Wire /api/chat SSE endpoint | 2.4 | chat.py | `curl -N /api/chat` → SSE events stream |
| 2.6 | Integrate Member 1's retrieval module | 2.4, M1 ready | chat_service.py | Query returns retrieved chunks |
| 2.7 | Wire RefusalGate levels 1-3 | 2.6, M1 ready | chat_service.py | "CEO email?" → refusal SSE event |
| 2.8 | Implement SLM Compression | 2.6 | slm_compressor.py | Chunks compressed before generation |

**Phase 2 Checkpoint**: Can ask "What are the major business segments?" → cited SSE answer; "CEO email?" → refusal.

---

### PHASE 3 (Hours 14-20): PAL, Citations, GLEAN

| # | Task | Depends On | Output | Checkpoint |
|---|------|-----------|--------|------------|
| 3.1 | Integrate PAL Router from Member 4 | 2.4, M4 ready | chat_service.py | Numeric questions route to PAL |
| 3.2 | Wire PAL execution SSE events | 3.1 | chat_service.py | SSE: pal_execution {code, result} |
| 3.3 | Integrate CitationEngine from Member 4 | 2.4, M4 ready | chat_service.py | [Source N, pX] in responses |
| 3.4 | Integrate GLEAN Verifier (Gate 4) | 3.3, M4 ready | chat_service.py | Post-gen check active |
| 3.5 | Implement UI component decision logic | 3.1-3.3 | chat_service.py | Revenue query → BarChart event |
| 3.6 | Implement prompt caching | 2.4 | prompt_cache.py | Follow-up queries use cached prefix |

**Phase 3 Checkpoint**: "What % did income grow?" → PAL calculates, [Source 3, p13] citation, BarChart UI event.

---

### PHASE 4 (Hours 20-28): Memory, Multi-turn, Multilingual

| # | Task | Depends On | Output | Checkpoint |
|---|------|-----------|--------|------------|
| 4.1 | Implement MEM1Adapter | Phase 3 | memory_manager.py | Compact state persists in Redis |
| 4.2 | Wire full conversational flow | 4.1 | chat_service.py | Q2 references Q1 correctly |
| 4.3 | Add language detection (langdetect) | Phase 3 | chat_service.py | Hindi query → Hindi response |
| 4.4 | Wire MEM1 state update after each turn | 4.1 | chat_service.py | Session state grows intelligently |
| 4.5 | Implement conversation persistence | 4.2 | conversation_service.py | Full history retrievable |

**Phase 4 Checkpoint**: T5 passes: "Summarize airport" → "Break that down" works with context.

---

### PHASE 5 (Hours 28-36): Voice & Polish

| # | Task | Depends On | Output | Checkpoint |
|---|------|-----------|--------|------------|
| 5.1 | Implement VoiceHandler (Whisper STT + TTS) | Phase 4 | voice_handler.py | Audio → text → audio works |
| 5.2 | Build /ws/voice WebSocket endpoint | 5.1 | voice.py | WebSocket connects, streams work |
| 5.3 | Implement barge-in support | 5.2 | voice.py | Interrupt cancels TTS |
| 5.4 | Build /api/tts REST endpoint | 5.1 | voice.py | POST text → audio stream |
| 5.5 | Add JWT auth middleware | Phase 4 | auth.py | All endpoints require valid JWT |

**Phase 5 Checkpoint**: Voice question → spoken answer with citations.

---

### PHASE 6 (Hours 36-42): Production Polish

| # | Task | Depends On | Output | Checkpoint |
|---|------|-----------|--------|------------|
| 6.1 | Write multi-stage Dockerfile | Phase 5 | Dockerfile | Image builds < 500MB |
| 6.2 | Test docker compose up end-to-end | 6.1 | All services | Single command starts everything |
| 6.3 | Add structured logging (JSON) | Phase 5 | All modules | Request tracing works |
| 6.4 | Performance: connection pooling, timeouts | Phase 5 | config.py, database.py | p99 latency acceptable |
| 6.5 | Write integration tests for T1-T5 | Phase 5 | tests/ | All 5 acceptance tests pass |
| 6.6 | Add /api/retrieval/debug endpoint | Phase 5 | chat.py | Debug panel data available |

**Phase 6 Checkpoint**: `docker compose up` → all T1-T5 pass → ready for demo.

---

## 17. CRITICAL RULES TO REMEMBER

> [!CAUTION]
> 1. **ALWAYS filter by project_id** in every Qdrant query — zero cross-contamination
> 2. **NEVER let LLM do arithmetic** — always route through PAL
> 3. **NEVER skip any refusal gate** — T4 (CEO email) must return "Not found"
> 4. **Use GPT-4o-mini for utility tasks** (grading, rewriting, compression), GPT-4o only for generation
> 5. **SLM compression is NOT stop-word removal** — it's query-aware sentence extraction
> 6. **Use `uv` not `pip`** — hackathon speed matters
> 7. **SSE streaming must include all 6 event types** — frontend depends on this contract

---

## 18. pyproject.toml (Dependencies)

```toml
[project]
name = "finsight-backend"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "uvloop>=0.21.0",
    "httptools>=0.6.0",
    "sqlalchemy[asyncio]>=2.0.36",
    "asyncpg>=0.30.0",
    "alembic>=1.14.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.7.0",
    "celery>=5.4.0",
    "redis>=5.2.0",
    "qdrant-client>=1.12.0",
    "openai>=1.60.0",
    "anthropic>=0.40.0",
    "python-multipart>=0.0.18",
    "python-jose[cryptography]>=3.3.0",
    "langdetect>=1.0.9",
    "rank-bm25>=0.2.2",
    "sentence-transformers>=3.4.0",
    "docling>=2.0.0",
    "llama-index>=0.12.0",
    "websockets>=14.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```
