"""
FinSight AI — ContextualEnricher
Calls Gemini utility models to:
  1. Generate a 50-100 token context summary prepended to each chunk
  2. For tables: Extract JSON key-value pairs for PAL engine
"""
import os
import json
from typing import List, Optional


class ContextualEnricher:
    """
    Enriches chunks with LLM-generated context summaries and table KV extraction.
    Uses Google Gemini utility models.
    Gracefully degrades: if LLM call fails, the chunk keeps its raw_text without summary.
    """

    def __init__(self, doc_title: str = "Financial Document", doc_date: str = "Unknown"):
        self.doc_title = doc_title
        self.doc_date = doc_date
        self._client = None
        self._model_name = os.getenv("UTILITY_MODEL", "gemini-2.5-flash-lite")

    def _get_client(self):
        """Lazy-load Gemini client."""
        if self._client is None:
            from google import genai

            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY not set in environment")
            self._client = genai.Client(api_key=api_key)
            print(f"[ContextualEnricher] Gemini model ready: {self._model_name}")
        return self._client

    def _generate_text(self, contents, max_output_tokens: int) -> str:
        """Generate text through the Google GenAI SDK."""
        from google.genai import types

        response = self._get_client().models.generate_content(
            model=self._model_name,
            contents=contents,
            config=types.GenerateContentConfig(
                max_output_tokens=max_output_tokens,
                temperature=0.0,
            ),
        )
        return (getattr(response, "text", "") or "").strip()

    def enrich_chunks(self, chunks: list) -> list:
        """
        Enrich a list of FinalChunk objects:
        - Generate context_summary for every chunk
        - Extract table_kv for table chunks
        - Set enriched_text = context_summary + "\\n\\n" + raw_text
        
        Args:
            chunks: List of FinalChunk objects from MetadataExtractor
            
        Returns:
            The same list, mutated in-place with enriched fields.
        """
        for i, chunk in enumerate(chunks):
            print(f"[ContextualEnricher] Enriching chunk {i+1}/{len(chunks)} "
                  f"(section: {chunk.section_header[:40]})")
            
            # 0. Zero-Trust PII Redaction
            chunk.raw_text = self._redact_pii(chunk.raw_text)
            
            # 1. Generate context summary
            summary = self._generate_summary(chunk)
            
            if summary:
                chunk.context_summary = summary
                chunk.enriched_text = f"{summary}\n\n{chunk.raw_text}"
            else:
                chunk.enriched_text = chunk.raw_text

            # 2. For tables: extract key-value pairs for PAL engine
            if chunk.is_table and chunk.table_html:
                kv = self._extract_table_kv(chunk)
                if kv:
                    chunk.table_kv = kv

            # 3. For images: extract visual description using Gemini Vision
            if chunk.is_image and getattr(chunk, "image_path", None) and os.path.exists(chunk.image_path):
                desc = self._extract_image_description(chunk)
                if desc:
                    chunk.image_description = desc
                    # Prepend the description to raw_text so BM25 indexes it too
                    chunk.raw_text = f"[Image Description: {desc}]\n\n{chunk.raw_text}"
                    # Re-generate enriched_text with the new raw_text
                    if summary:
                        chunk.enriched_text = f"{summary}\n\n{chunk.raw_text}"
                    else:
                        chunk.enriched_text = chunk.raw_text

        enriched_count = sum(1 for c in chunks if c.context_summary)
        kv_count = sum(1 for c in chunks if c.table_kv)
        image_count = sum(1 for c in chunks if getattr(c, "image_description", None))
        print(f"[ContextualEnricher] Done: {enriched_count}/{len(chunks)} summaries, "
              f"{kv_count} table KVs, {image_count} image descriptions extracted")
        return chunks

    def _redact_pii(self, text: str) -> str:
        """Zero-Trust PII Redaction: Masks SSNs, Emails, and Phone numbers before embedding."""
        import re
        if os.getenv("ENABLE_PII_REDACTION", "true").lower() != "true":
            return text
        
        # Mask SSN
        text = re.sub(r'\b\d{3}-\d{2}-\d{4}\b', '[REDACTED_SSN]', text)
        # Mask Email
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[REDACTED_EMAIL]', text)
        # Mask Phone Numbers (simple format)
        text = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[REDACTED_PHONE]', text)
        
        return text

    def _generate_summary(self, chunk) -> Optional[str]:
        """
        Call Gemini to generate a 50-100 token context summary for a chunk.
        Returns the summary string, or None on failure.
        """
        prompt = f"""You are a document indexing assistant. Write a concise context summary (50-100 tokens) 
for the following chunk from a financial document.

Document Title: {self.doc_title}
Document Date: {self.doc_date}
Section: {chunk.section_header}
Page: {chunk.page_number}
Chunk Type: {"Table" if chunk.is_table else "Text"}

Chunk Content (first 500 chars):
{chunk.raw_text[:500]}

Write ONLY the summary. Start with the document title and date. Include the section name.
Example: "From Adani Enterprises Q2 FY26 Earnings Report (Oct 2025), under 'Revenue Breakdown' section, this chunk discusses..."
"""
        try:
            return self._generate_text(prompt, max_output_tokens=150)
        except Exception as e:
            print(f"[ContextualEnricher] Warning: Summary generation failed: {e}")
            return None

    def _extract_table_kv(self, chunk) -> Optional[dict]:
        """
        Call Gemini to extract clean key-value pairs from a table's HTML.
        Returns a dict like {"Net Income": "500M", "Revenue": "1.2B"}, or None on failure.
        
        These KV pairs are used by Member 4's PAL engine for calculations.
        """
        prompt = f"""You are a financial data extraction assistant. Extract all key-value pairs from this HTML table.

Table HTML:
{chunk.table_html[:2000]}

Return a JSON object where keys are metric names and values are the corresponding numbers/values.
Include units where present. For multi-period tables, use format "Metric (Period)": "Value".

Example output:
{{"Total Revenue (Q2 FY26)": "₹23,532 Cr", "Net Profit (Q2 FY26)": "₹1,742 Cr", "EBITDA Margin": "12.5%"}}

Return ONLY valid JSON, no markdown, no explanation.
"""
        try:
            raw = self._generate_text(prompt, max_output_tokens=500)
            # Clean markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
                raw = raw.rsplit("```", 1)[0]
            return json.loads(raw)
        except json.JSONDecodeError:
            print(f"[ContextualEnricher] Warning: Table KV extraction returned invalid JSON")
            return None
        except Exception as e:
            print(f"[ContextualEnricher] Warning: Table KV extraction failed: {e}")
            return None

    def _extract_image_description(self, chunk) -> Optional[str]:
        """
        Call Gemini Vision to describe an image/chart.
        Returns the description string, or None on failure.
        """
        prompt = f"""You are a financial analyst assistant. Describe this image/chart from a financial document in detail.
If it is a chart, extract the key trends, numbers, and takeaways.
If it is a diagram or infographic, explain what it shows.

Document Section: {chunk.section_header}
Caption/Text nearby: {chunk.raw_text}

Provide a clear, factual description without markdown formatting.
"""
        try:
            uploaded = self._get_client().files.upload(file=chunk.image_path)
            return self._generate_text([prompt, uploaded], max_output_tokens=300)
        except Exception as e:
            print(f"[ContextualEnricher] Warning: Image description failed for {chunk.image_path}: {e}")
            return None
