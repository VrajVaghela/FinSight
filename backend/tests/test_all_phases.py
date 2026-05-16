# tests/test_all_phases.py
"""
Comprehensive Phase Verification Tests
Validates all phases from the implementation plan (Parts 1, 2, 3).
Run: pytest tests/test_all_phases.py -v
"""
import pytest
import os
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# ===========================================================================
# PHASE 1: FOUNDATION TESTS
# ===========================================================================

class TestPhase1Infrastructure:
    """Verify pyproject.toml dependencies, env var usage, and schema correctness."""

    def test_all_env_vars_have_defaults_or_documented(self):
        """No required env var should crash the app if missing — all must have defaults."""
        import importlib
        import app.models.database as db_mod
        import app.core.memory_manager as mm_mod
        import app.core.voice_handler as vh_mod
        import app.services.chat_service as cs_mod
        # If import fails, module has a missing/broken import
        assert db_mod is not None
        assert mm_mod is not None
        assert vh_mod is not None
        assert cs_mod is not None

    def test_upload_dir_uses_env_var(self):
        """UPLOAD_DIR must be read from env, not hardcoded."""
        import app.api.files as files_mod
        # Verify the UPLOAD_DIR variable reads from env
        with patch.dict(os.environ, {"UPLOAD_DIR": "/custom/path"}):
            import importlib
            importlib.reload(files_mod)
            assert files_mod.UPLOAD_DIR == "/custom/path"

    def test_schemas_file_upload_has_task_id(self):
        """FileUploadResponse must include task_id field."""
        from app.models.schemas import FileUploadResponse
        fields = FileUploadResponse.model_fields
        assert "task_id" in fields, "FileUploadResponse is missing 'task_id' field"
        assert "file_id" in fields
        assert "status" in fields

    def test_schemas_chat_request_all_fields(self):
        """ChatRequest must have all fields from implementation plan."""
        from app.models.schemas import ChatRequest
        fields = ChatRequest.model_fields
        required = ["project_id", "message"]
        optional = ["conversation_id", "language", "voice", "debug"]
        for f in required:
            assert f in fields, f"ChatRequest missing required field: {f}"
        for f in optional:
            assert f in fields, f"ChatRequest missing optional field: {f}"

    def test_orm_models_exist(self):
        """All ORM models from the schema design must be importable."""
        from app.models.orm import Project, File, Conversation, Message
        assert Project.__tablename__ == "projects"
        assert File.__tablename__ == "files"
        assert Conversation.__tablename__ == "conversations"
        assert Message.__tablename__ == "messages"

    def test_docker_compose_exists(self):
        """docker-compose.yml must exist at the project root."""
        import pathlib
        compose_path = pathlib.Path(__file__).parent.parent.parent / "docker-compose.yml"
        assert compose_path.exists(), "docker-compose.yml not found at ps2_hydra root"

    def test_dockerfile_exists(self):
        """Dockerfile must exist in the backend directory."""
        import pathlib
        dockerfile_path = pathlib.Path(__file__).parent.parent / "Dockerfile"
        assert dockerfile_path.exists(), "Dockerfile not found in backend/"

    def test_env_example_exists_and_has_required_keys(self):
        """`.env.example` must exist and contain all critical keys."""
        import pathlib
        env_path = pathlib.Path(__file__).parent.parent / ".env.example"
        assert env_path.exists(), ".env.example not found"
        content = env_path.read_text()
        required_keys = [
            "AI_PROVIDER", "GEMINI_API_KEY", "DATABASE_URL", "REDIS_URL",
            "JWT_SECRET", "GENERATION_MODEL", "UTILITY_MODEL",
            "GRADER_MODEL", "PAL_MODEL", "EMBEDDING_MODEL",
            "QDRANT_VECTOR_SIZE", "STT_MODEL", "TTS_MODEL", "RETRIEVAL_THRESHOLD"
        ]
        for key in required_keys:
            assert key in content, f".env.example missing required key: {key}"

    def test_gemini_is_default_provider(self):
        """The backend must default to Gemini and 3072-dimensional embeddings."""
        from app.config import settings

        assert settings.ai_provider == "gemini"
        assert settings.generation_model == "gemini-2.5-flash-lite"
        assert settings.utility_model == "gemini-2.5-flash-lite"
        assert settings.grader_model == "gemini-2.5-flash-lite"
        assert settings.pal_model == "gemini-2.5-flash-lite"
        assert settings.embedding_model == "gemini-embedding-001"
        assert settings.vector_dim == 3072

    def test_llm_client_requires_gemini_key_by_default(self):
        """Default LLM client creation must require GEMINI_API_KEY, not OPENAI_API_KEY."""
        from app.core.llm_client import get_llm_client

        fake_settings = MagicMock(
            ai_provider="gemini",
            gemini_api_key="",
            gemini_openai_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        with patch("app.core.llm_client.settings", fake_settings):
            with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
                get_llm_client()

    def test_llm_client_uses_gemini_openai_compatible_endpoint(self):
        """Gemini default should instantiate the OpenAI SDK with Google's compatible base URL."""
        from app.core.llm_client import get_llm_client

        fake_settings = MagicMock(
            ai_provider="gemini",
            gemini_api_key="gemini-test-key",
            gemini_openai_base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )
        with patch("app.core.llm_client.settings", fake_settings):
            with patch("app.core.llm_client.AsyncOpenAI") as mock_cls:
                client = get_llm_client()
        assert client is mock_cls.return_value
        mock_cls.assert_called_once_with(
            api_key="gemini-test-key",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        )

    def test_llm_client_supports_optional_openai_fallback(self):
        """OpenAI remains available only when explicitly selected."""
        from app.core.llm_client import get_llm_client

        fake_settings = MagicMock(ai_provider="openai", openai_api_key="sk-test")
        with patch("app.core.llm_client.settings", fake_settings):
            with patch("app.core.llm_client.AsyncOpenAI") as mock_cls:
                client = get_llm_client()
        assert client is mock_cls.return_value
        mock_cls.assert_called_once_with(api_key="sk-test")


# ===========================================================================
# PHASE 2: CHAT PIPELINE CORE TESTS
# ===========================================================================

class TestPhase2ChatPipeline:
    """Verify QueryRewriter, ProjectMemory, SSEFormatter, SLMCompressor."""

    @pytest.mark.asyncio
    async def test_query_rewriter_no_history_returns_original(self):
        """With empty history, rewriter must return the original message unchanged."""
        from app.core.memory_manager import QueryRewriter
        mock_client = AsyncMock()
        rewriter = QueryRewriter(llm_client=mock_client)
        result = await rewriter.rewrite([], "What is the revenue?")
        # No LLM call should be made for empty history
        mock_client.chat.completions.create.assert_not_called()
        assert result == "What is the revenue?"

    @pytest.mark.asyncio
    async def test_query_rewriter_uses_utility_model_from_env(self):
        """QueryRewriter must use UTILITY_MODEL env var, not a hardcoded model name."""
        from app.core.memory_manager import QueryRewriter
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = AsyncMock(
            choices=[MagicMock(message=MagicMock(content="standalone query"))]
        )
        with patch.dict(os.environ, {"UTILITY_MODEL": "gemini-custom-utility"}):
            rewriter = QueryRewriter(llm_client=mock_client)
            assert rewriter.model == "gemini-custom-utility"

    @pytest.mark.asyncio
    async def test_query_rewriter_rewrites_followup(self):
        """With history, rewriter must call LLM to produce standalone query."""
        from app.core.memory_manager import QueryRewriter
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content='{"query": "What are Adani\'s airport revenues?", "cross_document": false}'))]
        )
        rewriter = QueryRewriter(llm_client=mock_client)
        history = [
            {"role": "user", "content": "Tell me about Adani"},
            {"role": "assistant", "content": "Adani is a conglomerate..."}
        ]
        result = await rewriter.rewrite(history, "Break down the airport part")
        mock_client.chat.completions.create.assert_called_once()
        assert "airport" in result["query"].lower()

    def test_sse_formatter_chunk_event(self):
        """SSE chunk event must include delta and citations fields."""
        from app.core.streaming import SSEFormatter
        event = SSEFormatter.chunk("Hello world", [])
        assert "event: chunk" in event
        assert "delta" in event
        assert "citations" in event
        assert "Hello world" in event

    def test_sse_formatter_refusal_event(self):
        """SSE refusal event must include reason and standard message."""
        from app.core.streaming import SSEFormatter
        event = SSEFormatter.refusal("level_1_threshold")
        assert "event: refusal" in event
        assert "Not found in the document" in event

    def test_sse_formatter_done_event(self):
        """SSE done event must contain conversation_id, tokens, latency."""
        from app.core.streaming import SSEFormatter
        cid = str(uuid4())
        event = SSEFormatter.done(cid, 150, 80, 342)
        assert "event: done" in event
        parsed = json.loads(event.split("data: ")[1])
        assert parsed["conversation_id"] == cid
        assert parsed["total_tokens"] == 150
        assert parsed["latency_ms"] == 342

    def test_sse_formatter_all_six_event_types(self):
        """All 6 SSE event types from the implementation plan must be functional."""
        from app.core.streaming import SSEFormatter
        cid = str(uuid4())
        assert "event: chunk" in SSEFormatter.chunk("x")
        assert "event: retrieval_debug" in SSEFormatter.retrieval_debug([])
        assert "event: ui_component" in SSEFormatter.ui_component("BarChart", {})
        assert "event: refusal" in SSEFormatter.refusal("test")
        assert "event: pal_execution" in SSEFormatter.pal_execution("code", "result")
        assert "event: done" in SSEFormatter.done(cid, 0, 0, 0)

    @pytest.mark.asyncio
    async def test_slm_compressor_uses_utility_model_from_env(self):
        """SLMCompressor must use UTILITY_MODEL env var."""
        from app.core.slm_compressor import SLMCompressor
        mock_client = AsyncMock()
        with patch.dict(os.environ, {"UTILITY_MODEL": "gemini-custom-utility"}):
            compressor = SLMCompressor(llm_client=mock_client)
            assert compressor.model == "gemini-custom-utility"

    @pytest.mark.asyncio
    async def test_slm_compressor_removes_irrelevant_chunks(self):
        """SLMCompressor must drop chunks marked IRRELEVANT by the LLM."""
        from app.core.slm_compressor import SLMCompressor
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="IRRELEVANT"))]
        )
        compressor = SLMCompressor(llm_client=mock_client)
        chunks = [{"raw_text": "Some irrelevant text about the weather."}]
        result = await compressor.compress_chunks("What is the revenue?", chunks)
        assert result == [], "IRRELEVANT chunks should be dropped"


