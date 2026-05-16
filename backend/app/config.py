# app/config.py
"""
Centralized settings management using pydantic-settings.
All configuration is loaded from environment variables.
Access settings via: from app.config import settings
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # --- App ---
    app_name: str = "FinSight AI"
    app_version: str = "1.0.0"
    debug_mode: bool = False

    # --- Database ---
    database_url: str = "postgresql+asyncpg://finsight:finsight_dev@postgres:5432/finsight"
    db_pool_size: int = 20
    db_max_overflow: int = 10
    db_pool_timeout: int = 30
    db_pool_recycle: int = 1800

    # --- Redis ---
    redis_url: str = "redis://redis:6379/0"

    # --- Qdrant ---
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    qdrant_collection: str = "document_chunks"
    qdrant_vector_size: int = 384  # all-MiniLM-L6-v2 dimension
    vector_dim: int = 3072  # text-embedding-3-large

    # --- APIs ---
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    ai_provider: str = Field(default="groq", alias="AI_PROVIDER")
    gemini_openai_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    groq_openai_base_url: str = "https://api.groq.com/openai/v1"

    # --- Auth ---
    jwt_secret: str = "change_this_in_production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 24

    # --- CORS ---
    cors_origins: List[str] = ["http://localhost:3000", "http://frontend:3000"]

    # --- File Storage ---
    upload_dir: str = "/app/uploads"
    max_upload_size_mb: int = 50

    # --- LLM Models ---
    generation_model: str = "llama-3.3-70b-versatile"
    utility_model: str = "llama-3.3-70b-versatile"
    embedding_model: str = "gemini-embedding-001"  # Groq doesn't do embeddings, keep Gemini
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # --- Voice ---
    stt_model: str = "whisper-1"
    tts_model: str = "tts-1"
    tts_voice: str = "alloy"
    vad_silence_bytes: int = 32000

    # --- Pipeline ---
    retrieval_threshold: float = 0.5
    gate1_threshold: float = 0.3
    gate2_threshold: float = 0.5
    chat_history_limit: int = 6
    supported_languages: List[str] = ["en", "hi", "gu", "mr"]
    chart_keywords: List[str] = ["revenue", "growth", "trend", "chart", "plot", "quarterly", "annual"]
    table_keywords: List[str] = ["table", "compare", "list", "segments", "breakdown", "distribution"]
    
    # --- Advanced Retrieval Settings ---
    retrieval_top_k: int = 150
    section_top_k: int = 15
    rrf_k: int = 60
    reranker_top_k: int = 20
    create_collection_on_startup: bool = False
    
    # --- Internal Redis / Path Overrides ---
    redis_host: str = "localhost"
    redis_port: int = 6379
    bm25_index_dir: str = "./data/bm25_indexes"

    # --- Feature Flags ---
    enable_prompt_caching: bool = True
    enable_slm_compression: bool = True
    enable_voice: bool = True


settings = Settings()

def get_settings():
    return settings
