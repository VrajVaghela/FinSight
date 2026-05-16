# FinSight AI — Backend Engineer & Infrastructure Lead
# Implementation Plan Part 2: Control Flow, Data Flow & Core Modules

---

## 6. CONTROL FLOW — /api/chat (THE MAIN PIPELINE)

This is the most critical endpoint. You orchestrate the entire query pipeline:

```
POST /api/chat {project_id, conversation_id, message, language, voice, debug}
│
├─ 1. AUTH: Verify JWT → extract user_id
│
├─ 2. CONVERSATION SETUP
│   ├─ If conversation_id is None → create new Conversation in PostgreSQL
│   └─ Save user message to messages table
│
├─ 3. LANGUAGE DETECTION
│   └─ langdetect(message) → iso_code (e.g., "en", "hi", "gu")
│
├─ 4. QUERY REWRITING (memory_manager.py — YOUR MODULE)
│   ├─ Load last N messages from conversation
│   ├─ Call QueryRewriter.rewrite(chat_history, new_message)
│   │   └─ LLM call (GPT-4o-mini): "Rewrite this follow-up as standalone query"
│   └─ Output: standalone_query (string)
│
├─ 5. PROJECT CONTEXT (memory_manager.py — YOUR MODULE)
│   ├─ Load project.system_prompt from PostgreSQL
│   ├─ Load MEM1 state from Redis (compact session state)
│   └─ Build system_message = system_prompt + mem1_state
│
├─ 6. PROMPT CACHE CHECK (prompt_cache.py — YOUR MODULE)
│   ├─ Hash(system_prompt + project core context)
│   ├─ Check cache_entries table: if hit → set cache_control flag
│   └─ Anthropic API: send with cache_control: {type: "ephemeral"}
│
├─ 7. RETRIEVAL (CALL Member 1's retrieval_engine.py)
│   ├─ retriever = HybridRetriever(project_id=project_id)
│   ├─ raw_results = await retriever.search(standalone_query)
│   │   ├─ BM25 sparse search (parallel)
│   │   └─ Qdrant dense search with project_id filter (parallel)
│   ├─ fused = RRFMerger.merge(raw_results, k=60)
│   │
│   ├─ GATE 1: ScoreThresholdGate(fused, threshold=0.5)
│   │   └─ If max(score) < 0.5 → SSE: event:refusal → STOP
│   │
│   ├─ reranked = NeuralReranker.rerank(standalone_query, fused, top_k=10)
│   │
│   ├─ GATE 2: RerankerScoreGate(reranked, threshold=calibrated)
│   │   └─ If max(reranker_score) < threshold → SSE: event:refusal → STOP
│   │
│   ├─ GATE 3: LLMGrader(standalone_query, reranked_chunks)
│   │   └─ GPT-4o-mini → {"relevant": false} → SSE: event:refusal → STOP
│   │
│   └─ If debug=True → SSE: event:retrieval_debug {chunks with scores}
│
├─ 8. SLM COMPRESSION (slm_compressor.py — YOUR MODULE)
│   ├─ For each of top-10 chunks:
│   │   └─ GPT-4o-mini: "Extract only sentences relevant to: {query}"
│   ├─ Output: compressed_context (avg 60-70% reduction)
│   └─ This is CRITICAL for cost — premium LLM sees only relevant content
│
├─ 9. PAL ROUTING (CALL Member 4's reasoning_engine.py)
│   ├─ PALRouter.classify(standalone_query)
│   │   └─ Returns: "calculation" | "narrative"
│   ├─ If "calculation":
│   │   ├─ CodeGenerator.generate(query, compressed_context)
│   │   ├─ ast.parse validation
│   │   ├─ SymbolicExecutor.run(code)
│   │   ├─ SelfCorrectionLoop (up to 3 retries)
│   │   ├─ SSE: event:pal_execution {code, result}
│   │   └─ pal_result injected into generation context
│   └─ If "narrative": skip PAL
│
├─ 10. GENERATION (LLM call — GPT-4o / Claude Sonnet)
│   ├─ Build prompt: system_message + compressed_context + pal_result + query
│   ├─ Stream response via LLM API
│   ├─ For each token chunk:
│   │   └─ SSE: event:chunk {delta, citations[]}
│   └─ Accumulate full response text
│
├─ 11. GATE 4: GLEAN VERIFICATION (CALL Member 4's glean_verifier.py)
│   ├─ GLEANVerifier.verify(response, retrieved_chunks, project_guidelines)
│   ├─ If violation detected:
│   │   ├─ Trigger self-correction (up to 2 retries)
│   │   └─ If still failing → SSE: event:refusal {level_4_postgen}
│   └─ If passes → continue
│
├─ 12. CITATION MAPPING (CALL Member 4's citation_engine.py)
│   ├─ CitationQueryEngine.extract_citations(response)
│   ├─ BoundingBoxMapper.map(citation_chunk_ids)
│   └─ Enriched citations with bounding_box coordinates
│
├─ 13. UI COMPONENT DECISION (YOUR LOGIC)
│   ├─ If query mentions revenue/trend/growth → SSE: event:ui_component {BarChart}
│   ├─ If query mentions comparison/segments → SSE: event:ui_component {DataTable}
│   ├─ If PAL was triggered → SSE: event:ui_component {CodeBlock}
│   └─ Always → SSE: event:ui_component {PDFOverlay, bounding_boxes}
│
├─ 14. PERSIST RESULTS
│   ├─ Save assistant message to PostgreSQL (content, citations, pal, ui_components)
│   ├─ Update MEM1 state in Redis
│   ├─ Update prompt cache hit count
│   └─ SSE: event:done {conversation_id, total_tokens, cached_tokens, latency_ms}
│
└─ 15. VOICE OUTPUT (if voice=True)
    ├─ TTS call: OpenAI TTS API or ElevenLabs
    └─ Stream audio alongside text SSE events
```