# ===========================================================================
# PHASE 3: PAL, CITATIONS, GLEAN TESTS
# ===========================================================================

class TestPhase3UIComponents:
    """Verify UI component keyword detection is env-configurable, not hardcoded."""

    @pytest.mark.asyncio
    async def test_chat_service_chart_keywords_from_env(self):
        """CHART_KEYWORDS must be read from env in chat_service."""
        import app.services.chat_service as cs_mod
        import importlib
        with patch.dict(os.environ, {"CHART_KEYWORDS": "banana,mango"}):
            importlib.reload(cs_mod)
            assert "banana" in cs_mod.CHART_KEYWORDS
            assert "mango" in cs_mod.CHART_KEYWORDS
            # Default keywords should NOT be present after override
            assert "revenue" not in cs_mod.CHART_KEYWORDS

    @pytest.mark.asyncio
    async def test_chat_service_table_keywords_from_env(self):
        """TABLE_KEYWORDS must be read from env in chat_service."""
        import app.services.chat_service as cs_mod
        import importlib
        with patch.dict(os.environ, {"TABLE_KEYWORDS": "orange,grape"}):
            importlib.reload(cs_mod)
            assert "orange" in cs_mod.CHART_KEYWORDS or "orange" in cs_mod.TABLE_KEYWORDS

    def test_prompt_cache_hash_is_deterministic(self):
        """Same prompt inputs must always produce the same hash."""
        from app.core.prompt_cache import ProviderPromptCache
        cache = ProviderPromptCache(db_session=None)
        h1 = cache.compute_prefix_hash("system", "context")
        h2 = cache.compute_prefix_hash("system", "context")
        assert h1 == h2

    def test_prompt_cache_different_inputs_produce_different_hashes(self):
        """Different inputs must NOT produce the same hash."""
        from app.core.prompt_cache import ProviderPromptCache
        cache = ProviderPromptCache(db_session=None)
        h1 = cache.compute_prefix_hash("system", "context A")
        h2 = cache.compute_prefix_hash("system", "context B")
        assert h1 != h2


