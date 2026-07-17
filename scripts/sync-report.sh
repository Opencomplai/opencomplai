#!/usr/bin/env bash
#
# sync-report.sh — Commit-hash-aware "what changed since last sync" report.
#
# READ-ONLY and ADVISORY. It never transfers, deletes, or commits anything. It
# answers one question: "given the last enterprise commit we synced to the
# public repo, which files changed since then, and which of those will actually
# appear in the public sync vs. get stripped as private?"
#
# It does NOT decide what gets transferred. assemble.sh always does a full
# re-projection of HEAD and verify-oss.sh gates the whole tree — that is what
# keeps the public tree a pure, leak-proof function of enterprise HEAD. This
# report is purely for the human reviewer's situational awareness.
#
# Baseline resolution order (first hit wins):
#   1. the local marker file  <SOURCE_DIR>/.oss-sync-state   (see oss-config.sh)
#   2. the 'OSS-Synced-From:' trailer in the public repo's git log (if OUTPUT_DIR
#      given) — survives losing the local marker / switching machines
#   3. none  -> treated as an initial sync (no baseline to diff against)
#
# Usage:
#   bash scripts/sync-report.sh <SOURCE_DIR> [OUTPUT_DIR]
#
# Example:
#   bash scripts/sync-report.sh . ~/repos/opencomplai-public

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=oss-config.sh
source "$SCRIPT_DIR/oss-config.sh"

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
  echo "Usage: bash scripts/sync-report.sh <SOURCE_DIR> [OUTPUT_DIR]" >&2
  exit 2
fi

SOURCE_DIR="$1"
OUTPUT_DIR="${2:-}"

if ! git -C "$SOURCE_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "FAIL: SOURCE_DIR is not a git repository: $SOURCE_DIR" >&2
  exit 1
fi

HEAD_SHA="$(git -C "$SOURCE_DIR" rev-parse HEAD)"
HEAD_SHORT="$(git -C "$SOURCE_DIR" rev-parse --short HEAD)"
MARKER_PATH="$SOURCE_DIR/$SYNC_STATE_FILENAME"

# --- Resolve baseline SHA ---------------------------------------------------
BASELINE=""
BASELINE_SRC=""

# 1. local marker file (first 40-hex token)
if [ -f "$MARKER_PATH" ]; then
  cand="$(grep -oE '[0-9a-f]{40}' "$MARKER_PATH" | head -n1 || true)"
  if [ -n "$cand" ]; then
    BASELINE="$cand"
    BASELINE_SRC="local marker ($SYNC_STATE_FILENAME)"
  fi
fi

# 2. fallback: OSS-Synced-From trailer in the public repo's history
if [ -z "$BASELINE" ] && [ -n "$OUTPUT_DIR" ] && \
   git -C "$OUTPUT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  cand="$(git -C "$OUTPUT_DIR" log -n1 --pretty=%B 2>/dev/null \
            | grep -iE "^${SYNC_TRAILER_KEY}:" \
            | grep -oE '[0-9a-f]{7,40}' | head -n1 || true)"
  if [ -n "$cand" ]; then
    BASELINE="$cand"
    BASELINE_SRC="public commit trailer (${SYNC_TRAILER_KEY})"
  fi
fi

echo "============================================================"
echo " OSS sync change report"
echo "============================================================"
echo " Enterprise HEAD : $HEAD_SHORT  ($(git -C "$SOURCE_DIR" log -1 --pretty=%s))"

# --- No baseline: initial sync ----------------------------------------------
if [ -z "$BASELINE" ]; then
  echo " Last synced     : (none found — treating this as an INITIAL full sync)"
  echo ""
  echo " No baseline commit is recorded, so there is nothing to diff against."
  echo " This sync publishes the full current projection of HEAD."
  echo "============================================================"
  exit 0
fi

# --- Validate baseline is a known ancestor ----------------------------------
if ! git -C "$SOURCE_DIR" cat-file -e "${BASELINE}^{commit}" 2>/dev/null; then
  echo " Last synced     : $BASELINE  (from $BASELINE_SRC)"
  echo ""
  echo " WARN: that commit is not in this repo (shallow clone or rewritten"
  echo "       history). Cannot compute an incremental report — this run still"
  echo "       does a full, fully-verified re-projection, so the output is"
  echo "       correct regardless. Review the public repo's own git diff."
  echo "============================================================"
  exit 0
fi

BASE_SHORT="$(git -C "$SOURCE_DIR" rev-parse --short "$BASELINE")"
echo " Last synced     : $BASE_SHORT  (from $BASELINE_SRC)"

if [ "$(git -C "$SOURCE_DIR" rev-parse "$BASELINE")" = "$HEAD_SHA" ]; then
  echo ""
  echo " Already up to date — HEAD == last synced commit. Nothing changed."
  echo "============================================================"
  exit 0
fi

if ! git -C "$SOURCE_DIR" merge-base --is-ancestor "$BASELINE" HEAD 2>/dev/null; then
  echo ""
  echo " WARN: last-synced commit is not an ancestor of HEAD (history diverged/"
  echo "       rewritten). Showing a plain diff anyway; rely on the public repo's"
  echo "       own git diff as ground truth. The full re-projection is still safe."
fi

# --- Commits in range -------------------------------------------------------
echo ""
echo " Commits since last sync ($BASE_SHORT..$HEAD_SHORT):"
git -C "$SOURCE_DIR" log --oneline --no-decorate "${BASELINE}..HEAD" | sed 's/^/   /'

# --- File-level change classification ---------------------------------------
# --no-renames: a rename is reported as separate D(old) + A(new). This is the
# SAFE degradation — if the new path is private and the old was public, the old
# public file is a real deletion the public tree must reflect, never a silently
# skipped rename.
published=()
stripped=()
while IFS=$'\t' read -r status path _; do
  [ -z "${status:-}" ] && continue
  code="${status:0:1}"
  case "$code" in
    A) verb="added   " ;;
    M) verb="modified" ;;
    D) verb="deleted " ;;
    T) verb="typechg " ;;
    *) verb="$code       " ;;
  esac
  if oss_is_private "$path"; then
    stripped+=("$verb  $path")
  else
    published+=("$verb  $path")
  fi
done < <(git -C "$SOURCE_DIR" diff --name-status --no-renames "${BASELINE}..HEAD")

echo ""
echo " Changes that WILL appear in the public sync (${#published[@]}):"
if [ "${#published[@]}" -eq 0 ]; then
  echo "   (none — all changes are in private/stripped paths)"
else
  printf '   %s\n' "${published[@]}"
fi

echo ""
echo " Changes STRIPPED as private — no public effect (${#stripped[@]}):"
if [ "${#stripped[@]}" -eq 0 ]; then
  echo "   (none)"
else
  printf '   %s\n' "${stripped[@]}"
fi

echo "============================================================"
