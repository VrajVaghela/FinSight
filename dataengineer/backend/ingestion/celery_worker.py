"""
FinSight AI — Celery Worker
Async background task that runs the full ingestion pipeline.
Dispatched by the FastAPI upload endpoint.
"""
import os
# Disable HuggingFace symlinks on Windows to prevent WinError 1314
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["HF_HUB_DISABLE_SYMLINKS"] = "1"

from pathlib import Path
from backend.celery_app import celery_app
from backend.database import SessionLocal
from backend.models import File, Project
from datetime import datetime


@celery_app.task(name="ingestion.ingest_document", bind=True, max_retries=2)
def ingest_document(self, file_id: str, project_id: str, file_path: str):
    """
    Full ingestion pipeline task.
    
    Called as: ingest_document.delay(file_id, project_id, file_path)
    
    Flow:
      1. Set status → "processing"
      2. Run IngestionPipeline (Docling → Chunker → Metadata → Enricher → DualIndexer)
      3. Set status → "ready" with page_count and chunk_count
      4. On failure → set status → "failed" with error_message
    """
    db = SessionLocal()
    db_file = None
    try:
        absolute_path = Path(file_path).resolve()
        print(f"[Worker] Task received: file_id={file_id[:8]}..., path={absolute_path}")

        # Get the file record
        db_file = db.query(File).filter(File.id == file_id).first()
        if not db_file:
            print(f"[Worker] ERROR: File {file_id} not found in DB.")
            return

        # Update status to processing
        db_file.docling_status = "processing"
        db.commit()

        # Validate file exists
        if not absolute_path.exists():
            raise FileNotFoundError(f"File not found at {absolute_path}")

        # Get project info for enrichment prompts
        project = db.query(Project).filter(Project.id == project_id).first()
        doc_title = project.name if project else "Financial Document"

        # Check for GEMINI_API_KEY — if missing, skip enrichment
        skip_enrichment = not os.getenv("GEMINI_API_KEY")
        if skip_enrichment:
            print("[Worker] WARNING: No GEMINI_API_KEY set. Skipping LLM enrichment.")

        # Run the full pipeline
        from backend.ingestion.pipeline import IngestionPipeline
        pipeline = IngestionPipeline()
        
        def update_progress(msg: str):
            if db_file:
                db_file.progress_message = msg
                db.commit()

        result = pipeline.run(
            file_path=str(absolute_path),
            project_id=project_id,
            file_id=file_id,
            doc_title=doc_title,
            skip_enrichment=skip_enrichment,
            progress_callback=update_progress,
        )

        # Update DB with results
        db_file.page_count = result.get("page_count", 0)
        db_file.chunk_count = result.get("chunk_count", 0)
        db_file.docling_status = result.get("status", "ready")
        db_file.ingested_at = datetime.utcnow()
        db.commit()
        print(f"[Worker] SUCCESS: {db_file.original_name} → "
              f"{result['chunk_count']} chunks, {result['page_count']} pages")

    except Exception as e:
        db.rollback()
        error_msg = str(e)
        # Keep error message human-readable
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "..."
        
        if db_file:
            db_file.docling_status = "failed"
            db_file.error_message = error_msg
            db.commit()
        
        print(f"[Worker] FAILED: {error_msg}")

        # Retry on transient errors (Qdrant unreachable, network issue)
        if "Connection" in error_msg or "Timeout" in error_msg:
            raise self.retry(exc=e, countdown=30)

    finally:
        db.close()