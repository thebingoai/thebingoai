# Stage 1: Build dependencies
FROM python:3.12-slim AS builder
RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Stage 2: Runtime
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY backend/ ./backend/
COPY alembic/ ./alembic/
COPY alembic.ini .
RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/data/schemas /app/data/contexts \
    && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/health')"
CMD ["sh", "-c", "alembic upgrade head && uvicorn backend.main:app --host ${BACKEND_HOST:-0.0.0.0} --port ${BACKEND_PORT:-8000}"]
