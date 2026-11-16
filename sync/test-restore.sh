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

# Wait for Postgres to be ready. Check over TCP: while the image initialises the
# database it runs a temporary server that listens on the unix socket only and is
# then stopped and restarted, so a socket check can pass just before the real
# server restarts and drops the restore's connection.
echo "Waiting for Postgres to be ready..."
for i in $(seq 1 30); do
  if docker exec "$CONTAINER" pg_isready -h 127.0.0.1 -U "$POSTGRES_USER" -q 2>/dev/null; then
    break
  fi
  sleep 1
done

docker exec "$CONTAINER" pg_isready -h 127.0.0.1 -U "$POSTGRES_USER" || {
  echo "ERROR: Postgres did not become ready in time" >&2
  exit 1
}

# Roles are cluster-wide and not part of a pg_dump, but the dump grants privileges
# to them (evidence_vault_admin, evidence_vault_app), so a new server needs them
# first. The workflow writes them beside the dump with pg_dumpall --globals-only.
# The new server already has the bootstrap role, so "already exists" is expected
# here; a role that is really missing fails the restore below, which stops on error.
GLOBALS_FILE="${BACKUP_DIR}/globals.sql"
if [[ -f "$GLOBALS_FILE" ]]; then
  echo "Restoring roles..."
  docker exec -i -e PGPASSWORD="$POSTGRES_PASSWORD" "$CONTAINER" \
    psql -U "$POSTGRES_USER" -d postgres -q < "$GLOBALS_FILE" 2>&1 \
    | grep -v "already exists" || true
else
  echo "NOTE: no globals.sql beside the backup; roles are not restored"
fi

# Restore the backup
echo "Restoring backup..."
gunzip -c "$BACKUP_FILE" \
  | docker exec -i -e PGPASSWORD="$POSTGRES_PASSWORD" "$CONTAINER" \
    psql -U "$POSTGRES_USER" -d "$TEST_DB" -v ON_ERROR_STOP=1

# Schema integrity check. The restored table set must be the table set the backup
# was taken from: the workflow writes it to source_tables.txt beside the dump, so
# a migration that adds a table cannot make this check stale. Whatever the source,
# the evidence-vault baseline tables must be there, so an empty or truncated
# restore can never pass.
echo "Verifying schema integrity..."
BASELINE_TABLES="alembic_version dossier_index evidence_objects ledger_events"
ACTUAL_TABLES=$(docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" "$CONTAINER" \
  psql -U "$POSTGRES_USER" -d "$TEST_DB" -t -A -c \
  "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename;" \
  | tr '\n' ' ' | xargs)
echo "Actual tables:   $ACTUAL_TABLES"

for t in $BASELINE_TABLES; do
  if [[ " $ACTUAL_TABLES " != *" $t "* ]]; then
    echo "ERROR: restored schema lacks the baseline table $t" >&2
    exit 1
  fi
done

SOURCE_TABLES_FILE="${BACKUP_DIR}/source_tables.txt"
if [[ -f "$SOURCE_TABLES_FILE" ]]; then
  EXPECTED_TABLES=$(tr '\n' ' ' < "$SOURCE_TABLES_FILE" | xargs)
  echo "Expected tables: $EXPECTED_TABLES"
  if [[ "$ACTUAL_TABLES" != "$EXPECTED_TABLES" ]]; then
    echo "ERROR: restored schema does not match the database the backup was taken from" >&2
    exit 1
  fi
else
  echo "NOTE: no source_tables.txt beside the backup; only the baseline tables were checked"
fi

echo ""
echo "Restore test PASSED — backup from $(basename "$BACKUP_FILE") restored successfully."
