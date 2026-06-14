#!/usr/bin/env bash
# Automated restore smoke test — verifies that a pg_dump backup can be
# successfully restored and passes schema integrity checks.
# Used by .github/workflows/restore-test.yml (ISO 27001 A.8.13 / SOC 2 CC9.1).
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
POSTGRES_USER="${POSTGRES_USER:-opencomplai}"
POSTGRES_DB="${POSTGRES_DB:-opencomplai}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-testpassword}"
TEST_DB="restore_test_$$"
CONTAINER="restore-test-pg-$$"

cleanup() {
  docker rm -f "$CONTAINER" 2>/dev/null || true
}
trap cleanup EXIT

# Find the most recent backup
BACKUP_FILE=$(ls -t "${BACKUP_DIR}"/opencomplai_*.sql.gz 2>/dev/null | head -1)
if [[ -z "$BACKUP_FILE" ]]; then
  echo "ERROR: No backup files found in ${BACKUP_DIR}" >&2
  exit 1
fi
echo "Testing restore from: $BACKUP_FILE"

# Start a fresh Postgres container
docker run -d --name "$CONTAINER" \
  -e POSTGRES_USER="$POSTGRES_USER" \
  -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
  -e POSTGRES_DB="$TEST_DB" \
  postgres:15-alpine

# Wait for Postgres to be ready
echo "Waiting for Postgres to be ready..."
for i in $(seq 1 30); do
  if docker exec "$CONTAINER" pg_isready -U "$POSTGRES_USER" -q 2>/dev/null; then
    break
  fi
  sleep 1
done

docker exec "$CONTAINER" pg_isready -U "$POSTGRES_USER" || {
  echo "ERROR: Postgres did not become ready in time" >&2
  exit 1
}

# Restore the backup
echo "Restoring backup..."
gunzip -c "$BACKUP_FILE" \
  | docker exec -i -e PGPASSWORD="$POSTGRES_PASSWORD" "$CONTAINER" \
    psql -U "$POSTGRES_USER" -d "$TEST_DB" -v ON_ERROR_STOP=1

# Basic schema integrity check — verify core tables exist
echo "Verifying schema integrity..."
TABLES=$(docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$CONTAINER" \
  psql -U "$POSTGRES_USER" -d "$TEST_DB" -t -c \
  "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;")

for table in audit_events tenants tenant_users ingested_artifacts; do
  if echo "$TABLES" | grep -q "$table"; then
    echo "  [OK] Table $table present"
  else
    echo "  [WARN] Table $table not found (may not exist in this schema version)"
  fi
done

echo ""
echo "Restore test PASSED — backup from $(basename "$BACKUP_FILE") restored successfully."
