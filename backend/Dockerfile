# backend/Dockerfile

# ---- Stage 1: Dependencies ----
FROM python:3.12-slim AS dependencies

RUN pip install uv
WORKDIR /app

COPY pyproject.toml ./
RUN uv venv .venv && uv pip install --python .venv/bin/python -r pyproject.toml

# ---- Stage 2: Production ----
FROM python:3.12-slim AS production

# System deps for sentence-transformers, audio processing, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy installed packages from dependencies stage
COPY --from=dependencies /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p /app/uploads

# Non-root user
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--loop", "uvloop", "--http", "httptools"]