---

## 7. CONTROL FLOW — /ws/voice (WEBSOCKET VOICE PIPELINE)

```
Client connects: ws://host/ws/voice?project_id=xxx&conversation_id=xxx&token=jwt
│
├─ 1. Authenticate JWT from query param
├─ 2. Open bidirectional WebSocket
│
├─ RECEIVE LOOP (client → server):
│   ├─ Receive audio chunks (binary, 20-40ms each)
│   ├─ Buffer until silence detection (VAD — Voice Activity Detection)
│   ├─ On silence:
│   │   ├─ Concatenate buffered audio → WAV/webm
│   │   ├─ Whisper API: transcribe(audio, language=detected) → text
│   │   ├─ Send to same chat_service pipeline as /api/chat
│   │   └─ Stream results back as JSON frames on WebSocket
│   └─ On "interrupted" signal from client:
│       └─ Cancel current TTS stream, discard buffer (barge-in)
│
├─ SEND LOOP (server → client):
│   ├─ JSON frame: {type: "transcript", text: "user said..."}
│   ├─ JSON frame: {type: "chunk", delta: "...", citations: [...]}
│   ├─ Binary frames: TTS audio chunks (streaming)
│   ├─ JSON frame: {type: "done", ...}
│   └─ JSON frame: {type: "error", message: "..."}
│
└─ On disconnect: cleanup, persist conversation
```

---

## 8. CORE MODULE: memory_manager.py

