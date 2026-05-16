# app/models/orm.py
import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, DateTime, Integer,
    ForeignKey, JSON, Enum as SAEnum, Index
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    projects = relationship("Project", back_populates="owner")
    conversations = relationship("Conversation", back_populates="user")


# --- Enums ---
IngestionStatusEnum = SAEnum(
    "pending", "processing", "ready", "failed", "empty",
    name="ingestion_status"
)

MessageRoleEnum = SAEnum(
    "user", "assistant", "system",
    name="message_role"
)


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    system_prompt = Column(Text, default="")
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    owner = relationship("User", back_populates="projects")
    files = relationship("File", back_populates="project", cascade="all, delete-orphan")
    conversations = relationship("Conversation", back_populates="project", cascade="all, delete-orphan")

    def file_count(self) -> int:
        return len(self.files)

    def status(self) -> str:
        """Derives project readiness status from its files."""
        if not self.files:
            return "empty"
        statuses = {f.docling_status for f in self.files}
        if "processing" in statuses:
            return "processing"
        if "ready" in statuses and "failed" not in statuses:
            return "ready"
        if "ready" in statuses:
            return "partial"
        return "processing"


class File(Base):
    __tablename__ = "files"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    original_name = Column(String(512), nullable=False)
    storage_path = Column(String(1024), nullable=False)
    docling_status = Column(IngestionStatusEnum, default="pending", nullable=False)
    page_count = Column(Integer, nullable=True)
    chunk_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    ingested_at = Column(DateTime, nullable=True)
    filing_date = Column(DateTime, nullable=True)
    summary = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    project = relationship("Project", back_populates="files")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(512), default="New Conversation")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="conversations")
    project = relationship("Project", back_populates="conversations")
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at"
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(MessageRoleEnum, nullable=False)
    content = Column(Text, nullable=False)
    citations = Column(JSON, default=list)        # [{chunk_id, page, score, text_snippet, bounding_box}]
    retrieved_chunks = Column(JSON, default=list)  # [{chunk_id, score, text}]
    pal_execution = Column(JSON, nullable=True)    # {code, result}
    ui_components = Column(JSON, default=list)     # [{component, data}]
    refusal_info = Column(JSON, nullable=True)     # {level, reason}
    token_usage = Column(JSON, nullable=True)      # {prompt, completion, cached}
    latency_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")


class CacheEntry(Base):
    """Tracks local provider-neutral prompt cache prefixes."""
    __tablename__ = "cache_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prefix_hash = Column(String(64), unique=True, nullable=False, index=True)  # SHA-256
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    cached_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expiry = Column(DateTime, nullable=False)       # 5-min TTL, extended on hit
    hit_count = Column(Integer, default=0)
