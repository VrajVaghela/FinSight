# FinSight Conversational AI: Gemini Integration and E2E Testing Guide

This module is wired to Gemini through LangChain. Do not configure OpenAI keys or OpenAI model names for Member 4.

## Implementation Summary

The Gemini integration lives in `app/core/llm_client.py`:

```python
import os
from langchain_google_genai import ChatGoogleGenerativeAI

API_KEY = (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_API_KEY")
    or os.environ["GOOGLE_GENAI_API_KEY"]
)
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0.2"))

llm = ChatGoogleGenerativeAI(
    model=MODEL,
    temperature=TEMPERATURE,
    google_api_key=API_KEY
)
```

The pipeline modules now receive a LangChain `llm` object and call `invoke()` / `ainvoke()`:

```python
response = await process_query(
    query=standalone_query,
    chunks=reranked_chunks,
    project_id=request.project_id,
    language=request.language,
    llm=gemini_llm,
    db_conn=db_conn,
    qdrant_client=qdrant_client,
)
```

Updated files:

- `app/core/llm_client.py`: Gemini factory, text normalization, JSON parsing.
- `app/core/refusal_gate.py`: Gate 3 and Gate 4 now use the injected Gemini LangChain model.
- `app/core/reasoning_engine.py`: PAL router, PAL code generation, final generation, and `process_query()` use Gemini.
- `app/core/glean_verifier.py`: guideline checks and self-correction use Gemini.
- `app/main.py`: local FastAPI `/api/chat` SSE harness for manual testing.
- `pyproject.toml`: adds `langchain-google-genai`, `langchain`, `fastapi`, `uvicorn`, `python-dotenv`, and test dependencies.

## 1. Setup

Create `conversationalai/.env`:

```env
GEMINI_API_KEY=your_google_gemini_api_key
# GOOGLE_API_KEY=your_google_gemini_api_key       # also supported
# GOOGLE_GENAI_API_KEY=your_google_gemini_api_key # also supported

GEMINI_MODEL=gemini-2.5-flash
GEMINI_TEMPERATURE=0.2

GATE3_CONFIDENCE_THRESHOLD=0.5
GATE4_MIN_GROUNDED_RATIO=0.8
PAL_TIMEOUT_SECONDS=5
PAL_MAX_RETRIES=3
GLEAN_MAX_RETRIES=2
QDRANT_COLLECTION=document_chunks
```

Install dependencies from `conversationalai/`:

```bash
pip install langchain langchain-google-genai fastapi "uvicorn[standard]" python-dotenv asyncpg qdrant-client spacy pytest pytest-asyncio
```

Run unit tests:

```bash
pytest app/tests -q
```

Expected:

```text
15 passed
```

## 2. Start The FastAPI Server

From `conversationalai/`:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Health check:

```bash
curl http://localhost:8000/healthz
```

Expected:

```json
{"status":"ok"}
```

## 3. API Call Format

For local Member 4 testing, `/api/chat` accepts retrieved chunks directly. In the full FinSight backend, Member 3 can keep the public request to `query`, `project_id`, `language`, and `session_id`, then inject retrieved chunks server-side before calling `process_query()`.

```json
{
  "query": "What was total income in H1-FY26?",
  "project_id": "local-demo",
  "language": "English",
  "session_id": "manual-test-001",
  "chunks": [
    {
      "chunk_id": "chunk-1",
      "raw_text": "Total income for H1-FY26 was Rs 1,234 Cr.",
      "page_number": 3,
      "section_header": "Financial Highlights",
      "reranker_score": 0.97,
      "bounding_box": {"x": 0.12, "y": 0.34, "w": 0.76, "h": 0.04}
    }
  ]
}
```

The response is Server-Sent Events:

```text
data: {"type":"started",...}

data: {"type":"answer",...}

data: {"type":"done",...}
```

## 4. Manual Tests

### Test A: Standard Narrative

Goal: Gate 3 passes, PAL routes to narrative, answer includes `[Source N]`, GLEAN passes, Gate 4 passes.

```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What was total income in H1-FY26?",
    "project_id": "local-demo",
    "language": "English",
    "session_id": "test-a",
    "chunks": [
      {
        "chunk_id": "income-h1fy26",
        "raw_text": "Total income for H1-FY26 was Rs 1,234 Cr.",
        "page_number": 3,
        "section_header": "Financial Highlights",
        "reranker_score": 0.97,
        "bounding_box": {"x": 0.12, "y": 0.34, "w": 0.76, "h": 0.04}
      }
    ]
  }'
```

Expected SSE shape:

```text
data: {"type":"started","session_id":"test-a"}
data: {"type":"chunk","source_number":1,...}
data: {"type":"answer","text":"...Rs 1,234 Cr [Source 1]...","ui_component_hint":"Paragraph","glean_verified":true,"gate4_passed":true,...}
data: {"type":"done","latency":{...}}
```

Pass checks:

- No `refusal` event.
- `answer.text` contains `[Source 1]`.
- `glean_verified` is `true`.
- `gate4_passed` is `true`.

### Test B: Math / PAL Trigger

