"""
FinSight AI — MetadataExtractor
Assigns UUIDs, sequential chunk_index, bounding boxes, project/file IDs,
and token counts to every chunk. Produces FinalChunk objects.
"""
import uuid
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class FinalChunk:
    """The core output object of the ingestion pipeline.
    Every downstream component reads this shape."""
    chunk_id: str                           # UUID string — same as Qdrant point ID
    chunk_index: int                        # Sequential order in document
    project_id: str                         # For isolation — MUST be on every chunk
    file_id: str                            # Which file this chunk came from
    page_number: int                        # Page of first element (1-indexed)
    section_header: str                     # Nearest H1/H2 ancestor text
    raw_text: str                           # Original chunk text (BM25 + UI)
    context_summary: str = ""               # LLM-generated prefix (filled by Enricher)
    enriched_text: str = ""                 # context_summary + "\n\n" + raw_text
    bounding_box: Optional[dict] = None     # {x, y, w, h} normalized 0.0–1.0
    token_count: int = 0                    # tiktoken count of raw_text
    is_table: bool = False
    table_html: Optional[str] = None        # HTML serialization of table
    table_kv: Optional[dict] = None         # Key-value pairs extracted from table (for PAL)
    is_image: bool = False                  # True if chunk is a figure/chart/image
    image_path: Optional[str] = None        # Path to saved image file
    image_description: Optional[str] = None # Gemini Vision description of the image


class MetadataExtractor:
    """
    Takes RawChunks from the StructuralChunker and produces FinalChunks
    with full metadata: UUID, chunk_index, project_id, file_id, bounding_box, token_count.
    """

    def extract(
        self,
        raw_chunks: list,
        project_id: str,
        file_id: str,
    ) -> List[FinalChunk]:
        """
        Enrich raw chunks with metadata.
        
        Args:
            raw_chunks: List of RawChunk from StructuralChunker
            project_id: UUID string for project isolation
            file_id: UUID string for the source file
            
        Returns:
            List[FinalChunk] with all metadata populated.
        """
        final_chunks = []

        for idx, raw_chunk in enumerate(raw_chunks):
            chunk_id = f"p{raw_chunk.page_number}:c{idx}"

            # Compute bounding box: take the union of all element bboxes
            bbox = self._compute_union_bbox(raw_chunk.bboxes)

            # Count tokens
            token_count = self._count_tokens(raw_chunk.raw_text)

            final_chunk = FinalChunk(
                chunk_id=chunk_id,
                chunk_index=idx,
                project_id=project_id,
                file_id=file_id,
                page_number=raw_chunk.page_number,
                section_header=raw_chunk.section_header,
                raw_text=raw_chunk.raw_text,
                enriched_text=raw_chunk.raw_text,  # Will be updated by Enricher
                bounding_box=bbox,
                token_count=token_count,
                is_table=(raw_chunk.chunk_type == "table"),
                table_html=raw_chunk.table_html,
                is_image=(raw_chunk.chunk_type == "image"),
                image_path=getattr(raw_chunk, "image_path", None),
            )
            final_chunks.append(final_chunk)

        image_count = sum(1 for c in final_chunks if c.is_image)
        print(f"[MetadataExtractor] Tagged {len(final_chunks)} chunks with metadata "
              f"(project={project_id[:8]}..., file={file_id[:8]}..., images={image_count})")
        return final_chunks

    def _compute_union_bbox(self, bboxes: list) -> Optional[dict]:
        """
        Compute the union bounding box across all element bboxes.
        Returns {x, y, w, h} or None if no bboxes available.
        """
        if not bboxes:
            return None
        
        valid = [b for b in bboxes if b is not None]
        if not valid:
            return None

        min_x = min(b["x"] for b in valid)
        min_y = min(b["y"] for b in valid)
        max_x = max(b["x"] + b["w"] for b in valid)
        max_y = max(b["y"] + b["h"] for b in valid)

        return {
            "x": round(min_x, 6),
            "y": round(min_y, 6),
            "w": round(max_x - min_x, 6),
            "h": round(max_y - min_y, 6),
        }

    def _count_tokens(self, text: str) -> int:
        """
        Approximate token count. Uses a provider-neutral tiktoken encoding if
        available, otherwise falls back to a simple word-based estimate.
        """
        try:
            import tiktoken
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(text))
        except Exception:
            # Fallback: rough estimate
            return int(len(text.split()) * 1.3)