```python
# app/core/memory_manager.py
import json
import hashlib
from typing import Optional
from openai import AsyncOpenAI
from redis.asyncio import Redis

class QueryRewriter:
    """Condenses chat history + new question into standalone query."""

    REWRITE_PROMPT = """Given the conversation history and a follow-up question,
rewrite the follow-up as a standalone search query that contains all necessary
context. Do NOT answer the question — only rewrite it.

Chat History:
{history}

Follow-up Question: {question}

Standalone Query:"""

    def __init__(self, llm_client: AsyncOpenAI, model: str = "gpt-4o-mini"):
        self.client = llm_client
        self.model = model

    async def rewrite(self, chat_history: list[dict], new_message: str) -> str:
        if not chat_history:
            return new_message  # First message needs no rewriting

        # Format last 6 messages max (3 turns)
        history_text = "\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in chat_history[-6:]
        )
        prompt = self.REWRITE_PROMPT.format(
            history=history_text, question=new_message
        )
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=200
        )
        return response.choices[0].message.content.strip()


class ProjectMemory:
    """Manages project-level context: system prompt + preferences."""

    def __init__(self, db_session):
        self.db = db_session

    async def get_system_prompt(self, project_id: str) -> str:
        from app.models.orm import Project
        project = await self.db.get(Project, project_id)
        return project.system_prompt if project else ""

    def build_system_message(self, system_prompt: str, mem1_state: str = "") -> str:
        parts = []
        parts.append("You are FinSight AI, a financial document analysis assistant.")
        parts.append("CRITICAL: Only answer from the provided document context.")
        parts.append("If information is not in the context, say 'Not found in the document.'")
        parts.append("Always cite sources with [Source N, pX] format.")
        if system_prompt:
            parts.append(f"\nProject Instructions:\n{system_prompt}")
        if mem1_state:
            parts.append(f"\nSession State:\n{mem1_state}")
        return "\n".join(parts)


class MEM1Adapter:
    """Compact dynamic state management for long multi-turn sessions.

    Based on MEM1 (NeurIPS 2025): instead of passing full chat history,
    maintain a compact state summary that captures key information
    from the conversation. Updated after each turn via LLM.
    """

    STATE_UPDATE_PROMPT = """You maintain a compact session state for a financial AI.
Current state: {current_state}
Latest exchange - User: {user_msg} | Assistant: {assistant_msg}

Update the state to include any new key facts, entities, or context needed
for future questions. Keep it under 200 tokens. Output ONLY the updated state."""

    def __init__(self, redis: Redis, llm_client: AsyncOpenAI, model: str = "gpt-4o-mini"):
        self.redis = redis
        self.client = llm_client
        self.model = model
        self.ttl = 3600  # 1 hour session TTL

    def _key(self, conversation_id: str) -> str:
        return f"mem1:{conversation_id}"

    async def get_state(self, conversation_id: str) -> str:
        state = await self.redis.get(self._key(conversation_id))
        return state.decode() if state else ""

    async def update_state(
        self, conversation_id: str,
        user_msg: str, assistant_msg: str
    ):
        current = await self.get_state(conversation_id)
        prompt = self.STATE_UPDATE_PROMPT.format(
            current_state=current or "(empty)",
            user_msg=user_msg,
            assistant_msg=assistant_msg[:500]  # Truncate long responses
        )
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=250
        )
        new_state = response.choices[0].message.content.strip()
        await self.redis.setex(
            self._key(conversation_id), self.ttl, new_state
        )
        return new_state
```

---

## 9. CORE MODULE: slm_compressor.py

```python
# app/core/slm_compressor.py
from openai import AsyncOpenAI

class SLMCompressor:
    """Contextual compression using GPT-4o-mini.

    Before sending retrieved chunks to the premium LLM (GPT-4o/Claude),
    this module strips irrelevant sentences, achieving ~65% context reduction.
    This is NOT naive stop-word removal — it's query-aware extraction.
    """

    COMPRESS_PROMPT = """Given the user's question and a document chunk,
extract ONLY the sentences that are directly relevant to answering the question.
Preserve exact numbers, dates, and financial metrics verbatim.
Do NOT paraphrase or summarize — extract sentences as-is.
If nothing is relevant, output "IRRELEVANT".

Question: {query}

Document Chunk:
{chunk_text}

Relevant Sentences:"""

    def __init__(self, llm_client: AsyncOpenAI, model: str = "gpt-4o-mini"):
        self.client = llm_client
        self.model = model

    async def compress_chunks(
        self, query: str, chunks: list[dict]
    ) -> list[dict]:
        """Compress each chunk, removing irrelevant content."""
        import asyncio

        async def compress_one(chunk: dict) -> dict | None:
            prompt = self.COMPRESS_PROMPT.format(
                query=query, chunk_text=chunk["raw_text"]
            )
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=500
            )
            compressed = response.choices[0].message.content.strip()
            if compressed == "IRRELEVANT":
                return None
            return {**chunk, "raw_text": compressed}

        results = await asyncio.gather(
            *[compress_one(c) for c in chunks],
            return_exceptions=True
        )
        return [r for r in results if r is not None and not isinstance(r, Exception)]
```

