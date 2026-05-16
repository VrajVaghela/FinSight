# app/services/chat_service.py
"""
FinSight AI — ChatService (Simplified RAG Pipeline)
Direct Qdrant retrieval + Gemini generation via OpenAI-compatible API.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
import uuid
import time
import os
import asyncio
import json
import re
from typing import Any, AsyncGenerator
from uuid import UUID

from app.models.orm import Conversation, Message, File
from app.core.streaming import SSEFormatter
from app.core.llm_client import create_chat_completion
from app.config import settings


class ChatService:
    def __init__(
        self,
        db: AsyncSession,
        llm_client: Any = None,
        redis_client: Redis = None,
        openai_client: Any = None,
    ):
        llm_client = llm_client or openai_client
        self.db = db
        self.client = llm_client
        self.redis = redis_client
        self.generation_model = settings.generation_model
        self.sse = SSEFormatter()
        self._qdrant = None
        self._embedder = None

    def _get_qdrant(self):
        """Lazy-load Qdrant client."""
        if self._qdrant is None:
            from qdrant_client import QdrantClient
            self._qdrant = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                check_compatibility=False,
            )
        return self._qdrant

    _global_embedder = None

    def _get_embedder(self):
        """Lazy-load local sentence-transformers embedding model as a class-level singleton."""
        if ChatService._global_embedder is None:
            import os
            os.environ["TOKENIZERS_PARALLELISM"] = "false"
            os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
            from sentence_transformers import SentenceTransformer
            ChatService._global_embedder = SentenceTransformer("all-MiniLM-L6-v2")
        return ChatService._global_embedder

    async def _embed_query(self, query: str) -> list[float]:
        """Get embedding vector for a query string using local model."""
        model = self._get_embedder()
        embedding = await asyncio.to_thread(model.encode, query)
        return embedding.tolist()

    async def _retrieve_chunks(self, query: str, project_id: str, top_k: int = 10) -> list[dict]:
        """
        Retrieve relevant chunks from Qdrant using dense vector search.
        Returns list of dicts with chunk metadata.
        """
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        # 1. Embed the query
        query_vector = await self._embed_query(query)

        # 2. Search Qdrant (using query_points for qdrant-client >= 1.17)
        qdrant = self._get_qdrant()
        query_filter = Filter(
            must=[FieldCondition(key="project_id", match=MatchValue(value=project_id))]
        )

        response = await asyncio.to_thread(
            qdrant.query_points,
            collection_name=settings.qdrant_collection,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            with_payload=True,
        )
        results = response.points

        chunks = []
        for hit in results:
            payload = hit.payload or {}
            chunks.append({
                "chunk_id": payload.get("chunk_id", str(hit.id)),
                "raw_text": payload.get("raw_text", payload.get("enriched_text", "")),
                "page_number": payload.get("page_number", 0),
                "section_header": payload.get("section_header", ""),
                "score": float(hit.score),
                "is_table": payload.get("is_table", False),
                "table_html": payload.get("table_html", ""),
                "file_id": payload.get("file_id", ""),
            })

        return chunks

    async def process_chat(
        self,
        project_id: uuid.UUID,
        message: str,
        user_id: UUID,
        conversation_id: uuid.UUID = None,
        language: str = "auto",
        voice: bool = False,
        debug: bool = False
    ) -> AsyncGenerator[str, None]:
        start_time = time.time()

        # 1. Setup conversation
        if not conversation_id:
            # Auto-title from the first message
            title = message[:60].strip()
            if len(message) > 60:
                title += "…"
            conversation = Conversation(project_id=project_id, user_id=user_id, title=title)
            self.db.add(conversation)
            await self.db.commit()
            await self.db.refresh(conversation)
            conversation_id = conversation.id

        # 2. Get history
        from sqlalchemy import select
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(settings.chat_history_limit)
        )
        result = await self.db.execute(stmt)
        history = [{"role": m.role, "content": m.content} for m in reversed(result.scalars().all())]

        # 3. Retrieve relevant chunks
        yield self.sse.format_event("status", {"message": "Searching document..."})

        try:
            retrieved_chunks = await self._retrieve_chunks(message, str(project_id), top_k=10)
        except Exception as e:
            print(f"[ChatService] Retrieval error: {e}")
            retrieved_chunks = []

        # 4. Check if we have any relevant context
        if not retrieved_chunks:
            yield self.sse.format_event("chunk", {
                "delta": "I could not find relevant information in the uploaded documents to answer your question.",
                "citations": []
            })
            latency_ms = int((time.time() - start_time) * 1000)
            yield self.sse.done(str(conversation_id), total_tokens=0, cached_tokens=0, latency_ms=latency_ms)
            return

        # 5. Debug mode — emit retrieval info
        if debug and retrieved_chunks:
            debug_chunks = [
                {
                    "chunk_id": c["chunk_id"],
                    "score": c["score"],
                    "page_number": c["page_number"],
                    "section_header": c["section_header"],
                    "text_snippet": c["raw_text"],
                    "file_id": c["file_id"],
                    "table_html": c.get("table_html", ""),
                }
                for c in retrieved_chunks
            ]
            yield self.sse.retrieval_debug(debug_chunks)

        # 6. Build context from retrieved chunks with citations
        context_parts = []
        for i, chunk in enumerate(retrieved_chunks):
            citation_marker = chunk["chunk_id"]  # e.g., p3:c2
            context_parts.append(
                f"[{citation_marker}] (Page {chunk['page_number']}, Section: {chunk['section_header']})\n"
                f"{chunk['raw_text']}"
            )
        context_text = "\n\n---\n\n".join(context_parts)

        # 7. Build system prompt
        system_prompt = (
            "You are FinSight AI, a document-grounded financial analyst. "
            "Answer questions ONLY using the provided document context. "
            "If the answer is not in the context, say 'This information is not found in the document.' "
            "Always cite your sources using the [pX:cY] markers from the context. "
            "Be precise, factual, and cite specific numbers when available. "
            "IMPORTANT: If the user asks for a plot, chart, graph, or visual representation, DO NOT use Mermaid. "
            "Instead, you MUST output a JSON block for EACH chart requested. "
            "CRITICAL: You MUST wrap each JSON block in strict markdown code blocks exactly like this:\n"
            "```json\n"
            "{\n"
            '  "component": "BarChart",\n'
            '  "data": {\n'
            '    "title": "Your Chart Title",\n'
            '    "labels": ["A", "B", "C"],\n'
            '    "datasets": [{"label": "Metric Name", "values": [10, 20, 30]}]\n'
            "  }\n"
            "}\n"
            "```\n"
            "DO NOT output raw JSON without the ```json wrapper."
        )

        # 8. Stream LLM response
        yield self.sse.format_event("status", {"message": "Generating answer..."})

        messages = [
            {"role": "system", "content": system_prompt},
            *history[-4:],  # Last 4 messages for context
            {"role": "user", "content": f"Document Context:\n{context_text}\n\nQuestion: {message}"}
        ]

        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = await create_chat_completion(
                    self.client,
                    model=self.generation_model,
                    messages=messages,
                    stream=True,
                )

                full_content = ""
                total_tokens = 0
                async for chunk in response:
                    if hasattr(chunk, "usage") and chunk.usage:
                        total_tokens = getattr(chunk.usage, "total_tokens", 0) or 0

                    if chunk.choices:
                        delta = chunk.choices[0].delta
                        if hasattr(delta, "content") and delta.content:
                            full_content += delta.content
                            yield self.sse.chunk(delta.content)
                break  # Success, exit retry loop

            except Exception as e:
                error_msg = str(e)
                if ("429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg) and attempt < max_retries - 1:
                    wait_time = 35
                    print(f"[ChatService] Rate limited. Waiting {wait_time}s before retry...")
                    yield self.sse.format_event("status", {"message": f"Rate limited. Retrying in {wait_time}s..."})
                    await asyncio.sleep(wait_time)
                    continue
                print(f"[ChatService] LLM error: {error_msg}")
                yield self.sse.chunk(f"Error: {error_msg[:200]}")
                full_content = "Error generating response"
                total_tokens = 0
                break

        # Extract UI components using robust brace counting
        json_blocks = []
        extracted_components = []
        start_idx = 0
        while True:
            # Look for the start of a potential JSON block
            # We look for either ```json {  or just { "component":
            match = re.search(r'```(?:json)?\s*(\{\s*"component"\s*:)|(\{\s*"component"\s*:)', full_content[start_idx:])
            if not match:
                break
                
            # The start of the JSON object itself
            # If match.group(1) exists, it's the start of the object inside a markdown block
            # If match.group(2) exists, it's a raw object
            idx = start_idx + match.start(1 if match.group(1) else 2)
            
            brace_count = 0
            end_idx = -1
            in_string = False
            escape = False
            
            for i in range(idx, len(full_content)):
                char = full_content[i]
                if escape:
                    escape = False
                    continue
                if char == '\\':
                    escape = True
                elif char == '"':
                    in_string = not in_string
                elif not in_string:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            end_idx = i
                            break
            
            if end_idx != -1:
                json_str = full_content[idx:end_idx+1]
                # If it was inside a markdown block, the "full_match" should include the backticks
                # Let's see if we can find them
                before = full_content[max(0, idx-15):idx]
                after = full_content[end_idx+1:end_idx+10]
                
                full_match = json_str
                if "```" in before and "```" in after:
                    # Try to reconstruct the full markdown block for replacement
                    md_start = full_content.rfind("```", 0, idx)
                    md_end = full_content.find("```", end_idx + 1)
                    if md_start != -1 and md_end != -1:
                        full_match = full_content[md_start:md_end+3]
                
                json_blocks.append((full_match, json_str))
                start_idx = max(start_idx + 1, end_idx + 1)
            else:
                break

        for full_match, json_str in json_blocks:
            try:
                ui_data = json.loads(json_str)
                if "component" in ui_data:
                    yield self.sse.format_event("ui_component", ui_data)
                    extracted_components.append(ui_data)
                    full_content = full_content.replace(full_match, "").strip()
            except Exception as e:
                print(f"[ChatService] Failed to parse UI component JSON: {e}")

        # If we have components but no text, add a descriptive prefix
        if extracted_components and not full_content.strip():
            full_content = "I've generated the requested visualization(s) based on your query."
            yield self.sse.chunk(full_content)

        # 9. Emit citation summary
        citation_dicts = [
            {
                "chunk_id": c["chunk_id"],
                "page": c["page_number"],
                "score": c["score"],
                "text_snippet": c["raw_text"][:100],
            }
            for c in retrieved_chunks[:5]
        ]
        yield self.sse.chunk("", citations=citation_dicts)

        # 10. Persist messages
        user_msg = Message(conversation_id=conversation_id, role="user", content=message)
        asst_msg = Message(
            conversation_id=conversation_id, 
            role="assistant", 
            content=full_content,
            citations=citation_dicts,
            ui_components=extracted_components
        )
        self.db.add_all([user_msg, asst_msg])
        await self.db.commit()

        latency_ms = int((time.time() - start_time) * 1000)
        yield self.sse.done(
            str(conversation_id),
            total_tokens=total_tokens,
            cached_tokens=0,
            latency_ms=latency_ms
        )
