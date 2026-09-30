# ============================================================
# FabFlow AI — Backend Dockerfile
# ============================================================
# Multi-stage build:
#   Stage 1 (builder) : Install Python deps into a venv
#   Stage 2 (runtime) : Slim runtime image copying only the venv
#
# Build:
#   docker build -t fabflow-ai:latest .
#
# Run (standalone, SQLite):
#   docker run -p 8000:8000 fabflow-ai:latest
#
# Run (with PostgreSQL via docker-compose):
#   docker-compose up --build
# ============================================================

# ─── Stage 1: dependency builder ─────────────────────────────
FROM python:3.12-slim AS builder

# System build deps for psycopg2 and OR-Tools native libs
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Create isolated virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install Python dependencies (layer-cached unless requirements.txt changes)
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ─── Stage 2: lean runtime image ─────────────────────────────
FROM python:3.12-slim AS runtime

LABEL maintainer="FabFlow AI Engineering"
LABEL version="1.0.0"
LABEL description="Intelligent Semiconductor Fab Scheduling & Optimization Platform"

# Runtime system deps only (libpq for psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy the virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN groupadd --gid 1001 fabflow \
 && useradd --uid 1001 --gid 1001 --shell /bin/bash --create-home fabflow

WORKDIR /app

# Copy application source
COPY --chown=fabflow:fabflow . .

# Switch to non-root user
USER fabflow

# ─── Environment defaults (override via docker-compose / K8s) ─
ENV DATABASE_URL="sqlite:///./fabflow_dev.db"
ENV SQL_ECHO="false"
ENV DB_POOL_SIZE="10"
ENV DB_MAX_OVERFLOW="20"

# Expose FastAPI port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"

# ─── Entry point ──────────────────────────────────────────────
CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info", \
     "--proxy-headers"]