Goal: PAL router chooses `PAL`, executes generated Python, and emits `pal_execution`.

```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What was the CAGR of revenue from FY22 to FY26?",
    "project_id": "local-demo",
    "language": "English",
    "session_id": "test-b",
    "chunks": [
      {
        "chunk_id": "revenue-fy22",
        "raw_text": "Revenue in FY22 was Rs 800 Cr.",
        "page_number": 4,
        "section_header": "Revenue Trend",
        "reranker_score": 0.96,
        "bounding_box": {"x": 0.11, "y": 0.28, "w": 0.70, "h": 0.04}
      },
      {
        "chunk_id": "revenue-fy26",
        "raw_text": "Revenue in FY26 was Rs 1,400 Cr.",
        "page_number": 5,
        "section_header": "Revenue Trend",
        "reranker_score": 0.96,
        "bounding_box": {"x": 0.11, "y": 0.35, "w": 0.70, "h": 0.04}
      }
    ]
  }'
```

Expected SSE shape:

```text
data: {"type":"pal_execution","code":"...print(...)...","result":"...%","verified":true,"attempts":1}
data: {"type":"answer","text":"... [Source 1][Source 2] ...","ui_component_hint":"CodeBlock",...}
data: {"type":"done","latency":{...}}
```

Pass checks:

- `pal_execution` is present.
- `pal_execution.verified` is `true`.
- `pal_execution.result` is a numeric result, usually around `15%`.
- `ui_component_hint` is `CodeBlock`.

### Test C: Gate 3 Refusal

Goal: Off-topic/private-info query is blocked before PAL, generation, GLEAN, or Gate 4.

```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the CEO'\''s personal email address?",
    "project_id": "local-demo",
    "language": "English",
    "session_id": "test-c",
    "chunks": [
      {
        "chunk_id": "revenue-only",
        "raw_text": "Revenue grew by 23% year over year.",
        "page_number": 2,
        "section_header": "Performance",
        "reranker_score": 0.91
      }
    ]
  }'
```

Expected SSE shape:

```text
data: {"type":"started","session_id":"test-c"}
data: {"type":"refusal","reason":"level_3_grader","message":"Not found in the document."}
data: {"type":"done","latency":{"gate3_ms":...}}
```

Pass checks:

- `refusal.reason` is `level_3_grader`.
- No `pal_execution` event.
- No substantive `answer` event.

### Test D: GLEAN Catch / Forced Hallucination

Goal: Force a fabricated number into the draft answer and verify GLEAN blocks it at Level 4 compliance.

Stop the server, then restart it with the local test injection enabled and GLEAN retries disabled:

PowerShell:

```powershell
$env:FINSIGHT_TEST_FORCE_HALLUCINATION="1"
$env:GLEAN_MAX_RETRIES="0"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Bash:

```bash
FINSIGHT_TEST_FORCE_HALLUCINATION=1 GLEAN_MAX_RETRIES=0 \
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Run:

```bash
curl -N -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Summarize the H1-FY26 financial highlights.",
    "project_id": "local-demo",
    "language": "English",
    "session_id": "test-d",
    "chunks": [
      {
        "chunk_id": "safe-financials",
        "raw_text": "Total income for H1-FY26 was Rs 1,234 Cr. Revenue grew by 23% year over year.",
        "page_number": 3,
        "section_header": "Financial Highlights",
        "reranker_score": 0.97
      }
    ]
  }'
```

Expected SSE shape:

```text
data: {"type":"refusal","reason":"glean_verifier","message":"Answer failed compliance verification after multiple attempts."}
data: {"type":"done","latency":{...}}
```

Pass checks:

- `refusal.reason` is `glean_verifier`.
- The final answer is not streamed.
- Server logs or Gemini traces should show the injected unsupported claim: `CEO received a Rs 5 Cr bonus`.

After the test, disable the injection:

PowerShell:

```powershell
Remove-Item Env:\FINSIGHT_TEST_FORCE_HALLUCINATION
Remove-Item Env:\GLEAN_MAX_RETRIES
```

Bash:

```bash
unset FINSIGHT_TEST_FORCE_HALLUCINATION
unset GLEAN_MAX_RETRIES
```

## 5. Production Integration Notes

Member 3 should construct Gemini once at application startup:

```python
import os
from langchain_google_genai import ChatGoogleGenerativeAI

API_KEY = (
    os.getenv("GEMINI_API_KEY")
    or os.getenv("GOOGLE_API_KEY")
    or os.environ["GOOGLE_GENAI_API_KEY"]
)
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0.2"))

llm = ChatGoogleGenerativeAI(
    model=MODEL,
    temperature=TEMPERATURE,
    google_api_key=API_KEY
)
```

Then pass it into Member 4:

```python
final = await process_query(
    query=standalone_query,
    chunks=reranked_chunks,
    project_id=project_id,
    language=language,
    llm=llm,
    db_conn=db_conn,
    qdrant_client=qdrant_client,
)
```

This keeps all gates, PAL, generation, citation verification, GLEAN, and Gate 4 on the same Gemini model.
