"""
FinSight AI — Pipeline Orchestrator
Orchestrates the full ingestion pipeline in sequence:
  1. DoclingParser     → Parse PDF into structured document
  2. StructuralChunker → Split into heading-anchored, table-isolated chunks
  3. MetadataExtractor → Assign UUIDs, bounding boxes, project/file IDs
  4. ContextualEnricher → LLM-generated summaries + table KV extraction
  5. DualIndexer       → Write to Qdrant (dense) + BM25 (sparse)
"""
from typing import Optional

from backend.ingestion.docling_parser import DoclingParser
from backend.ingestion.chunker import StructuralChunker
from backend.ingestion.metadata_extractor import MetadataExtractor, FinalChunk
from backend.ingestion.enricher import ContextualEnricher
from backend.ingestion.dual_indexer import DualIndexer


class IngestionPipeline:
    """
    Runs the complete ingestion pipeline for a single PDF file.
    
    Usage:
        pipeline = IngestionPipeline()
        result = pipeline.run(
            file_path="/data/uploads/abc.pdf",
            project_id="...",
            file_id="...",
            doc_title="Adani Enterprises Q2 FY26",
            doc_date="October 2025",
        )
    """

    def __init__(self):
        self.parser = DoclingParser()
        self.chunker = StructuralChunker()
        self.extractor = MetadataExtractor()
        self.enricher = ContextualEnricher()
        self.indexer = DualIndexer()

    def run(
        self,
        file_path: str,
        project_id: str,
        file_id: str,
        doc_title: str = "Financial Document",
        doc_date: str = "Unknown",
        skip_enrichment: bool = False,
        progress_callback=None,
    ) -> dict:
        """
        Execute the full pipeline.
        
        Args:
            file_path: Absolute path to the PDF
            project_id: UUID string for project isolation
            file_id: UUID string for this file
            doc_title: Title for enrichment prompts
            doc_date: Date for enrichment prompts
            skip_enrichment: If True, skip LLM calls (useful for testing)
            progress_callback: Function to call with progress updates
            
        Returns:
            dict with {chunk_count, page_count, table_count, status}
        """
        print(f"\n{'='*60}")
        print(f"[Pipeline] Starting ingestion for: {file_path}")
        print(f"[Pipeline] Project: {project_id[:8]}... | File: {file_id[:8]}...")
        print(f"{'='*60}\n")

        # Phase 2: Parse PDF with Docling
        if progress_callback: progress_callback("Phase 2: Visually mapping PDF layout with Docling...")
        print("[Pipeline] Phase 2: Parsing PDF with Docling...")
        docling_result = self.parser.parse_pdf(file_path)
        
        # Get page count from Docling
        pages = getattr(docling_result.document, 'pages', {})
        page_count = len(pages) if pages else 1

        # Phase 3: Structural Chunking
        if progress_callback: progress_callback("Phase 3: Slicing document at structural boundaries...")
        print("\n[Pipeline] Phase 3: Structural chunking...")
        raw_chunks = self.chunker.chunk_document(docling_result, file_id=file_id)

        if not raw_chunks:
            print("[Pipeline] WARNING: No chunks produced! Document may be empty.")
            return {"chunk_count": 0, "page_count": page_count, "table_count": 0, "status": "empty"}

        # Phase 4: Metadata Extraction
        if progress_callback: progress_callback("Phase 4: Extracting chunk metadata and bounding boxes...")
        print("\n[Pipeline] Phase 4: Metadata extraction...")
        final_chunks = self.extractor.extract(raw_chunks, project_id, file_id)

        # Phase 5: Contextual Enrichment (LLM calls)
        if not skip_enrichment:
            if progress_callback: progress_callback("Phase 5: Enriching context and extracting tables via Gemini...")
            print("\n[Pipeline] Phase 5: Contextual enrichment (LLM)...")
            self.enricher.doc_title = doc_title
            self.enricher.doc_date = doc_date
            final_chunks = self.enricher.enrich_chunks(final_chunks)
        else:
            print("\n[Pipeline] Phase 5: SKIPPED (skip_enrichment=True)")
            for chunk in final_chunks:
                chunk.enriched_text = chunk.raw_text

        # Phase 6: Dual Indexing (Qdrant + BM25)
        if progress_callback: progress_callback("Phase 6: Dual indexing into Qdrant and local BM25...")
        print("\n[Pipeline] Phase 6: Dual indexing (Qdrant + BM25)...")
        self.indexer.ensure_collection()
        self.indexer.delete_file_points(file_id)  # Re-ingestion safety
        indexed = self.indexer.index_chunks(final_chunks)

        # Summary
        table_count = sum(1 for c in final_chunks if c.is_table)
        kv_count = sum(1 for c in final_chunks if c.table_kv)
        
        print(f"\n{'='*60}")
        print(f"[Pipeline] COMPLETE!")
        print(f"  Pages:      {page_count}")
        print(f"  Chunks:     {indexed}")
        print(f"  Tables:     {table_count}")
        print(f"  Table KVs:  {kv_count}")
        print(f"{'='*60}\n")

        return {
            "chunk_count": indexed,
            "page_count": page_count,
            "table_count": table_count,
            "kv_count": kv_count,
            "status": "ready",
        }