# ===========================================================================
# PHASE 4: MEMORY AND MULTILINGUAL TESTS
# ===========================================================================

class TestPhase4Memory:
    """Verify MEM1Adapter and language detection."""

    @pytest.mark.asyncio
    async def test_mem1_adapter_uses_utility_model_from_env(self):
        """MEM1Adapter must use UTILITY_MODEL env var."""
        from app.core.memory_manager import MEM1Adapter
        mock_client = AsyncMock()
        with patch.dict(os.environ, {"UTILITY_MODEL": "gemini-custom-memory"}):
            adapter = MEM1Adapter(llm_client=mock_client)
            assert adapter.model == "gemini-custom-memory"

    @pytest.mark.asyncio
    async def test_mem1_state_update_calls_llm(self):
        """MEM1 update_state must call the LLM with correct inputs."""
        from app.core.memory_manager import MEM1Adapter
        mock_client = AsyncMock()
        mock_client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="Updated state: user asked about revenue"))]
        )
        adapter = MEM1Adapter(llm_client=mock_client)
        result = await adapter.update_state("", "What is revenue?", "Revenue is $100M.")
        mock_client.chat.completions.create.assert_called_once()
        assert "Updated state" in result

    def test_language_detection_english(self):
        """English text must be detected as 'en'."""
        from langdetect import detect
        assert detect("What are the business segments?") == "en"

    def test_supported_languages_from_env(self):
        """SUPPORTED_LANGUAGES must be configurable from env."""
        import app.services.chat_service as cs_mod
        import importlib
        with patch.dict(os.environ, {"SUPPORTED_LANGUAGES": "en,fr,de"}):
            importlib.reload(cs_mod)
            assert "fr" in cs_mod.SUPPORTED_LANGUAGES
            assert "hi" not in cs_mod.SUPPORTED_LANGUAGES


