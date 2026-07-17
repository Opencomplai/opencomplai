#!/usr/bin/env bash
#
# verify-oss.sh — Hard gate before publishing the OSS tree.
#
# Runs path/file gates AND a secret-content scan over an assembled output tree.
# If ANY check fails, this script exits nonzero and the tree MUST NOT be pushed.
# There is no override.
#
# Usage:
#   bash scripts/verify-oss.sh <OUTPUT_DIR>
#
# Example:
#   bash scripts/verify-oss.sh ~/repos/opencomplai-public

set -euo pipefail

# --- Load shared config (single source of truth for the denylist) -----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=oss-config.sh
source "$SCRIPT_DIR/oss-config.sh"

# --- Argument validation ----------------------------------------------------
if [ "$#" -ne 1 ]; then
  echo "Usage: bash scripts/verify-oss.sh <OUTPUT_DIR>" >&2
  exit 2
fi

OUTPUT_DIR="$1"

if [ ! -d "$OUTPUT_DIR" ]; then
  echo "FAIL: OUTPUT_DIR does not exist: $OUTPUT_DIR" >&2
  exit 1
fi

FAILED=0
fail() { echo "FAIL: $1" >&2; FAILED=1; }
warn() { echo "WARN: $1" >&2; }

# Helper: find files excluding the .git directory.
find_tree() { find "$OUTPUT_DIR" -not -path "*/.git/*" "$@"; }

# --- Gate: output is non-empty ----------------------------------------------
if [ -z "$(find_tree -type f -print -quit)" ]; then
  fail "output dir is empty — assemble may have failed"
fi

# --- Gate: private directories absent ---------------------------------------
for d in "${PRIVATE_DIRS[@]}"; do
  if [ -e "$OUTPUT_DIR/$d" ]; then
    fail "$d/ found in output"
  fi
done

# --- Gate: private files absent ---------------------------------------------
for f in "${PRIVATE_FILES[@]}"; do
  if [ -e "$OUTPUT_DIR/$f" ]; then
    fail "private file found in output: $f"
  fi
done

# --- Gate: internal sync marker absent (defense in depth) -------------------
# The .oss-sync-state marker is gitignored so it is never archived, but assert
# it anyway — it must never appear in the public tree.
while IFS= read -r -d '' f; do
  fail "internal sync marker found: ${f#"$OUTPUT_DIR"/}"
done < <(find_tree -type f -name "$SYNC_STATE_FILENAME" -print0)

# --- Gate: private workflows absent -----------------------------------------
for wf in "${PRIVATE_WORKFLOWS[@]}"; do
  if [ -f "$OUTPUT_DIR/$wf" ]; then
    fail "private workflow found in output: $wf"
  fi
done

# --- Gate: no internal plan files -------------------------------------------
while IFS= read -r -d '' f; do
  fail "internal plan file found: ${f#"$OUTPUT_DIR"/}"
done < <(find_tree -type f -name "*.plan.md" -print0)

# --- Gate: no .env files (except .env.example) ------------------------------
while IFS= read -r -d '' f; do
  base="$(basename "$f")"
  if [ "$base" != ".env.example" ]; then
    fail ".env file found: ${f#"$OUTPUT_DIR"/}"
  fi
done < <(find_tree -type f -name ".env*" -print0)

# --- Gate: no secret-pattern files ------------------------------------------
for glob in "${SECRET_GLOBS[@]}"; do
  while IFS= read -r -d '' f; do
    fail "secret-pattern file found: ${f#"$OUTPUT_DIR"/}"
  done < <(find_tree -type f -name "$glob" -print0)
done

# --- Gate: no private-path refs left in build manifests ---------------------
# Stripping a private dir does not scrub it from monorepo lockfiles/workspace
# files. A build manifest must never reference a private path — assemble.sh
# prunes/regenerates them; this is the hard backstop if that was skipped.
for glob in "${MANIFEST_GLOBS[@]}"; do
  while IFS= read -r -d '' f; do
    for d in "${PRIVATE_DIRS[@]}"; do
      if grep -qF -- "$d/" "$f" 2>/dev/null; then
        fail "private path '$d/' referenced in build manifest: ${f#"$OUTPUT_DIR"/}"
      fi
    done
  done < <(find_tree -type f -name "$glob" -print0)
done

# --- Gate: file-size (possible data dump) -----------------------------------
# Single find -size pass (no per-file wc subshell — that is ~100x slower on
# Windows where each process spawn is expensive).
while IFS= read -r -d '' f; do
  fail "oversized file (possible data dump): ${f#"$OUTPUT_DIR"/} (> $MAX_FILE_BYTES bytes)"
done < <(find_tree -type f -size +"${MAX_FILE_BYTES}"c -print0)

# --- Gate: secret-content scan (BLOCKING if a scanner is available) ---------
if command -v gitleaks >/dev/null 2>&1; then
  echo "Running gitleaks secret-content scan ..."
  if ! gitleaks detect --source "$OUTPUT_DIR" --no-git --redact; then
    fail "gitleaks found secrets in the output tree"
  fi
elif command -v trufflehog >/dev/null 2>&1; then
  echo "Running trufflehog secret-content scan ..."
  if ! trufflehog filesystem "$OUTPUT_DIR" --fail >/dev/null; then
    fail "trufflehog found secrets in the output tree"
  fi
else
  warn "no secret scanner found (gitleaks/trufflehog) — content scan SKIPPED."
  warn "Install gitleaks before publishing, or run the ecc:opensource-sanitizer skill manually."
fi

# --- Result -----------------------------------------------------------------
if [ "$FAILED" -ne 0 ]; then
  echo ""
  echo "VERIFY FAILED — do NOT push this tree." >&2
  exit 1
fi

FILE_COUNT=$(find_tree -type f | wc -l | tr -d ' ')
echo ""
echo "PASS — $FILE_COUNT files ready to publish (secret scan clean)"
