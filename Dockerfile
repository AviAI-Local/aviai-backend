# Build stage
FROM python:3.12-slim AS builder

WORKDIR /app

# Install system dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libsndfile1 \
    ffmpeg \
    espeak-ng \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml ./

# Create virtual environment and install dependencies
RUN uv venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
RUN uv pip install .

# Download NLTK data
RUN python -c "import nltk; nltk.download('punkt_tab', download_dir='/app/nltk_data')"


# Production stage
FROM python:3.12-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libsndfile1 \
    ffmpeg \
    espeak-ng \
    libportaudio2 \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment and NLTK data
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/nltk_data /app/nltk_data

# Environment
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"
ENV NLTK_DATA="/app/nltk_data"
ENV PYTHONUNBUFFERED=1

# Copy application
COPY src/ ./src/
COPY database/ ./database/
COPY scenario/ ./scenario/
COPY alembic/ ./alembic/
COPY alembic.ini ./

# Render uses the PORT environment variable
EXPOSE 10000

# Container health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\", \"10000\")}/docs')" || exit 1

# Run from src
WORKDIR /app/src

# Migrations run inside main.py's lifespan startup, not here — running them
# before uvicorn starts would delay port binding and trip Render's port-scan
# timeout (no separate pre-deploy step on the free tier).
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]