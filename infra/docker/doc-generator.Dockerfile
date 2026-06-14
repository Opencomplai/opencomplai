# syntax=docker/dockerfile:1
FROM python:3.11-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY packages/core ./packages/core
COPY services/doc-generator ./services/doc-generator

RUN uv sync --package opencomplai-doc-generator

# ---------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    rm -rf /var/lib/apt/lists/* && \
    addgroup --gid 1001 opencomplai && \
    adduser --uid 1001 --gid 1001 --no-create-home opencomplai

COPY --from=builder --chown=1001:1001 /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/services/doc-generator/src:/app/packages/core/src" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --chown=1001:1001 services/doc-generator/src ./services/doc-generator/src
COPY --chown=1001:1001 packages/core/src ./packages/core/src

USER 1001

EXPOSE 8003

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD curl -fsS http://localhost:8003/health || exit 1

CMD ["uvicorn", "opencomplai_doc_generator.main:app", "--host", "0.0.0.0", "--port", "8003"]
