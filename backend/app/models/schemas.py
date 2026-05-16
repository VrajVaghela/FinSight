# app/models/schemas.py
"""
Pydantic request/response schemas for all API endpoints.
Strictly aligned with implementation_plan_part1.md Section 2.2.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal, List
from uuid import UUID
from datetime import datetime


# ===========================================================================
# PROJECT
# ===========================================================================

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, description="Project display name")
    system_prompt: str = Field(default="", description="Custom instructions for the AI within this project")


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    system_prompt: Optional[str] = None


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    system_prompt: str
    created_at: datetime
    file_count: int = 0
    status: Literal["empty", "processing", "ready", "partial"] = "empty"


# ===========================================================================
# FILE
# ===========================================================================

class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    original_name: str
    docling_status: str
    page_count: Optional[int] = None
    chunk_count: int = 0
    error_message: Optional[str] = None
    ingested_at: Optional[datetime] = None
    created_at: datetime


class FileUploadResponse(BaseModel):
    file_id: UUID
    original_name: str
    status: str
    task_id: Optional[str] = None  # Celery task ID for polling


class ProjectStatusResponse(BaseModel):
    project_id: UUID
    files: List[FileResponse]
    overall_status: Literal["empty", "processing", "ready", "partial"]


# ===========================================================================
# CHAT
# ===========================================================================

class ChatRequest(BaseModel):
    project_id: UUID
    conversation_id: Optional[UUID] = None   # None = create new
    message: str = Field(..., min_length=1)
    language: str = Field(default="auto", description="ISO 639-1 or 'auto'")
    voice: bool = Field(default=False, description="If True, also return TTS audio")
    debug: bool = Field(default=False, description="If True, include retrieval_debug SSE events")


class Citation(BaseModel):
    chunk_id: str
    page: int
    score: float
    text_snippet: str
    bounding_box: Optional[dict] = None   # {x, y, w, h}


# --- SSE Event Payloads (used internally and in OpenAPI docs) ---

class SSEChunkEvent(BaseModel):
    delta: str
    citations: List[Citation] = []


class SSERetrievalDebug(BaseModel):
    chunks: List[dict]  # [{id, text_snippet, score, page, bounding_box}]


class SSEUIComponent(BaseModel):
    component: Literal["BarChart", "LineChart", "DataTable", "PDFOverlay", "CodeBlock", "PlainText"]
    data: dict


class SSERefusal(BaseModel):
    reason: Literal["level_1_threshold", "level_2_reranker", "level_3_grader", "level_4_postgen"]
    message: str = "Not found in the document."


class SSEPalExecution(BaseModel):
    code: str
    result: str


class SSEDone(BaseModel):
    conversation_id: UUID
    total_tokens: int
    cached_tokens: int
    latency_ms: int


# ===========================================================================
# VOICE
# ===========================================================================

class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1)
    language: str = "en"
    voice_id: str = "alloy"


# ===========================================================================
# CONVERSATION
# ===========================================================================

class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    role: str
    content: str
    citations: List[dict] = []
    pal_execution: Optional[dict] = None
    ui_components: List[dict] = []
    refusal_info: Optional[dict] = None
    token_usage: Optional[dict] = None
    latency_ms: Optional[int] = None
    created_at: datetime


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    title: str
    created_at: datetime


class ConversationHistory(BaseModel):
    conversation_id: UUID
    project_id: UUID
    title: str
    messages: List[MessageResponse]


# ===========================================================================
# AUTH
# ===========================================================================

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds

class UserCreate(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    created_at: datetime