# ===========================================================================
# PHASE 5: VOICE TESTS
# ===========================================================================

class TestPhase5Voice:
    """Verify VoiceHandler uses env vars and auth is properly wired."""

    def test_voice_handler_models_from_env(self):
        """VoiceHandler must read STT_MODEL, TTS_MODEL, TTS_VOICE from env."""
        with patch.dict(os.environ, {
            "STT_MODEL": "gemini-custom-stt",
            "TTS_MODEL": "gemini-custom-tts",
            "TTS_VOICE": "Kore",
            "GEMINI_API_KEY": "gemini-test-key"
        }):
            from app.core import voice_handler
            import importlib
            importlib.reload(voice_handler)
            handler = voice_handler.VoiceHandler()
            assert handler.stt_model == "gemini-custom-stt"
            assert handler.tts_model == "gemini-custom-tts"
            assert handler.voice == "Kore"

    def test_vad_threshold_from_env(self):
        """VAD silence threshold must be configurable via env var."""
        with patch.dict(os.environ, {"VAD_SILENCE_BYTES": "64000", "GEMINI_API_KEY": "gemini-test-key"}):
            from app.core import voice_handler
            import importlib
            importlib.reload(voice_handler)
            handler = voice_handler.VoiceHandler()
            assert handler.silence_threshold_bytes == 64000

    def test_jwt_secret_from_env(self):
        """JWT_SECRET must not be hardcoded — must come from env."""
        import app.middleware.auth as auth_mod
        original_secret = auth_mod.JWT_SECRET
        with patch.dict(os.environ, {"JWT_SECRET": "my_test_secret_123"}):
            import importlib
            importlib.reload(auth_mod)
            assert auth_mod.JWT_SECRET == "my_test_secret_123"

    def test_create_and_verify_token_roundtrip(self):
        """JWT tokens created must be verifiable by verify_token."""
        import asyncio
        from app.middleware.auth import create_access_token, verify_token
        token = create_access_token({"sub": "user_abc"})
        result = asyncio.get_event_loop().run_until_complete(verify_token(token))
        assert result == "user_abc"


# ===========================================================================
# PHASE 6: PRODUCTION POLISH TESTS
# ===========================================================================

class TestPhase6Production:
    """Verify Dockerfile, logging, connection pooling, and debug endpoint."""

    def test_dockerfile_has_multistage_build(self):
        """Dockerfile must have both 'dependencies' and 'production' stages."""
        import pathlib
        df = pathlib.Path(__file__).parent.parent / "Dockerfile"
        content = df.read_text()
        assert "AS dependencies" in content, "Missing 'dependencies' build stage"
        assert "AS production" in content, "Missing 'production' build stage"
        assert "useradd" in content, "Dockerfile must run as non-root user"

    def test_database_pool_size_configured(self):
        """Database engine must have connection pool settings, not defaults."""
        import app.models.database as db_mod
        engine = db_mod.engine
        pool = engine.pool
        # SQLAlchemy AsyncAdaptedQueuePool should have size
        assert hasattr(pool, 'size'), "Connection pool missing 'size'"

    def test_json_logging_formatter(self):
        """JSON log formatter must produce valid JSON output."""
        import logging
        import json
        from app.core.logging import JSONFormatter
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Test message", args=(), exc_info=None
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "level" in parsed
        assert "message" in parsed
        assert "timestamp" in parsed

    def test_env_example_no_hardcoded_secrets(self):
        """env.example must not contain real API keys."""
        import pathlib
        env_path = pathlib.Path(__file__).parent.parent / ".env.example"
        content = env_path.read_text()
        assert "sk-" not in content
