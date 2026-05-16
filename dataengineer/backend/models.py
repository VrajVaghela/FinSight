import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from .database import Base

class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Note: In a full app, you'd have system_prompt and owner_id here too

class File(Base):
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    original_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    
    # Status Enum: "pending" -> "processing" -> "ready" | "failed"
    docling_status = Column(String, default="pending") 
    page_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)      # Number of chunks indexed
    progress_message = Column(String, nullable=True) # For live terminal UI updates
    error_message = Column(Text, nullable=True)
    ingested_at = Column(DateTime, default=datetime.utcnow)