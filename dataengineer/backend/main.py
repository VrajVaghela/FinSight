import os
import uuid
import shutil
from fastapi import FastAPI, UploadFile, File as FastAPIFile, Depends, HTTPException, Path
from sqlalchemy.orm import Session
from backend.database import engine, Base, get_db
from backend.models import File, Project
from backend.schemas import FileUploadResponse, FileStatusResponse
from backend.ingestion.celery_worker import ingest_document

# Create database tables automatically
Base.metadata.create_all(bind=engine)

app = FastAPI(title="FinSight AI API")

# Ensure upload directory exists
UPLOAD_DIR = os.getenv("PDF_UPLOAD_DIR", "./data/uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Define allowed extensions at the top of main.py
ALLOWED_EXTENSIONS = {".pdf", ".pptx", ".ppt", ".txt"}

@app.post("/api/projects/{project_id}/files", response_model=FileUploadResponse)
async def upload_file(
    project_id: uuid.UUID = Path(...),
    file: UploadFile = FastAPIFile(...),
    db: Session = Depends(get_db)
):
    # 1. Improved Validation
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 2. Project Auto-creation (Keep this for testing)
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        new_project = Project(id=project_id, name=f"Project {str(project_id)[:8]}")
        db.add(new_project)
        db.commit()

    # 3. Save file with original extension preserved
    file_id = uuid.uuid4()
    # We keep the extension so the Worker knows how to parse it later
    safe_filename = f"{file_id}{file_ext}" 
    file_path = os.path.join(UPLOAD_DIR, safe_filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 4. Database Entry
    db_file = File(
        id=file_id,
        project_id=project_id,
        original_name=file.filename,
        file_path=file_path,
        docling_status="pending"
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    # 5. Notify the Worker
    ingest_document.delay(str(file_id), str(project_id), file_path)

    return FileUploadResponse(
        file_id=db_file.id,
        project_id=db_file.project_id,
        status=db_file.docling_status,
        message=f"File '{file.filename}' uploaded. Processing started."
    )

@app.get("/api/projects/{project_id}/status", response_model=list[FileStatusResponse])
async def get_project_files_status(
    project_id: uuid.UUID = Path(...),
    db: Session = Depends(get_db)
):
    """Endpoint for the frontend to poll ingestion status."""
    files = db.query(File).filter(File.project_id == project_id).all()
    
    if not files:
        return []
        
    return [
        FileStatusResponse(
            file_id=f.id,
            status=f.docling_status,
            page_count=f.page_count,
            chunk_count=f.chunk_count or 0,
            progress_message=f.progress_message,
            error_message=f.error_message
        ) for f in files
    ]