#!/usr/bin/env bash
#
# sync-oss.sh — One-command sync: assemble + verify + change report.
#
# This is the command you run day to day. In order it:
#   1. assemble.sh   — full re-projection of enterprise HEAD into <OUTPUT_DIR>,
#                      private paths stripped (committed files only).
#   2. verify-oss.sh — HARD GATE over the whole output tree. Nonzero = STOP.
#   3. sync-report.sh — prints exactly what changed since the last sync
#                       (commit-hash aware), split into published vs stripped.
#   4. on PASS only, records HEAD in the gitignored marker <.oss-sync-state> so
#      the NEXT run can show the next delta.
#
# It NEVER commits and NEVER pushes. It only transfers/updates files in the
# output working tree and updates the local marker. You review the diff and
# commit/push manually.
#
# Usage:
#   bash scripts/sync-oss.sh <OUTPUT_DIR> [SOURCE_DIR]
#
# Example:
#   bash scripts/sync-oss.sh ~/repos/opencomplai-public
#   bash scripts/sync-oss.sh ~/repos/opencomplai-public .

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=oss-config.sh
source "$SCRIPT_DIR/oss-config.sh"

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "Usage: bash scripts/sync-oss.sh <OUTPUT_DIR> [SOURCE_DIR]" >&2
  exit 2
fi

OUTPUT_DIR="$1"
SOURCE_DIR="${2:-.}"

# --- 0. Change report BEFORE assembling (baseline vs current HEAD) ----------
echo "==> What changed since the last sync ..."
bash "$SCRIPT_DIR/sync-report.sh" "$SOURCE_DIR" "$OUTPUT_DIR" || true

# --- 1. Assemble (full re-projection) ---------------------------------------
echo ""
echo "==> Assembling public tree ..."
bash "$SCRIPT_DIR/assemble.sh" "$SOURCE_DIR" "$OUTPUT_DIR"

# --- 2. Verify (hard gate) --------------------------------------------------
echo ""
echo "==> Verifying ..."
bash "$SCRIPT_DIR/verify-oss.sh" "$OUTPUT_DIR"

# --- 3. Record the marker (only reached if verify passed) -------------------
HEAD_SHA="$(git -C "$SOURCE_DIR" rev-parse HEAD)"
HEAD_SHORT="$(git -C "$SOURCE_DIR" rev-parse --short HEAD)"
MARKER_PATH="$SOURCE_DIR/$SYNC_STATE_FILENAME"
{
  echo "# opencomplai OSS sync state — gitignored, DO NOT COMMIT to either repo."
  echo "# Enterprise commit whose projection was last assembled + verified."
  echo "# Advisory only: sets the baseline for the next change report; never"
  echo "# decides what is transferred. Regenerated on every successful sync."
  echo "$HEAD_SHA"
  echo "synced_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > "$MARKER_PATH"
echo ""
echo "Recorded sync marker: $SYNC_STATE_FILENAME -> $HEAD_SHORT"

# --- 4. Manual, no-commit next steps ----------------------------------------
cat <<EOF

Ready. This script did NOT commit or push anything — it only updated files.
Review the diff, then commit & push manually:

    cd "$OUTPUT_DIR"
    git add -A
    git status                       # confirm the changed files match the report
    git commit -m "chore: sync from enterprise @ $(date +%Y-%m-%d)

    ${SYNC_TRAILER_KEY}: ${HEAD_SHA}"
    git push origin main

The '${SYNC_TRAILER_KEY}' trailer records provenance in public history and lets
any machine recover the sync baseline even if the local marker is lost.
EOF
