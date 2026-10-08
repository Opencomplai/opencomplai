# syntax=docker/dockerfile:1
# Base image is pinned by digest. To refresh it, run
# `docker buildx imagetools inspect python:3.11-slim` and use the index digest in both FROM lines.
FROM python:3.11-slim@sha256:6f31d6e9ba2b0a787a3f81c37b004155b87b9efa1b771182bd550c1615745be5 AS builder

WORKDIR /app

RUN pip install --no-cache-dir "uv==0.11.2"

COPY pyproject.toml uv.lock ./
COPY packages/core ./packages/core
COPY services/evidence-vault ./services/evidence-vault

RUN uv sync --frozen --no-dev --package opencomplai-evidence-vault

# ---------------------------------------------------------------------------
FROM python:3.11-slim@sha256:6f31d6e9ba2b0a787a3f81c37b004155b87b9efa1b771182bd550c1615745be5 AS runtime

WORKDIR /app

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    python -m pip uninstall -y pip setuptools wheel && \
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
COPY --chown=1001:1001 sync/seed_demo.py sync/reset_demo.py ./scripts/
COPY --chown=1001:1001 sync/demo ./scripts/demo
COPY --chown=1001:1001 infra/docker/evidence-vault-entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Pre-create the data directories owned by the runtime user. Docker seeds a
# fresh named volume from the image's mount point, so creating these here as
# 1001:1001 makes the volume writable by the non-root user. Without this the
# volume defaults to root:root and CAS writes fail with EACCES.
RUN mkdir -p /data/evidence /data/keys && chown -R 1001:1001 /data

USER 1001

EXPOSE 8002

# /ready (not /health) also confirms the database is actually migrated —
# see the /ready endpoint in main.py and issue #48 finding 11.
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
  CMD curl -fsS http://localhost:8002/ready || exit 1

# entrypoint.sh runs `alembic upgrade head` before exec'ing uvicorn. Only
# this default CMD path is wrapped — demo-seeder (docker-compose.yml) uses
# this same image with an overridden `command:` that replaces this CMD
# outright, so it never runs the migration step itself.
CMD ["/app/entrypoint.sh"]
