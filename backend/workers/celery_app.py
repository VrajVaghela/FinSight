# workers/celery_app.py
from celery import Celery
import os
import asyncio
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

celery_app = Celery(
    "finsight",
    broker=REDIS_URL,
    backend=REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,
)

@celery_app.task(name="workers.ingestion_tasks.ingest_pdf", bind=True, max_retries=2)
def ingest_pdf(self, file_id: str, project_id: str, file_path: str):
    import asyncio
    return asyncio.run(async_ingest_pdf(self, file_id, project_id, file_path))

async def async_ingest_pdf(task_self, file_id: str, project_id: str, file_path: str):
    from app.models.database import SessionLocal
    from app.models.orm import File as DBFile, Project
    from app.ingestion.pipeline import IngestionPipeline
    from datetime import datetime
    
    async with SessionLocal() as db:
        db_file = None
        try:
            absolute_path = Path(file_path).resolve()
            print(f"[Worker] Task received: file_id={file_id[:8]}..., path={absolute_path}")

            db_file = await db.get(DBFile, file_id)
            if not db_file:
                print(f"[Worker] ERROR: File {file_id} not found in DB.")
                return

            db_file.docling_status = "processing"
            await db.commit()

            if not absolute_path.exists():
                raise FileNotFoundError(f"File not found at {absolute_path}")

            project = await db.get(Project, project_id)
            doc_title = project.name if project else "Financial Document"

            # Skip enrichment to preserve API quota for chat queries
            # Enrichment adds context summaries but is not required for RAG to work
            skip_enrichment = True

            pipeline = IngestionPipeline()
            # Run the synchronous pipeline in a separate thread to avoid blocking the event loop
            result = await asyncio.to_thread(
                pipeline.run,
                file_path=str(absolute_path),
                project_id=project_id,
                file_id=file_id,
                doc_title=doc_title,
                skip_enrichment=skip_enrichment,
            )

            # Re-fetch the file object as the session might have been stale/closed after the long thread call
            db_file = await db.get(DBFile, file_id)
            if not db_file:
                print(f"[Worker] ERROR: File {file_id} disappeared from DB.")
                return

            db_file.page_count = result.get("page_count", 0)
            db_file.chunk_count = result.get("chunk_count", 0)
            db_file.docling_status = result.get("status", "ready")
            db_file.ingested_at = datetime.utcnow()
            await db.commit()
            print(f"[Worker] SUCCESS: {db_file.original_name} -> {db_file.chunk_count} chunks")
            return {"status": "success", "file_id": file_id}
            
        except Exception as e:
            await db.rollback()
            error_msg = str(e)
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "..."
            
            if db_file:
                db_file.docling_status = "failed"
                db_file.error_message = error_msg
                await db.commit()
            print(f"[Worker] FAILED: {error_msg}")
            if "Connection" in error_msg or "Timeout" in error_msg:
                raise task_self.retry(exc=e, countdown=30)
        finally:
            from app.models.database import engine
            await engine.dispose()
