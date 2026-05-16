# Task Tracker: FinSight AI Backend & Infrastructure

- [x] **Phase 1: Foundation (Hours 0-6)**
    - [x] 1.1 Init repo: `uv init`, create pyproject.toml
    - [x] 1.2 Write docker-compose.yml (6 services)
    - [x] 1.3 Create SQLAlchemy models (orm.py) + Alembic migration
    - [x] 1.4 Create Pydantic schemas (schemas.py)
    - [x] 1.5 Build FastAPI skeleton: main.py + health endpoint
    - [x] 1.6 Build /api/projects CRUD endpoints
    - [x] 1.7 Build /api/projects/{id}/files upload endpoint
    - [x] 1.8 Set up Celery app + Redis broker
    - [x] 1.9 Wire Member 2's ingestion task trigger

- [/] **Phase 2: Chat Pipeline Core (Hours 6-14)**
    - [x] 2.1 Implement QueryRewriter (memory_manager.py)
    - [x] 2.2 Implement ProjectMemory
    - [x] 2.3 Build SSEFormatter (streaming.py)
    - [x] 2.4 Build chat_service.py orchestrator skeleton
    - [x] 2.5 Wire /api/chat SSE endpoint
    - [ ] 2.6 Integrate Member 1's retrieval module
    - [ ] 2.7 Wire RefusalGate levels 1-3
    - [x] 2.8 Implement SLM Compression

- [/] **Phase 3: PAL, Citations, GLEAN (Hours 14-20)**
    - [ ] 3.1 Integrate PAL Router (Member 4)
    - [ ] 3.2 Wire PAL execution SSE events
    - [ ] 3.3 Integrate CitationEngine (Member 4)
    - [ ] 3.4 Integrate GLEAN Verifier (Gate 4)
    - [x] 3.5 UI component decision logic
    - [x] 3.6 Implement prompt caching

- [x] **Phase 4: Memory, Multi-turn, Multilingual (Hours 20-28)**
    - [x] 4.1 Implement MEM1Adapter
    - [x] 4.2 Wire full conversational flow
    - [x] 4.3 Language detection (langdetect)
    - [x] 4.4 MEM1 state update logic
    - [x] 4.5 Conversation persistence

- [x] **Phase 5: Voice & Polish (Hours 28-36)**
    - [x] 5.1 VoiceHandler (Whisper STT + TTS)
    - [x] 5.2 WebSocket /ws/voice endpoint
    - [x] 5.3 Barge-in support
    - [x] 5.4 /api/tts REST endpoint
    - [x] 5.5 JWT auth middleware

- [x] **Phase 6: Production Polish (Hours 36-42)**
    - [x] 6.1 Multi-stage Dockerfile
    - [x] 6.2 Test docker compose up end-to-end
    - [x] 6.3 Structured logging (JSON)
    - [x] 6.4 Performance: pooling, timeouts
    - [x] 6.5 Integration tests (T1-T5)
    - [x] 6.6 /api/retrieval/debug endpoint
