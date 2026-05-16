# FinSight AI — Backend Engineer & Infrastructure Lead
# Complete Implementation Plan (Part 1: Architecture & Data Schemas)

> **Role**: Member 3 — Backend Engineer & Infrastructure Lead
> **Owns**: FastAPI server, Docker Compose, WebSocket voice, MEM1 memory, project workspaces, prompt caching, SLM compression, QueryRewriter

---

## 1. YOUR COMPONENT OWNERSHIP MAP

```
backend/
├── app/
│   ├── main.py                    # FastAPI app, CORS, lifespan, router mounting
│   ├── config.py                  # Settings via pydantic-settings (env vars)
│   ├── dependencies.py            # Shared DI: db sessions, redis, qdrant client
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── projects.py            # POST /api/projects, GET /api/projects/{id}/status
│   │   ├── chat.py                # POST /api/chat (SSE streaming)
│   │   ├── voice.py               # WebSocket /ws/voice, POST /api/tts
│   │   ├── health.py              # GET /api/health
│   │   └── files.py               # POST /api/projects/{id}/files (delegates to Member 2)
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── memory_manager.py      # QueryRewriter, ProjectMemory, MEM1Adapter
│   │   ├── prompt_cache.py        # Anthropic prompt caching logic
│   │   ├── slm_compressor.py      # SLM contextual compression (GPT-4o-mini)
│   │   ├── streaming.py           # SSE event formatter & generator
│   │   └── voice_handler.py       # Whisper STT + TTS pipeline
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── database.py            # SQLAlchemy engine, Base, session factory
│   │   ├── schemas.py             # Pydantic request/response models
│   │   └── orm.py                 # SQLAlchemy ORM models (projects, files, conversations, messages)
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── project_service.py     # CRUD for projects, file associations
│   │   ├── chat_service.py        # Orchestrator: rewrites query → calls retrieval → gates → generation → SSE
│   │   └── conversation_service.py # Conversation CRUD, message persistence
│   │
│   └── middleware/
│       ├── __init__.py
│       └── auth.py                # JWT verification middleware
│
├── workers/
│   └── celery_app.py              # Celery config (used by Member 2's ingestion tasks)
│
├── Dockerfile                     # Multi-stage build
├── docker-compose.yml             # 6 services
├── pyproject.toml                 # uv-managed dependencies
├── uv.lock
├── alembic/                       # DB migrations
│   ├── env.py
│   └── versions/
└── tests/
    ├── test_chat.py
    ├── test_projects.py
    └── test_voice.py
```

---

## 2. POSTGRESQL DATA SCHEMAS (ORM Models)

### 2.1 orm.py — SQLAlchemy Models

```python
# app/models/orm.py
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, DateTime, Integer, Boolean,
    ForeignKey, JSON, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import relationship
from app.models.database import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    system_prompt = Column(Text, default="")
    owner_id = Column(String(255), nullable=False)   # from JWT
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    files = relationship("File", back_populates="project", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="project", cascade="all, delete-orphan")


class File(Base):
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    original_name = Column(String(512), nullable=False)
    storage_path = Column(String(1024), nullable=False)    # local/S3 path
    docling_status = Column(
        SAEnum("pending", "processing", "ready", "failed", name="ingestion_status"),
        default="pending"
    )
    page_count = Column(Integer, nullable=True)
    chunk_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    ingested_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="files")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    user_id = Column(String(255), nullable=False)
    title = Column(String(512), default="New Conversation")
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan",
                            order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    role = Column(SAEnum("user", "assistant", "system", name="message_role"), nullable=False)
    content = Column(Text, nullable=False)
    citations = Column(JSON, default=list)          # [{chunk_id, page, score, text_snippet}]
    retrieved_chunks = Column(JSON, default=list)    # [{chunk_id, score, text}]
    pal_execution = Column(JSON, nullable=True)      # {code, result} if PAL was triggered
    ui_components = Column(JSON, default=list)       # [{component, data}]
    refusal_info = Column(JSON, nullable=True)       # {level, reason} if refused
    token_usage = Column(JSON, nullable=True)        # {prompt, completion, cached}
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    conversation = relationship("Conversation", back_populates="messages")


class CacheEntry(Base):
    __tablename__ = "cache_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prefix_hash = Column(String(64), unique=True, nullable=False)  # SHA-256 of cached prefix
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    cached_at = Column(DateTime, default=datetime.utcnow)
    expiry = Column(DateTime, nullable=False)        # Anthropic: 5-min TTL, extended on hit
    hit_count = Column(Integer, default=0)
```

