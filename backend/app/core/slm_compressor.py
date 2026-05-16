# app/core/slm_compressor.py
import os
from typing import Any

from app.config import settings
from app.core.llm_client import create_chat_completion

class SLMCompressor:
    """Contextual compression using the configured utility LLM."""

    COMPRESS_PROMPT = """Given the user's question and a document chunk,
extract ONLY the sentences that are directly relevant to answering the question.
Preserve exact numbers, dates, and financial metrics verbatim.
Do NOT paraphrase or summarize — extract sentences as-is.
If nothing is relevant, output "IRRELEVANT".

Question: {query}

Document Chunk:
{chunk_text}

Relevant Sentences:"""

    def __init__(self, llm_client: Any, model: str = None):
        self.client = llm_client
        self.model = model or os.getenv("UTILITY_MODEL", settings.utility_model)

    async def compress_chunks(self, query: str, chunks: list[dict]) -> list[dict]:
        """Compress each chunk, removing irrelevant content."""
        import asyncio

        async def compress_one(chunk: dict) -> dict | None:
            # We assume chunk has "raw_text"
            text = chunk.get("raw_text", "")
            if not text:
                return None
                
            prompt = self.COMPRESS_PROMPT.format(
                query=query, chunk_text=text
            )
            response = await create_chat_completion(
                self.client,
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=500
            )
            compressed = response.choices[0].message.content.strip()
            if compressed == "IRRELEVANT":
                return None
            
            new_chunk = dict(chunk)
            new_chunk["raw_text"] = compressed
            return new_chunk

        results = await asyncio.gather(
            *[compress_one(c) for c in chunks],
            return_exceptions=True
        )
        return [r for r in results if r is not None and not isinstance(r, Exception)]
