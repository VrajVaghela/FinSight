from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class FileUploadResponse(BaseModel):
    file_id: UUID
    project_id: UUID
    status: str
    message: str

class FileStatusResponse(BaseModel):
    file_id: UUID
    docling_status: str
    page_count: int
    chunk_count: int = 0
    progress_message: Optional[str] = None
    error_message: Optional[str] = None