---

## 10. CORE MODULE: prompt_cache.py

```python
# app/core/prompt_cache.py
import hashlib
from datetime import datetime, timedelta

class AnthropicPromptCache:
    """Implements Anthropic-style prompt caching for cost reduction.

    Caches the project system prompt + core document context as a prefix.
    On follow-up turns within same project, the cached prefix saves ~80%
    token cost since Anthropic charges 10% for cached input tokens.
    """

    def __init__(self, db_session):
        self.db = db_session

    def compute_prefix_hash(self, system_prompt: str, core_context: str) -> str:
        content = f"{system_prompt}||{core_context}"
        return hashlib.sha256(content.encode()).hexdigest()

    async def get_or_create_cache(self, project_id: str, system_prompt: str,
                                   core_context: str) -> dict:
        prefix_hash = self.compute_prefix_hash(system_prompt, core_context)

        from app.models.orm import CacheEntry
        from sqlalchemy import select
        stmt = select(CacheEntry).where(CacheEntry.prefix_hash == prefix_hash)
        result = await self.db.execute(stmt)
        entry = result.scalar_one_or_none()

        if entry and entry.expiry > datetime.utcnow():
            entry.hit_count += 1
            entry.expiry = datetime.utcnow() + timedelta(minutes=5)  # Extend TTL
            await self.db.commit()
            return {"cached": True, "cache_control": {"type": "ephemeral"}}

        # Create new cache entry
        new_entry = CacheEntry(
            prefix_hash=prefix_hash,
            project_id=project_id,
            expiry=datetime.utcnow() + timedelta(minutes=5)
        )
        self.db.add(new_entry)
        await self.db.commit()
        return {"cached": False, "cache_control": {"type": "ephemeral"}}

    def build_cached_messages(self, system_prompt: str, core_context: str,
                               cache_info: dict) -> list[dict]:
        """Build message list with cache_control markers for Anthropic API."""
        messages = []
        # System message with cache control
        system_content = [
            {"type": "text", "text": system_prompt},
            {"type": "text", "text": core_context,
             "cache_control": cache_info["cache_control"]}
        ]
        return system_content
```

---

## 11. CORE MODULE: streaming.py

```python
# app/core/streaming.py
import json
from typing import AsyncGenerator

class SSEFormatter:
    """Formats events for Server-Sent Events streaming."""

    @staticmethod
    def format_event(event_type: str, data: dict) -> str:
        json_data = json.dumps(data, default=str)
        return f"event: {event_type}\ndata: {json_data}\n\n"

    @staticmethod
    def chunk(delta: str, citations: list = None) -> str:
        return SSEFormatter.format_event("chunk", {
            "delta": delta,
            "citations": citations or []
        })

    @staticmethod
    def retrieval_debug(chunks: list) -> str:
        return SSEFormatter.format_event("retrieval_debug", {"chunks": chunks})

    @staticmethod
    def ui_component(component: str, data: dict) -> str:
        return SSEFormatter.format_event("ui_component", {
            "component": component, "data": data
        })

    @staticmethod
    def refusal(reason: str, message: str = "Not found in the document.") -> str:
        return SSEFormatter.format_event("refusal", {
            "reason": reason, "message": message
        })

    @staticmethod
    def pal_execution(code: str, result: str) -> str:
        return SSEFormatter.format_event("pal_execution", {
            "code": code, "result": result
        })

    @staticmethod
    def done(conversation_id: str, total_tokens: int,
             cached_tokens: int, latency_ms: int) -> str:
        return SSEFormatter.format_event("done", {
            "conversation_id": str(conversation_id),
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
            "latency_ms": latency_ms
        })
```

---

*Continued in Part 3: Integration Contracts, Endpoints, Dockerfile & Step-by-Step Checkpoints*
