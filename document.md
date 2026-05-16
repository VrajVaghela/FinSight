# FinSight AI: Advanced System Architecture & Documentation

FinSight AI is an enterprise-grade Financial Retrieval-Augmented Generation (RAG) platform designed to handle complex financial documents with high precision. It integrates advanced layout-aware parsing, a sophisticated multi-stage retrieval pipeline, real-time voice interaction, and automated RAG evaluation metrics.

## Table of Contents

1. [High-Level Architecture](#1-high-level-architecture)
2. [Advanced Technology Stack](#2-advanced-technology-stack)
3. [API Reference](#3-api-reference)
4. [Core Workflows](#4-core-workflows)
5. [Project Structure](#5-project-structure)
6. [Configuration & Environment](#6-configuration--environment)
7. [Security & Authentication](#7-security--authentication)
8. [Database Schema](#8-database-schema)
9. [Voice System Deep Dive](#9-voice-system-deep-dive)
10. [Evaluation Framework](#10-evaluation-framework)
11. [Deployment & Development](#11-deployment--development)
12. [Troubleshooting & FAQs](#12-troubleshooting--faqs)

---

## 1. High-Level Architecture

The system is built on a distributed micro-services architecture, optimized for high-throughput document processing and low-latency interactive queries.

### 1.1 System Overview

FinSight AI follows a layered architecture pattern that separates concerns while enabling efficient inter-service communication:

```mermaid
graph TD
    User([User / Browser])
    
    subgraph "Frontend Layer (Next.js 15)"
        NextJS[Next.js App Router]
        GenUI[GenUI Router / Mermaid]
        DocExp[Document Explorer]
    end
    
    subgraph "Security Layer"
        Auth[JWT Auth Middleware]
    end
    
    subgraph "Backend API Layer (FastAPI)"
        ChatAPI[Chat & Voice API]
        ProjAPI[Project & File Management]
        EvalAPI[RAG Evaluation API]
    end
    
    subgraph "Processing & Retrieval (Async)"
        Celery[Celery Worker Pool]
        Ingestion[Ingestion Pipeline]
        HybridSearch[Hybrid Retriever BM25 + Vector]
        Reranker[Neural Reranker]
        RefusalGate[Refusal Gates / Guardrails]
    end
    
    subgraph "Infrastructure Layer"
        Postgres[(PostgreSQL)]
        Redis[(Redis)]
        Qdrant[(Qdrant Vector DB)]
        Storage[Local / S3 Storage]
    end
    
    subgraph "External AI Services"
        Gemini[Google Gemini API]
        Groq[Groq / Llama-3.3 Evaluator]
    end
    
    User <--> NextJS
    NextJS --> Auth
    Auth --> ChatAPI & ProjAPI & EvalAPI
    
    ChatAPI <--> HybridSearch
    HybridSearch --> Reranker
    Reranker --> RefusalGate
    RefusalGate --> ChatAPI
    
    ProjAPI -->|Task| Redis
    Redis --> Celery
    Celery --> Ingestion
    Ingestion -->|Parse| Docling(Docling SDK)
    Ingestion -->|Index| Qdrant & Postgres
    
    EvalAPI --> Groq
```

### 1.2 Data Flow Patterns

#### Synchronous Request-Response Pattern
Used for: Chat queries, file retrieval, evaluation triggers
- Client sends HTTP request with JWT token
- API validates authentication
- Retrieval pipeline executes (typically 200-800ms)
- Response streamed back via SSE or returned directly

#### Asynchronous Task Queue Pattern
Used for: Document ingestion, bulk indexing, report generation
- Client submits task via API
- Celery task queued in Redis
- Worker processes in background
- Status polled via WebSocket or polling endpoint

#### Real-Time Streaming Pattern
Used for: Voice interaction, live progress updates
- WebSocket connection established
- Audio/text streamed bidirectionally
- Server-side events (SSE) for incremental updates

---

## 2. Advanced Technology Stack

### 2.1 Frontend Ecosystem

| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | Next.js 15 (App Router) | React-based full-stack framework with SSR/CSR |
| Language | TypeScript 5.x | Type-safe frontend development |
| UI Library | React 19 | Latest React with concurrent features |
| Styling | Tailwind CSS 4 | Utility-first styling with CSS variables |
| State Management | Zustand | Lightweight, hooks-based state management |
| Real-time | Socket.io / SSE | WebSocket and Server-Sent Events |
| Document Rendering | react-pdf | PDF.js wrapper for document viewer |
| Charts | Recharts / Chart.js | Data visualization components |
| Mermaid | mermaid.js | Diagram rendering from text |
| Form Handling | React Hook Form + Zod | Form validation and schema enforcement |

#### GenUI Framework

The GenUI system dynamically renders LLM-generated JSON into interactive UI components:

```typescript
// Example GenUI component schema
interface GenUIComponent {
  type: 'chart' | 'table' | 'metric-card' | 'comparison';
  data: Record<string, unknown>;
  config: {
    title?: string;
    colors?: string[];
    showLegend?: boolean;
  };
}
```

#### Document Explorer

Coordinate-mapped PDF viewer enables:
- Precise citation jumping (click reference → scroll to PDF location)
- Source verification overlay
- Highlight matching text in PDF
- Multi-page document navigation

### 2.2 Backend & AI

| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | FastAPI | Modern async Python web framework |
| ORM | SQLAlchemy 2.0 | Async database ORM with type hints |
| Database | PostgreSQL + asyncpg | ACID-compliant relational DB |
| Vector Store | Qdrant | High-performance vector similarity search |
| Cache | Redis (async) | In-memory cache and task broker |
| Task Queue | Celery | Distributed task execution |
| Parsing | Docling SDK | Layout-aware document parsing |
| Embeddings | Google Gemini Embedding | Dense vector representation |
| LLM | Google Gemini 2.0 | Primary generative model |
| Evaluator | Groq + Llama-3.3 | Fast inference for evaluation |
| STT | Whisper | Speech-to-text processing |
| TTS | gTTS / Edge-TTS | Text-to-speech output |

#### Retrieval Pipeline Architecture

```mermaid
graph LR
    Query[User Query] --> Router[Section Router]
    Router --> Session[Session Scoping]
    Session --> Hybrid[Hybrid Retrieval]
    Hybrid --> Vector[Vector Search Qdrant]
    Hybrid --> BM25[BM25 Search]
    Vector --> RRF[RRF Merger]
    BM25 --> RRF
    RRF --> Rerank[Neural Reranker]
    Rerank --> Guard[Refusal Gate]
    Guard --> Response[Grounded Response]
    Guard --> Unknown[Refusal Response]
```

##### Key Retrieval Components

1. **Section Router**: ML model predicting relevant document sections
2. **Session Scoping**: Conversation history integration for context bias
3. **Hybrid Retrieval**: Dual-index searching (dense + sparse)
4. **Reciprocal Rank Fusion (RRF)**: Score harmonization algorithm
5. **Neural Reranker**: Cross-encoder for final precision ranking
6. **Refusal Gate**: Confidence threshold for knowledge cutoff

### 2.3 Infrastructure

| Service | Docker Image | Port | Purpose |
|---------|--------------|------|---------|
| PostgreSQL | postgres:16 | 5432 | Relational metadata storage |
| Qdrant | qdrant:latest | 6333 | Vector similarity search |
| Redis | redis:7-alpine | 6379 | Cache & Celery broker |
| Docling | docling:latest | (batch) | Document parsing |

---

## 3. API Reference

### 3.1 Authentication Endpoints

#### POST /api/auth/register
Register a new user account.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123",
  "full_name": "John Doe"
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe",
  "created_at": "2024-01-15T10:30:00Z"
}
```

#### POST /api/auth/login
Authenticate and receive JWT tokens.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

#### POST /api/auth/refresh
Refresh access token using refresh token.

#### POST /api/auth/logout
Invalidate current session.

### 3.2 Project Endpoints

#### GET /api/projects
List all projects for authenticated user.

**Response (200):**
```json
{
  "projects": [
    {
      "id": "uuid",
      "name": "Q4 Financial Report",
      "description": "Annual Q4 analysis",
      "file_count": 24,
      "created_at": "2024-01-10T08:00:00Z",
      "updated_at": "2024-01-14T16:30:00Z"
    }
  ]
}
```

#### POST /api/projects
Create a new project.

**Request:**
```json
{
  "name": "Project Name",
  "description": "Optional description"
}
```

#### GET /api/projects/{project_id}
Get project details with file list.

#### DELETE /api/projects/{project_id}
Delete project and all associated files.

### 3.3 File Management Endpoints

#### POST /api/projects/{project_id}/files
Upload a file for ingestion.

**Request (Multipart):**
```
file: <binary PDF>
chunk_size: 512
enable_ocr: true
```

**Response (202):**
```json
{
  "task_id": "celery-task-id",
  "status": "queued",
  "message": "File queued for processing"
}
```

#### GET /api/projects/{project_id}/files
List all files in project.

#### GET /api/projects/{project_id}/files/{file_id}
Get file metadata and ingestion status.

#### DELETE /api/projects/{project_id}/files/{file_id}
Delete file and its indexed content.

### 3.4 Chat & Query Endpoints

#### POST /api/chat/query
Send a text query to the RAG system.

**Request:**
```json
{
  "project_id": "uuid",
  "message": "What was the revenue growth in Q3?",
  "use_history": true,
  "stream": false
}
```

**Response (200):**
```json
{
  "response": "The revenue growth in Q3 was 15.2% year-over-year...",
  "citations": [
    {
      "file_id": "uuid",
      "page": 12,
      "text": "Revenue grew by 15.2% to $45.2M...",
      "bbox": {"x1": 100, "y1": 200, "x2": 500, "y2": 300}
    }
  ],
  "genui": null,
  "metrics": {
    "latency_ms": 450,
    "retrieved_chunks": 5
  }
}
```

#### POST /api/chat/query (Streaming)
Streaming variant using SSE.

```bash
curl -N -X POST "http://localhost:8000/api/chat/query" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"project_id": "...", "message": "What was the revenue?"}'
```

**SSE Events:**
```
event: chunk
data: {"type": "chunk", "content": "The "}

event: chunk
data: {"type": "chunk", "content": "revenue "}

event: citation
data: {"type": "citation", "file_id": "...", "page": 12}

event: done
data: {"type": "done", "latency_ms": 450}
```

### 3.5 Voice Endpoints

#### WebSocket /api/voice/ws
Real-time voice communication.

**Connection:**
```javascript
const ws = new WebSocket('ws://localhost:8000/api/voice/ws?token=<JWT>');
```

**Client → Server Messages:**
```json
// Audio chunk (binary PCM)
{"type": "audio", "data": "<binary>"}

// Text message
{"type": "text", "message": "What was the net income?"}

// Control signals
{"type": "control", "action": "start" | "stop" | "interrupt"}
```

**Server → Client Messages:**
```json
// Transcription
{"type": "transcript", "text": "What was the revenue?", "final": true}

// Response chunk
{"type": "response", "chunk": "The revenue was"}

{"type": "response", "chunk": " $15.2M in Q3."}

// Audio output
{"type": "audio", "data": "<binary PCM>"}

// Status update
{"type": "status", "idle": true}
```

### 3.6 Evaluation Endpoints

#### POST /api/evaluation/run
Run RAG evaluation on a project.

**Request:**
```json
{
  "project_id": "uuid",
  "num_samples": 20,
  "metrics": ["faithfulness", "answer_relevancy", "context_relevancy"]
}
```

**Response (202):**
```json
{
  "task_id": "celery-task-id",
  "status": "queued"
}
```

#### GET /api/evaluation/results/{task_id}
Get evaluation results.

**Response (200):**
```json
{
  "task_id": "uuid",
  "status": "completed",
  "results": {
    "faithfulness": {
      "mean_score": 0.87,
      "std": 0.12
    },
    "answer_relevancy": {
      "mean_score": 0.82,
      "std": 0.15
    },
    "context_relevancy": {
      "mean_score": 0.79,
      "std": 0.18
    }
  },
  "retrieval_metrics": {
    "hit_rate": 0.85,
    "recall_at_5": 0.72,
    "mrr": 0.81
  }
}
```

---

## 4. Core Workflows

### 4.1 Intelligent Document Ingestion

The ingestion pipeline processes uploaded documents through multiple stages to ensure accurate extraction and indexing:

```mermaid
flowchart TD
    Upload[File Upload] --> Validate[Validation]
    Validate --> Queue[Celery Queue]
    Queue --> Fetch[Fetch from Storage]
    Fetch --> Docling[Docling Parse]
    Docling --> Extract[Extract Layout Primitives]
    Extract --> Chunker[Structural Chunker]
    Chunker --> Chunks[Document Chunks]
    Chunks --> Enrich[Contextual Enrichment]
    Enrich --> Embed[Generate Embeddings]
    Embed --> IndexVec[Index to Qdrant]
    IndexVec --> IndexBM[Index to BM25]
    IndexBM --> Complete[Mark Complete]
```

#### Stage 1: Structural Parsing

Docling extracts layout primitives from documents:
- **Headings**: Hierarchical title detection with font size analysis
- **Paragraphs**: Text flow with reading order
- **Tables**: Cell structure, headers, and merged cells
- **Figures**: Image extraction with captions
- **Bounding Boxes**: Spatial coordinates for citation mapping

```python
# Docling parsing configuration
PARSING_CONFIG = {
    "resolve_links": True,
    "valid_formats": ["pdf", "docx"],
    "extract_tables": True,
    "extract_images": True,
    "page_prefix": True,
}
```

#### Stage 2: Logical Chunking

The `StructuralChunker` divides documents based on semantic boundaries:

```python
class StructuralChunker:
    """Smart chunking based on document structure."""
    
    CHUNK_STRATEGIES = {
        "by_heading": "Split at each heading level",
        "by_paragraph": "Keep paragraphs intact",
        "by_table": "Tables as atomic units",
        "fixed_size": "Fixed token windows",
        "semantic": "ML-based boundary detection",
    }
    
    def __init__(
        self,
        strategy: str = "by_heading",
        max_tokens: int = 512,
        overlap: int = 50,
    ):
        self.strategy = strategy
        self.max_tokens = max_tokens
        self.overlap = overlap
    
    def chunk(self, document: Document) -> list[Chunk]:
        """Process document into semantic chunks."""
```

#### Stage 3: Contextual Enrichment

Each chunk is enriched with metadata:
- **Summary**: LLM-generated abstract of chunk content
- **Key Entities**: Named entities (companies, figures, dates)
- **Fiscal Metrics**: Extracted financial indicators
- **Keywords**: BM25 term weights

```python
# Enrichment pipeline
ENRICHMENT_PROMPT = """
You are a financial document analyzer. For the following document chunk:
{chunk_text}

Provide:
1. A 2-sentence summary
2. Key financial metrics mentioned
3. Relevant entities (companies, people, dates)
"""

class ChunkEnricher:
    """Enrich chunks with LLM-generated metadata."""
    
    async def enrich(self, chunk: Chunk) -> EnrichedChunk:
        summary = await self.llm.agenerate([ENRICHMENT_PROMPT])
        entities = await self.extract_entities(chunk.text)
        metrics = await self.extract_metrics(chunk.text)
        
        return EnrichedChunk(
            **chunk.dict(),
            summary=summary,
            entities=entities,
            metrics=metrics,
        )
```

#### Stage 4: Dual Indexing

Chunks are indexed in both vector and lexical stores:

| Index | Use Case | Strengths |
|-------|---------|-----------|
| Qdrant (Vectors) | Semantic similarity | Captures meaning, synonyms |
| BM25 (Postgres FTS) | Exact term matching | Precision, rare terms |

```python
# Dual indexing
async def index_chunk(chunk: EnrichedChunk):
    # Vector indexing
    embedding = await embedding_service.embed(chunk.summary)
    await qdrantClient.upsert(
        collection="chunks",
        points=[PointStruct(
            id=chunk.id,
            vector=embedding,
            payload=chunk.dict(),
        )]
    )
    
    # Lexical indexing
    await postgresClient.execute("""
        INSERT INTO chunk_fts (id, content, document)
        VALUES ($1, $2, $3)
    """, chunk.id, chunk.text, chunk.document_id)
```

### 4.2 Multi-Stage Retrieval Pipeline

The RAG system executes a sophisticated retrieval sequence for every query:

```mermaid
flowchart LR
    Query[User Query] --> Route[Section Routing]
    Route --> Scope[Session Scoping]
    Scope --> Hybrid[Hybrid Search]
    Hybrid --> Vec1[Vector Search]
    Hybrid --> BM251[BM25 Search]
    Vec1 --> RRF[RRF Merger]
    BM251 --> RRF
    RRF --> Rerank[Neural Rerank]
    Rerank --> Gate[Refusal Gate]
    Gate --> Respond[Response]
    Gate --> Refuse[Refusal]
```

#### Stage 1: Section Routing

Predicts relevant document sections to narrow search space:

```python
class SectionRouter:
    """Route queries to relevant document sections."""
    
    async def route(self, query: str, project_id: str) -> list[str]:
        # Get project documents
        docs = await self.get_project_docs(project_id)
        
        # Predict sections
        embeddings = await self.embed([query] + docs)
        similarities = cosine_similarity(embeddings[0], embeddings[1:])
        
        # Return top-k sections
        top_k = docs[np.argsort(similarities)[-5:]]
        return top_k
```

#### Stage 2: Session Scoping

Incorporates conversation history:

```python
class SessionScoper:
    """Incorporate session context into retrieval."""
    
    async def scope_query(
        self,
        query: str,
        session_id: str,
    ) -> ScopedQuery:
        # Get recent messages
        messages = await self.get_messages(session_id, limit=5)
        
        # Extract key topics
        topics = self.extract_topics(messages)
        
        # Boost relevance for same-topic chunks
        query_with_context = f"""
            Query: {query}
            Related to: {', '.join(topics)}
        """
        
        return ScopedQuery(
            text=query_with_context,
            topicWeights=self.compute_topic_weights(topics),
        )
```

#### Stage 3: Hybrid Retrieval

Parallel search across both indices:

```python
class HybridRetriever:
    """Combined vector + lexical search."""
    
    async def retrieve(
        self,
        query: ScopedQuery,
        top_k: int = 20,
    ) -> list[RetrievedChunk]:
        # Vector search
        vector_results = await self.vector_search(
            query.text,
            limit=top_k * 2,
        )
        
        # BM25 search
        bm25_results = await self.bm25_search(
            query.text,
            limit=top_k * 2,
        )
        
        # Apply topic weights
        vector_results = self.apply_weights(
            vector_results, 
            query.topicWeights
        )
        
        # RRF merge
        return self.rrf_merge(vector_results, bm25_results, top_k)
    
    def rrf_merge(
        self,
        vec_results: list,
        bm25_results: list,
        top_k: int,
    ) -> list:
        """Reciprocal Rank Fusion algorithm."""
        scores = defaultdict(float)
        
        for results, k in [(vec_results, 1), (bm25_results, 1)]:
            for rank, item in enumerate(results):
                scores[item.id] += 1.0 / (k * (rank + 60))
        
        sorted_items = sorted(scores.items(), key=lambda x: -x[1])
        return [item for item, _ in sorted_items[:top_k]]
```

#### Stage 4: Neural Reranking

Cross-encoder for final precision:

```python
class NeuralReranker:
    """Cross-encoder reranking."""
    
    async def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
    ) -> list[RerankedChunk]:
        # Create pairs
        pairs = [(query, chunk.text) for chunk in chunks]
        
        # Score with cross-encoder
        scores = await self.cross_encoder.score_pairs(pairs)
        
        # Sort by score
        reranked = sorted(
            zip(chunks, scores),
            key=lambda x: x[1],
            reverse=True,
        )
        
        return [
            RerankedChunk(chunk=chunk, score=score)
            for chunk, score in reranked
        ]
```

#### Stage 5: Refusal Gate

Confidence-based knowledge cutoff:

```python
class RefusalGate:
    """Prevent halucinations with confidence thresholds."""
    
    def __init__(
        self,
        rerank_threshold: float = 0.75,
        use_fallback: bool = True,
    ):
        self.rerank_threshold = rerank_threshold
        self.use_fallback = use_fallback
    
    def evaluate(
        self,
        query: str,
        chunks: list[RerankedChunk],
    ) -> RetrievalResult:
        top_chunk = chunks[0]
        
        if top_chunk.score < self.rerank_threshold:
            if self.use_fallback:
                return RetrievalResult(
                    success=False,
                    refusal_message=(
                        "I don't have enough information "
                        "to answer that accurately."
                    ),
                )
        
        return RetrievalResult(
            success=True,
            chunks=[c.chunk for c in chunks[:5]],
        )
```

### 4.3 Voice Interaction & Barge-In

The voice system provides real-time speech interaction:

```mermaid
sequenceDiagram
    participant User
    participant Client
    participant Server
    participant STT
    participant RAG
    participant TTS
    
    User->>Client: Start Speaking
    Client->>Client: Stream Audio
    Client->>Server: Audio Stream
    Server->>STT: Forward Audio
    STT-->>Server: Transcription
    Server->>RAG: Send Query
    RAG-->>Server: Response
    Server->>TTS: Text to Speech
    TTS-->>Server: Audio
    Server->>Client: Stream Audio
    Client->>User: Play Audio
    
    Note over User,Server: Barge-In Scenario
    User->>Client: Interrupt
    Client->>Server: interrupt signal
    Server->>TTS: Stop playback
    Server->>Client: Clear buffer
    Client->>User: Ready for input
```

#### Real-Time STT Configuration

```python
# Whisper STT configuration
STT_CONFIG = {
    "model": "base",  # tiny, base, small, medium, large
    "language": "en",
    "task": "transcribe",
    "beam_size": 5,
    "vad_filter": True,
    "initial_prompt": "Financial report analysis",
}

# Streaming configuration
STREAMING_CONFIG = {
    "sample_rate": 16000,
    "chunk_duration_ms": 100,
    "silence_threshold": 0.01,
    "silence_duration_ms": 800,  # trigger on 800ms silence
    "max_duration_ms": 30000,
}
```

#### TTS Configuration

```python
# Text-to-Speech configuration
TTS_CONFIG = {
    "engine": "gtts",  # gtts, edge-tts
    "language": "en",
    "speed": 1.0,
    "pitch": 0,
}

# Edge-TTS voices
EDGE_TTS_VOICES = {
    "female": "en-US-JennyNeural",
    "male": "en-US-GuyNeural",
}
```

#### Barge-In Implementation

```python
class VoiceController:
    """Manage voice interaction with barge-in."""
    
    def __init__(self):
        self.is_speaking = False
        self.is_listening = False
        self.interrupt_flag = False
    
    async def handle_interrupt(self):
        """Handle user interruption."""
        self.interrupt_flag = True
        
        # Stop TTS playback
        await self.tts.stop()
        
        # Clear audio buffer
        self.audio_buffer.clear()
        
        # Reset state
        self.is_speaking = False
        self.is_listening = True
        
        # Signal client to resume
        await self.ws.send({
            "type": "status",
            "listening": True,
        })
```

### 4.4 Automated RAG Evaluation

The evaluation framework ensures continuous quality:

```mermaid
flowchart TD
    Generate[Generate Test Questions] --> Sample[Sampling]
    Sample --> Retrieve[Run RAG Pipeline]
    Retrieve --> Judge[LLM-as-Judge]
    Judge --> Score[Calculate Scores]
    Score --> Metrics[Aggregate Metrics]
```

#### Evaluation Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| Faithfulness | Response matches retrieved context | > 0.80 |
| Answer Relevancy | Response addresses query | > 0.75 |
| Context Relevancy | Retrieved context relevant | > 0.70 |
| Hit Rate | Top-1 contains answer | > 0.80 |
| Recall@K | Answer in top-K | > 0.75 @ K=5 |
| MRR | Mean Reciprocal Rank | > 0.80 |

#### LLM-as-Judge Prompts

```python
FAITHFULNESS_PROMPT = """
You are an expert evaluator. Given a question, retrieved context, and answer,
evaluate whether the answer is faithful (supported by) the context.

Question: {question}
Context: {context}
Answer: {answer}

Is the answer supported by the context? Rate from 0-1:
"""

ANSWER_RELEVANCY_PROMPT = """
Given a question and answer, evaluate how well the answer addresses the question.

Question: {question}
Answer: {answer}

How well does the answer address the question? Rate from 0-1:
"""
```

---

## 5. Project Structure

```
ps2_hydra/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py          # Authentication endpoints
│   │   │   ├── chat.py        # Chat & query endpoints
│   │   │   ├── voice.py      # Voice interaction
│   │   │   ├── projects.py   # Project CRUD
│   │   │   ├── files.py     # File management
│   │   │   └── evaluation.py # RAG evaluation
│   │   ├── ingestion/
│   │   │   ├── __init__.py
│   │   │   ├── parser.py      # Docling wrapper
│   │   │   ├── chunker.py    # Structural chunking
│   │   │   ├── enricher.py  # LLM enrichment
│   │   │   └── indexer.py   # Dual indexing
│   │   ├── retrieval/
│   │   │   ├── __init__.py
│   │   │   ├── router.py      # Section routing
│   │   │   ├── hybrid.py     # Hybrid search
│   │   │   ├── reranker.py   # Neural reranking
│   │   │   └── refusal.py   # Refusal gates
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── user.py       # User model
│   │   │   ├── project.py   # Project model
│   │   │   ├── file.py      # File model
│   │   │   ├── message.py   # Chat message model
│   │   │   └── chunk.py   # Chunk model
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── chat.py      # Chat business logic
│   │   │   ├── project.py  # Project business logic
│   │   │   ├── voice.py    # Voice handling
│   │   │   └── eval.py     # Evaluation logic
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py    # Configuration
│   │   │   ├── database.py # DB connection
│   │   │   ├── llm.py     # LLM clients
│   │   │   └── voice.py   # Voice utilities
│   │   ├── main.py          # FastAPI application
│   │   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   └── api/
│   │   ├── components/
│   │   │   ├── chat/
│   │   │   │   ├── ChatWindow.tsx
│   │   │   │   ├── MessageBubble.tsx
│   │   │   │   ├── CitationBadge.tsx
│   │   │   │   ├── GenUIRouter.tsx
│   │   │   │   └── VoiceInput.tsx
│   │   │   └── doc-explorer/
│   │   │       ├── PDFViewer.tsx
│   │   │       └── CitationOverlay.tsx
│   │   ├── lib/
│   │   │   ├── api.ts       # API client
│   │   │   ├── socket.ts   # WebSocket
│   │   │   └── sse.ts      # SSE handler
│   │   ├── hooks/
│   │   │   ├── useChat.ts
│   │   │   ├── useVoice.ts
│   │   │   └── useIngestionStatus.ts
│   │   └── types/
│   │       └── index.ts
│   ├── package.json
│   └── tsconfig.json
├── docker-compose.yml           # Full system stack
├── docker-compose.infra.yml # Infrastructure only
└── start-local.ps1          # Windows startup script
```

---

## 6. Configuration & Environment

### 6.1 Environment Variables

#### Backend Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string |
| `REDIS_URL` | Yes | - | Redis connection string |
| `QDRANT_URL` | Yes | - | Qdrant server URL |
| `SECRET_KEY` | Yes | - | JWT signing secret |
| `ALGORITHM` | Yes | HS256 | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | 30 | Token expiry time |
| `GOOGLE_API_KEY` | Yes | - | Gemini API key |
| `GROQ_API_KEY` | Yes | - | Groq API key |
| `UPLOAD_DIR` | No | ./uploads | File upload directory |
| `CELERY_BROKER_URL` | No | - | Redis broker URL |
| `CELERY_RESULT_BACKEND` | No | - | Redis result backend |

#### Frontend Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | Yes | http://localhost:8000 | Backend API URL |
| `NEXT_PUBLIC_WS_URL` | Yes | ws://localhost:8000 | WebSocket URL |

### 6.2 Configuration Files

#### backend/app/core/config.py

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Database
    database_url: str
    redis_url: str
    qdrant_url: str
    
    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # AI Services
    google_api_key: str
    groq_api_key: str
    
    # Storage
    upload_dir: str = "./uploads"
    max_file_size_mb: int = 50
    
    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"
    
    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
```

### 6.3 Docker Configuration

#### docker-compose.infra.yml

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: finsight
      POSTGRES_PASSWORD: finsight123
      POSTGRES_DB: finsight
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  qdrant_data:
  redis_data:
```

---

## 7. Security & Authentication

### 7.1 JWT Authentication

The system uses JWT tokens for stateless authentication:

```python
# Token generation
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(
        to_encode,
        settings.secret_key,
        algorithm=settings.algorithm,
    )
    return encoded_jwt

# Token verification
def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
```

### 7.2 Password Hashing

```python
import bcrypt

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(plain_password: str, hashed: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode(),
        hashed.encode(),
    )
```

### 7.3 User-Project Isolation

Each user can only access their own projects:

```python
def get_user_projects(user_id: str) -> list[Project]:
    return db.query(Project).filter(
        Project.owner_id == user_id
    ).all()

def get_user_project(project_id: str, user_id: str) -> Project:
    project = db.query(Project).filter(
        Project.id == project_id
    ).first()
    
    if project.owner_id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied",
        )
    
    return project
```

### 7.4 API Security Best Practices

- Rate limiting on authentication endpoints
- Input validation with Pydantic schemas
- SQL injection prevention via ORM
- CORS configuration for frontend
- HTTPS enforcement in production

---

## 8. Database Schema

### 8.1 User Model

```python
class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now())
```

### 8.2 Project Model

```python
class Project(Base):
    __tablename__ = "projects"
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    name = Column(String(255), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now())
    
    owner = relationship("User", back_populates="projects")
    files = relationship("File", back_populates="project")
```

### 8.3 File Model

```python
class File(Base):
    __tablename__ = "files"
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"))
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512))
    file_size = Column(Integer)
    file_type = Column(String(50))
    status = Column(Enum(IngestionStatus))
    chunk_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=func.now())
    
    project = relationship("Project", back_populates="files")
    chunks = relationship("Chunk", back_populates="file")
```

### 8.4 Chunk Model

```python
class Chunk(Base):
    __tablename__ = "chunks"
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("files.id"))
    page_number = Column(Integer)
    sequence = Column(Integer)
    content = Column(Text)
    summary = Column(Text)
    embedding = Column(Vector(1536))  # For vector storage
    metadata = Column(JSONB)
    
    file = relationship("File", back_populates="chunks")
```

---

## 9. Voice System Deep Dive

### 9.1 Audio Pipeline

```mermaid
flowchart LR
    Mic[Microphone] --> Encode[Audio Encode]
    Encode --> Streaming[WebSocket Stream]
    Streaming --> Buffer[Audio Buffer]
    Buffer --> VAD[Voice Activity Detection]
    VAD --> Transcribe[Whisper STT]
    Transcribe --> Query[Query RAG]
    Query --> Synth[Speech Synthesis]
    Synth --> Playback[Audio Playback]
```

### 9.2 WebSocket Protocol

```python
# Connection initialization
class VoiceWebSocket:
    """Handle voice WebSocket connections."""
    
    async def connect(self, websocket: WebSocket, token: str):
        await websocket.accept()
        
        # Verify token
        payload = verify_token(token)
        self.user_id = payload["sub"]
        
        # Initialize audio handlers
        self.stt = WhisperSTT()
        self.tts = EdgeTTS()
        self.rag = RAGPipeline()
        
        # Start handlers
        asyncio.create_task(self.handle_audio(websocket))
        asyncio.create_task(self.handle_output(websocket))
```

### 9.3 Silence Detection

```python
class SilenceDetector:
    """Detect speech boundaries."""
    
    def __init__(
        self,
        sample_rate: int = 16000,
        silence_duration: float = 0.8,
        threshold: float = 0.01,
    ):
        self.sample_rate = sample_rate
        self.silence_duration = silence_duration
        self.threshold = threshold
        self.silence_count = 0
    
    def process(self, audio_chunk: bytes) -> bool:
        """Return True if speech ended."""
        # Calculate RMS energy
        samples = np.frombuffer(audio_chunk, dtype=np.int16)
        energy = np.sqrt(np.mean(samples ** 2)) / 32768
        
        if energy < self.threshold:
            self.silence_count += len(audio_chunk) / self.sample_rate
        else:
            self.silence_count = 0
        
        return self.silence_count >= self.silence_duration
```

---

## 10. Evaluation Framework

### 10.1 Generating Test Questions

```python
class QuestionGenerator:
    """Generate test questions from documents."""
    
    async def generate(
        self,
        chunks: list[Chunk],
        num_questions: int = 5,
    ) -> list[str]:
        prompt = f"""
        Based on the following information, generate 
        {num_questions} questions that this information 
        could answer:
        
        {chr(10).join([c.summary for c in chunks])}
        """
        
        response = await self.llm.agenerate(prompt)
        questions = self.parse_questions(response)
        return questions
```

### 10.2 Running Evaluation

```python
async def evaluate_project(project_id: str, num_samples: int = 20):
    # Get random chunks
    chunks = await get_random_chunks(project_id, num_samples)
    
    # Generate questions
    questions = await question_generator.generate(chunks)
    
    results = []
    for question in questions:
        # Run RAG pipeline
        response = await rag_pipeline.query(question)
        
        # Get relevant chunks
        retrieved = [c.text for c in response.chunks]
        
        # Evaluate with LLM-as-judge
        faithfulness = await judge.evaluate_faithfulness(
            question, retrieved, response.text
        )
        answer_relevancy = await judge.evaluate_answer_relevancy(
            question, response.text
        )
        context_relevancy = await judge.evaluate_context_relevancy(
            question, retrieved
        )
        
        results.append({
            "question": question,
            "response": response.text,
            "faithfulness": faithfulness,
            "answer_relevancy": answer_relevancy,
            "context_relevancy": context_relevancy,
        })
    
    return aggregate_results(results)
```

---

## 11. Deployment & Development

### 11.1 Local Development (Windows)

Run the startup script:

```powershell
.\start-local.ps1
```

This script will:
1. Verify Python 3.11+ and Node.js 20+ are installed
2. Start infrastructure containers (PostgreSQL, Redis, Qdrant)
3. Install Python dependencies
4. Install Node.js dependencies
5. Initialize the database
6. Start the FastAPI backend
7. Start the Celery worker
8. Start the Next.js frontend

### 11.2 Manual Startup

```bash
# Terminal 1: Infrastructure
docker-compose -f docker-compose.infra.yml up -d

# Terminal 2: Backend
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 3: Celery Worker
cd backend
celery -A app.core.celery worker --loglevel=info --pool=solo

# Terminal 4: Frontend
cd frontend
npm run dev
```

### 11.3 Production Deployment

```yaml
# docker-compose.yml
version: '3.8'

services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/finsight
      - REDIS_URL=redis://redis:6379
    depends_on:
      - postgres
      - redis
      - qdrant

  celery:
    build: ./backend
    command: celery -A app.core.celery worker
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
    depends_on:
      - redis

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    depends_on:
      - backend
```

---

## 12. Troubleshooting & FAQs

### 12.1 Common Issues

#### Issue: "Connection refused to PostgreSQL"

**Solution:**
1. Ensure PostgreSQL container is running: `docker ps`
2. Check logs: `docker logs postgres`
3. Verify connection string in `.env`
4. Wait for database initialization (first start takes 30s)

#### Issue: "File upload fails with 413"

**Solution:**
1. Check `max_file_size_mb` in config
2. Verify Nginx/client upload limits
3. Check disk space on upload directory

#### Issue: "Voice transcription is slow"

**Solution:**
1. Use smaller Whisper model: `base` instead of `large`
2. Check network latency to STT service
3. Increase silence detection duration

#### Issue: "RAG returns no results"

**Solution:**
1. Verify documents are indexed: GET /api/files
2. Check chunk status is "completed"
3. Test embedding API directly
4. Verify Qdrant collection exists

### 12.2 Performance Tuning

| Component | Parameter | Default | Optimization |
|-----------|------------|---------|--------------|
| Retrieval | top_k | 20 | Increase for recall |
| Retrieval | rerank_top | 10 | Decrease for speed |
| Embedding | batch_size | 100 | Increase for throughput |
| Celery | concurrency | 4 | Increase for parallel processing |
| PostgreSQL | pool_size | 20 | Match concurrent requests |

### 12.3 FAQ

**Q: Can I use my own LLM provider?**
A: Currently, only Google Gemini and Groq are supported. The modular architecture allows adding new providers in `app/core/llm.py`.

**Q: How do I add custom evaluation metrics?**
A: Implement new judge classes in `app/services/eval.py` and register them in the evaluation endpoint.

**Q: Can I use S3 instead of local storage?**
A: Yes, configure `S3_BUCKET` and AWS credentials in settings.

**Q: How do I contribute to FinSight AI?**
A: Follow the contribution guidelines in CONTRIBUTING.md.

---

## Appendix A: API Response Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 422 | Validation Error |
| 429 | Rate Limited |
| 500 | Internal Error |

## Appendix B: Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2024-01-15 | Initial release |
| 1.1.0 | 2024-02-01 | Voice support added |
| 1.2.0 | 2024-03-15 | Evaluation framework |

---

*Last updated: 2026-05-09*