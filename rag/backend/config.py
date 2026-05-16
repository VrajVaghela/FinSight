from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    qdrant_host: str = os.getenv("QDRANT_HOST", "qdrant")
    qdrant_port: int = int(os.getenv("QDRANT_PORT", "6333"))
    qdrant_collection: str = os.getenv("QDRANT_COLLECTION", "document_chunks")
    qdrant_vector_size: int = int(os.getenv("QDRANT_VECTOR_SIZE", "3072"))
    ai_provider: str = os.getenv("AI_PROVIDER", "gemini")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
    redis_host: str = os.getenv("REDIS_HOST", "redis")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    gate1_threshold: float = float(os.getenv("GATE1_THRESHOLD", "0.5"))
    gate2_threshold: float = float(os.getenv("GATE2_THRESHOLD", "0.0"))
    rrf_k: int = int(os.getenv("RRF_K", "60"))
    retrieval_top_k: int = int(os.getenv("RETRIEVAL_TOP_K", "150"))
    reranker_top_k: int = int(os.getenv("RERANKER_TOP_K", "20"))
    reranker_model: str = os.getenv(
        "RERANKER_MODEL",
        "cross-encoder/ms-marco-MiniLM-L-6-v2",
    )
    create_collection_on_startup: bool = (
        os.getenv("CREATE_QDRANT_COLLECTION_ON_STARTUP", "false").lower()
        in {"1", "true", "yes"}
    )
    query_log_path: str = os.getenv("QUERY_LOG_PATH", "backend/logs/retrieval_queries.jsonl")
    query_log_retention_days: int = int(os.getenv("QUERY_LOG_RETENTION_DAYS", "30"))
    dynamic_thresholds_enabled: bool = (
        os.getenv("DYNAMIC_THRESHOLDS_ENABLED", "true").lower() in {"1", "true", "yes"}
    )
    gate1_numeric_delta: float = float(os.getenv("GATE1_NUMERIC_DELTA", "-0.05"))
    gate1_short_query_delta: float = float(os.getenv("GATE1_SHORT_QUERY_DELTA", "0.05"))
    gate1_personal_info_delta: float = float(os.getenv("GATE1_PERSONAL_INFO_DELTA", "0.10"))
    gate2_table_delta: float = float(os.getenv("GATE2_TABLE_DELTA", "-0.03"))
    gate2_followup_delta: float = float(os.getenv("GATE2_FOLLOWUP_DELTA", "-0.05"))
    gate2_speculative_delta: float = float(os.getenv("GATE2_SPECULATIVE_DELTA", "0.15"))
    section_collection: str = os.getenv("QDRANT_SECTION_COLLECTION", "document_sections")
    section_rrf_k: int = int(os.getenv("SECTION_RRF_K", "30"))
    section_top_k: int = int(os.getenv("SECTION_TOP_K", "5"))
    session_scope_bias: float = float(os.getenv("SESSION_SCOPE_BIAS", "0.15"))
    session_chunk_scope_bias: float = float(os.getenv("SESSION_CHUNK_SCOPE_BIAS", "0.05"))
    session_scope_ttl_seconds: int = int(os.getenv("SESSION_SCOPE_TTL_SECONDS", "86400"))


def get_settings() -> Settings:
    return Settings()
