# syntax=docker/dockerfile:1
FROM python:3.11-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY packages/core ./packages/core
COPY services/evidence-vault ./services/evidence-vault

RUN uv sync --package opencomplai-evidence-vault

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
    PYTHONPATH="/app/services/evidence-vault/src:/app/packages/core/src" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --chown=1001:1001 services/evidence-vault/src ./services/evidence-vault/src
COPY --chown=1001:1001 services/evidence-vault/alembic.ini ./services/evidence-vault/alembic.ini
COPY --chown=1001:1001 services/evidence-vault/migrations ./services/evidence-vault/migrations
COPY --chown=1001:1001 packages/core/src ./packages/core/src
COPY --chown=1001:1001 scripts ./scripts

# Pre-create the data directories owned by the runtime user. Docker seeds a
# fresh named volume from the image's mount point, so creating these here as
# 1001:1001 makes the volume writable by the non-root user. Without this the
# volume defaults to root:root and CAS writes fail with EACCES.
RUN mkdir -p /data/evidence /data/keys && chown -R 1001:1001 /data

USER 1001

EXPOSE 8002

HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD curl -fsS http://localhost:8002/health || exit 1

CMD ["uvicorn", "opencomplai_evidence_vault.main:app", "--host", "0.0.0.0", "--port", "8002"]