### 2.2 schemas.py — Pydantic Request/Response Models

```python
# app/models/schemas.py
from pydantic import BaseModel, Field
from typing import Optional, Literal
from uuid import UUID
from datetime import datetime

# === PROJECT ===
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    system_prompt: str = ""

class ProjectResponse(BaseModel):
    id: UUID
    name: str
    system_prompt: str
    created_at: datetime
    file_count: int = 0
    status: Literal["empty", "processing", "ready"] = "empty"

# === FILE ===
class FileUploadResponse(BaseModel):
    file_id: UUID
    original_name: str
    status: str  # "pending"
    task_id: str  # Celery task ID for polling

class ProjectStatusResponse(BaseModel):
    project_id: UUID
    files: list[dict]  # [{file_id, name, status, page_count, chunk_count}]
    overall_status: Literal["empty", "processing", "ready", "partial"]

# === CHAT ===
class ChatRequest(BaseModel):
    project_id: UUID
    conversation_id: Optional[UUID] = None  # None = create new conversation
    message: str
    language: str = "auto"                  # ISO 639-1 or "auto"
    voice: bool = False                     # if True, also return TTS audio
    debug: bool = False                     # if True, include retrieval_debug events

class Citation(BaseModel):
    chunk_id: str
    page: int
    score: float
    text_snippet: str
    bounding_box: Optional[dict] = None  # {x, y, w, h}

class SSEChunkEvent(BaseModel):
    delta: str
    citations: list[Citation] = []

class SSERetrievalDebug(BaseModel):
    chunks: list[dict]  # [{id, text_snippet, score, page, bounding_box}]

class SSEUIComponent(BaseModel):
    component: Literal["BarChart", "LineChart", "DataTable", "PDFOverlay", "CodeBlock", "PlainText"]
    data: dict

class SSERefusal(BaseModel):
    reason: Literal["level_1_threshold", "level_2_reranker", "level_3_grader", "level_4_postgen"]
    message: str

class SSEPalExecution(BaseModel):
    code: str
    result: str

class SSEDone(BaseModel):
    conversation_id: UUID
    total_tokens: int
    cached_tokens: int
    latency_ms: int

# === VOICE ===
class TTSRequest(BaseModel):
    text: str
    language: str = "en"
    voice_id: str = "alloy"

# === CONVERSATION ===
class ConversationHistory(BaseModel):
    conversation_id: UUID
    project_id: UUID
    title: str
    messages: list[dict]  # [{role, content, citations, timestamp}]
```

---

## 3. QDRANT COLLECTION SCHEMA (Reference — owned by Member 2, consumed by you)

```python
# Qdrant collection: "document_chunks"
# You MUST filter every query by project_id — this is YOUR responsibility

QDRANT_COLLECTION = "document_chunks"
VECTOR_DIM = 1536  # text-embedding-3-large

# Every point payload structure:
payload_schema = {
    "project_id": "uuid-string",         # HARD FILTER on every search
    "file_id": "uuid-string",
    "page_number": 1,                     # int
    "chunk_index": 0,                     # int, order within file
    "section_header": "Revenue Overview", # str
    "raw_text": "...",                    # str, original chunk text
    "context_summary": "...",             # str, 50-100 token LLM prepend
    "bounding_box": {"x": 0, "y": 0, "w": 100, "h": 50},
    "token_count": 342,
    "is_table": False,
    "table_html": None                    # str|null
}
```

---

## 4. ARCHITECTURE: HOW YOUR COMPONENTS FIT IN THE 7-LAYER SYSTEM

