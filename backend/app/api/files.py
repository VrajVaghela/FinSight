# app/api/files.py
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from fastapi.responses import FileResponse as FastAPIFileResponse
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
import os
import shutil
import logging
import asyncio
from app.models.database import get_db
from app.models.orm import File as DBFile, Project
from app.models.schemas import FileUploadResponse
from app.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

UPLOAD_DIR = settings.upload_dir

@router.post("/projects/{project_id}/files", response_model=FileUploadResponse)
async def upload_file(
    project_id: uuid.UUID,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    # Verify project exists
    project = await db.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    file_id = uuid.uuid4()
    filename = f"{file_id}_{file.filename}"
    file_path = os.path.join(UPLOAD_DIR, filename)

    try:
        # Save file locally
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Create DB record. In local debug mode we mark the file as ready so
        # the UI can proceed without requiring Redis/Celery/Qdrant.
        db_file = DBFile(
            id=file_id,
            project_id=project_id,
            original_name=file.filename,
            storage_path=file_path,
            docling_status="ready" if settings.debug_mode else "pending"
        )
        db.add(db_file)
        await db.commit()

        task_id = None
        if not settings.debug_mode:
            from workers.celery_app import ingest_pdf
            task = ingest_pdf.delay(str(file_id), str(project_id), file_path)
            task_id = task.id
    except Exception as exc:
        await db.rollback()
        logger.exception("File upload failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return FileUploadResponse(
        file_id=file_id,
        original_name=file.filename,
        status="ready" if settings.debug_mode else "pending",
        task_id=task_id
    )

@router.get("/files/{file_id}/status", response_model=FileUploadResponse)
async def get_file_status(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """Poll ingestion status for a single file."""
    file = await db.get(DBFile, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileUploadResponse(
        file_id=file.id,
        original_name=file.original_name,
        status=file.docling_status,
        task_id=None
    )


@router.get("/files/{file_id}/sections")
async def get_file_sections(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return the document's table of contents by extracting unique section headers
    from the indexed chunks in Qdrant."""
    file = await db.get(DBFile, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    sections = []
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter, FieldCondition, MatchValue, ScrollRequest
        import asyncio

        qdrant = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            check_compatibility=False,
        )

        # Scroll through all points for this file
        all_points = []
        offset = None
        while True:
            scroll_result = await asyncio.to_thread(
                qdrant.scroll,
                collection_name=settings.qdrant_collection,
                scroll_filter=Filter(
                    must=[FieldCondition(key="file_id", match=MatchValue(value=str(file_id)))]
                ),
                limit=100,
                offset=offset,
                with_payload=True,
            )
            points, next_offset = scroll_result
            all_points.extend(points)
            if next_offset is None:
                break
            offset = next_offset

        # Group chunks by page to extract a title per page/section
        pages = {}
        for pt in all_points:
            payload = pt.payload or {}
            page = payload.get("page_number", 0)
            if page not in pages:
                pages[page] = []
            pages[page].append(payload)
            
        seen = {}
        for page, payloads in pages.items():
            # Sort payloads by chunk_index to get the chronological first chunk
            payloads.sort(key=lambda x: x.get("chunk_index", 0))
            
            header = ""
            # Try to find a valid section header
            for p in payloads:
                h = p.get("section_header", "").strip()
                if h and not h.lower().startswith("page "):
                    header = h
                    break
            
            # If no section header, fallback to the first line of text on this page
            if not header and payloads:
                first_text = payloads[0].get("raw_text", "").strip()
                if first_text:
                    # Take the first line, up to 60 characters
                    first_line = first_text.split('\n')[0].strip()
                    header = first_line[:60] + ("..." if len(first_line) > 60 else "")
            
            if header:
                chunk_id = payloads[0].get("chunk_id", "")
                if header not in seen:
                    seen[header] = {
                        "id": chunk_id,
                        "title": header,
                        "page": page,
                    }
                else:
                    # Keep the earliest occurrence
                    if page < seen[header]["page"]:
                        seen[header]["page"] = page
                        seen[header]["id"] = chunk_id

        sections = sorted(seen.values(), key=lambda s: s["page"])
    except Exception as e:
        logger.warning(f"Failed to fetch sections from Qdrant: {e}")
        # Return empty sections if Qdrant is unavailable
        sections = []

    return {
        "file_id": str(file_id),
        "file_name": file.original_name,
        "sections": sections,
    }


@router.get("/files/{file_id}/content")
async def get_file_content(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Fetch all chunks for a file (useful for rendering non-PDF documents)."""
    from qdrant_client import QdrantClient
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    from app.config import settings

    file = await db.get(DBFile, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        qdrant = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            check_compatibility=False,
        )
        all_points = []
        offset = None
        while True:
            scroll_result = await asyncio.to_thread(
                qdrant.scroll,
                collection_name=settings.qdrant_collection,
                scroll_filter=Filter(
                    must=[FieldCondition(key="file_id", match=MatchValue(value=str(file_id)))]
                ),
                limit=100,
                offset=offset,
                with_payload=True,
            )
            points, next_offset = scroll_result
            all_points.extend(points)
            if next_offset is None:
                break
            offset = next_offset

        chunks = []
        for pt in all_points:
            payload = pt.payload or {}
            chunks.append({
                "chunk_id": payload.get("chunk_id", str(pt.id)),
                "chunk_index": payload.get("chunk_index", 0),
                "raw_text": payload.get("raw_text", payload.get("enriched_text", "")),
                "table_html": payload.get("table_html", ""),
                "is_table": payload.get("is_table", False),
                "section_header": payload.get("section_header", ""),
                "page_number": payload.get("page_number", 0),
            })

        chunks.sort(key=lambda c: c["chunk_index"])

        return {
            "file_id": str(file_id),
            "file_name": file.original_name,
            "chunks": chunks
        }
    except Exception as e:
        logger.error(f"Failed to fetch content from Qdrant: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch file content")


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Serve the original PDF file for in-browser viewing."""
    file = await db.get(DBFile, file_id)
    if not file:
        raise HTTPException(status_code=404, detail="File not found")

    if not os.path.exists(file.storage_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FastAPIFileResponse(
        path=file.storage_path,
        media_type="application/pdf",
        filename=file.original_name,
        headers={"Content-Disposition": f'inline; filename="{file.original_name}"'},
    )


@router.get("/chunks/lookup")
async def lookup_chunk(
    chunk_id: str,
    project_id: str = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Resolve a chunk_id (e.g., 'p3:c2' or a UUID string) to its full payload
    including file_id, section_header, page_number, and text.

    This is used by the Document Explorer when the caller only has an LLM
    citation marker and needs to find the backing document.
    """
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        qdrant = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            check_compatibility=False,
        )

        # Build filter: match by chunk_id field in payload, optionally scoped to project
        must_conditions = [FieldCondition(key="chunk_id", match=MatchValue(value=chunk_id))]
        if project_id:
            must_conditions.append(
                FieldCondition(key="project_id", match=MatchValue(value=project_id))
            )

        scroll_result = await asyncio.to_thread(
            qdrant.scroll,
            collection_name=settings.qdrant_collection,
            scroll_filter=Filter(must=must_conditions),
            limit=1,
            with_payload=True,
        )
        points, _ = scroll_result

        if not points:
            raise HTTPException(status_code=404, detail=f"Chunk '{chunk_id}' not found")

        payload = points[0].payload or {}
        return {
            "chunk_id": payload.get("chunk_id", str(points[0].id)),
            "file_id": payload.get("file_id", ""),
            "section_header": payload.get("section_header", ""),
            "page_number": payload.get("page_number", 0),
            "raw_text": payload.get("raw_text", payload.get("enriched_text", "")),
            "table_html": payload.get("table_html", ""),
            "is_table": payload.get("is_table", False),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chunk lookup failed for '{chunk_id}': {e}")
        raise HTTPException(status_code=500, detail="Chunk lookup failed")