```
┌─────────────────────────────────────────────────────────────────┐
│ L1  PRESENTATION (Member 5 — Next.js 16)                       │
│     Calls YOUR endpoints: /api/chat, /ws/voice, /api/projects  │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP/SSE/WebSocket
┌──────────────────────────▼──────────────────────────────────────┐
│ YOUR LAYER — FastAPI Server (main.py)                          │
│                                                                 │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────────┐ │
│  │ /api/chat    │  │ /ws/voice    │  │ /api/projects          │ │
│  │ SSE stream   │  │ WebSocket    │  │ CRUD + status          │ │
│  └──────┬───────┘  └──────┬───────┘  └────────────────────────┘ │
│         │                 │                                      │
│  ┌──────▼─────────────────▼──────────────────────────────────┐  │
│  │           chat_service.py — ORCHESTRATOR                   │  │
│  │                                                            │  │
│  │  1. QueryRewriter (memory_manager.py)                      │  │
│  │     └─ Condenses chat history → standalone query           │  │
│  │  2. ProjectMemory (memory_manager.py)                      │  │
│  │     └─ Loads project system_prompt from PostgreSQL          │  │
│  │  3. MEM1Adapter (memory_manager.py)                        │  │
│  │     └─ Compact state for long sessions (Redis-backed)      │  │
│  │  4. PromptCache (prompt_cache.py)                          │  │
│  │     └─ Anthropic prefix caching for cost reduction         │  │
│  │  5. SLMCompressor (slm_compressor.py)                      │  │
│  │     └─ GPT-4o-mini strips irrelevant sentences             │  │
│  └──────┬────────────────────────────────────────────────────┘  │
│         │ Calls into other members' modules:                     │
└─────────┼────────────────────────────────────────────────────────┘
          │
    ┌─────▼──────────────────────────────────────────────────┐
    │  Member 1's retrieval_engine.py                         │
    │  HybridRetriever → RRFMerger → NeuralReranker          │
    │  → RefusalGate (L1, L2, L3)                            │
    ├─────────────────────────────────────────────────────────┤
    │  Member 4's reasoning_engine.py                         │
    │  PALRouter → CodeGenerator → SymbolicExecutor           │
    ├─────────────────────────────────────────────────────────┤
    │  Member 4's citation_engine.py                          │
    │  CitationQueryEngine → BoundingBoxMapper                │
    ├─────────────────────────────────────────────────────────┤
    │  Member 4's glean_verifier.py                           │
    │  GLEANVerifier → Gate 4 post-generation check           │
    └─────────────────────────────────────────────────────────┘
```

**Key insight**: You are the **integration hub**. Your `chat_service.py` orchestrates the entire query pipeline by calling modules owned by Members 1 and 4 in sequence.

---

## 5. DOCKER COMPOSE — 6 SERVICES

```yaml
# docker-compose.yml
version: "3.9"

services:
  # --- Infrastructure ---
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: finsight
      POSTGRES_USER: finsight
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-finsight_dev}
    ports: ["5432:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U finsight"]
      interval: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 5

  qdrant:
    image: qdrant/qdrant:v1.12.1
    ports: ["6333:6333", "6334:6334"]
    volumes:
      - qdrantdata:/qdrant/storage
    environment:
      QDRANT__SERVICE__GRPC_PORT: 6334

  # --- Application ---
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
      target: production
    ports: ["8000:8000"]
    env_file: .env
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
      qdrant: { condition: service_started }
    command: >
      uvicorn app.main:app --host 0.0.0.0 --port 8000
      --workers 4 --loop uvloop --http httptools
    volumes:
      - uploads:/app/uploads

  celery-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
      target: production
    env_file: .env
    depends_on:
      postgres: { condition: service_healthy }
      redis: { condition: service_healthy }
      qdrant: { condition: service_started }
    command: >
      celery -A workers.celery_app worker
      --loglevel=info --concurrency=4 --pool=prefork
    volumes:
      - uploads:/app/uploads

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    ports: ["3000:3000"]
    depends_on: [api]
    environment:
      NEXT_PUBLIC_API_URL: http://api:8000

volumes:
  pgdata:
  redisdata:
  qdrantdata:
  uploads:
```

---

*Continued in Part 2: Control Flow, Data Flow, Integration Contracts, and Step-by-Step Checkpoints*
