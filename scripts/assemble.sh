#!/usr/bin/env bash
#
# assemble.sh — Build the public OSS tree from the enterprise repo.
#
# Camp 2 model: the private enterprise repo is primary; the public OSS repo is a
# derived artifact. This script exports ONLY git-tracked, committed files (via
# `git archive`), then strips the private paths. It never copies the raw working
# tree, so untracked/gitignored junk and stray secrets cannot leak.
#
# Usage:
#   bash scripts/assemble.sh <SOURCE_DIR> <OUTPUT_DIR>
#
# Example:
#   bash scripts/assemble.sh . ~/repos/opencomplai-public
#
# After running, ALWAYS run scripts/verify-oss.sh against <OUTPUT_DIR> before
# pushing anything to the public repo.

set -euo pipefail

# --- Load shared config (single source of truth for the denylist) -----------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=oss-config.sh
source "$SCRIPT_DIR/oss-config.sh"

# --- Argument validation ----------------------------------------------------
if [ "$#" -ne 2 ]; then
  echo "Usage: bash scripts/assemble.sh <SOURCE_DIR> <OUTPUT_DIR>" >&2
  exit 2
fi

SOURCE_DIR="$1"
OUTPUT_DIR="$2"

if [ ! -d "$SOURCE_DIR" ]; then
  echo "FAIL: SOURCE_DIR does not exist: $SOURCE_DIR" >&2
  exit 1
fi

if ! git -C "$SOURCE_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "FAIL: SOURCE_DIR is not a git repository: $SOURCE_DIR" >&2
  exit 1
fi

# --- Refuse a dirty tree ----------------------------------------------------
# We publish committed state only — never a dirty working tree.
if ! git -C "$SOURCE_DIR" diff --quiet || ! git -C "$SOURCE_DIR" diff --cached --quiet; then
  echo "FAIL: SOURCE_DIR has uncommitted changes to tracked files." >&2
  echo "      Commit or stash them first — assemble publishes committed state only." >&2
  exit 1
fi

# --- Prepare a clean OUTPUT_DIR --------------------------------------------
# Preserve the public repo's .git directory if OUTPUT_DIR is an existing clone.
if [ -d "$OUTPUT_DIR/.git" ]; then
  echo "Note: OUTPUT_DIR is an existing git repo — preserving its .git/ and replacing tracked files."
  find "$OUTPUT_DIR" -mindepth 1 -maxdepth 1 ! -name '.git' -exec rm -rf {} +
else
  rm -rf "$OUTPUT_DIR"
  mkdir -p "$OUTPUT_DIR"
fi

# --- Export the tracked tree ------------------------------------------------
echo "Exporting tracked tree from $SOURCE_DIR (HEAD) ..."
git -C "$SOURCE_DIR" archive --format=tar HEAD | tar -x -C "$OUTPUT_DIR"

# --- Strip private directories ----------------------------------------------
for p in "${PRIVATE_DIRS[@]}"; do
  if [ -e "$OUTPUT_DIR/$p" ]; then
    echo "Stripping private path: $p"
    rm -rf "${OUTPUT_DIR:?}/$p"
  fi
done

# --- Strip private files (exact paths) --------------------------------------
for f in "${PRIVATE_FILES[@]}"; do
  if [ -e "$OUTPUT_DIR/$f" ]; then
    echo "Stripping private file: $f"
    rm -f "${OUTPUT_DIR:?}/$f"
  fi
done

# --- Strip private glob patterns --------------------------------------------
for glob in "${PRIVATE_GLOBS[@]}"; do
  while IFS= read -r -d '' match; do
    echo "Stripping private file: ${match#"$OUTPUT_DIR"/}"
    rm -f "$match"
  done < <(find "$OUTPUT_DIR" -type f -name "$glob" -print0)
done

# --- Strip private workflows ------------------------------------------------
for wf in "${PRIVATE_WORKFLOWS[@]}"; do
  if [ -f "$OUTPUT_DIR/$wf" ]; then
    echo "Stripping private workflow: $wf"
    rm -f "$OUTPUT_DIR/$wf"
  fi
done

# --- Prune private members from workspace manifests -------------------------
# Removing a private DIR leaves the private package referenced in monorepo
# workspace files. Drop any workspace member whose path is a private path.
for ws in "${WORKSPACE_MANIFESTS[@]}"; do
  wsfile="$OUTPUT_DIR/$ws"
  [ -f "$wsfile" ] || continue
  tmp="$(mktemp)"
  while IFS= read -r line || [ -n "$line" ]; do
    # Is this a YAML list entry? "  - 'some/path'" / "  - some/path"
    trimmed="${line#"${line%%[![:space:]]*}"}"   # strip leading whitespace
    if [ "${trimmed:0:2}" = "- " ]; then
      member="${trimmed:2}"
      member="${member#\'}"; member="${member%\'}"   # strip surrounding single quotes
      member="${member#\"}"; member="${member%\"}"   # or double quotes
      member="${member%%[[:space:]]*}"               # drop any trailing comment/space
      if oss_is_private "${member%/\*}" || oss_is_private "$member"; then
        # NOTE: stderr — the loop's stdout is redirected into the new file.
        echo "Pruning private workspace member from $ws: $member" >&2
        continue
      fi
    fi
    printf '%s\n' "$line"
  done < "$wsfile" > "$tmp"
  mv "$tmp" "$wsfile"
done

# --- Regenerate the lockfile for the public workspace -----------------------
# After pruning the workspace, the committed pnpm-lock.yaml still contains the
# private package's importer + resolved deps. Regenerate it so it matches only
# the public workspace. lockfile-only: never writes node_modules. Offline first
# (deterministic, from the local store); fall back to network; else warn and let
# verify-oss.sh block. Never fatal here — verify is the hard gate.
if [ -f "$OUTPUT_DIR/pnpm-workspace.yaml" ] && [ -f "$OUTPUT_DIR/pnpm-lock.yaml" ]; then
  if command -v pnpm >/dev/null 2>&1; then
    echo "Regenerating pnpm-lock.yaml for the public workspace ..."
    regen_ok=0
    # Offline first: deterministic, uses the local pnpm store, cannot hang on
    # network (all remaining deps are already resolved in the committed lock).
    if ( cd "$OUTPUT_DIR" && pnpm install --lockfile-only --ignore-scripts --offline >/dev/null 2>&1 ); then
      echo "  pnpm-lock.yaml regenerated (offline)."
      regen_ok=1
    # Bounded online fallback only if the store is cold (e.g. fresh machine).
    elif command -v timeout >/dev/null 2>&1 && \
         ( cd "$OUTPUT_DIR" && timeout 90 pnpm install --lockfile-only --ignore-scripts >/dev/null 2>&1 ); then
      echo "  pnpm-lock.yaml regenerated (online)."
      regen_ok=1
    fi
    if [ "$regen_ok" -ne 1 ]; then
      echo "WARN: could not regenerate pnpm-lock.yaml automatically. Run manually" >&2
      echo "      with network:  ( cd \"$OUTPUT_DIR\" && pnpm install --lockfile-only )" >&2
      echo "      verify-oss.sh will BLOCK the push until private refs are gone." >&2
    fi
    # lockfile-only must not create node_modules; remove any stray dir just in case.
    rm -rf "${OUTPUT_DIR:?}/node_modules"
  else
    echo "WARN: pnpm not found — cannot regenerate pnpm-lock.yaml. verify-oss.sh" >&2
    echo "      will BLOCK if private references remain." >&2
  fi
fi

# --- Summary ----------------------------------------------------------------
FILE_COUNT=$(find "$OUTPUT_DIR" -type f -not -path "*/.git/*" | wc -l | tr -d ' ')
echo ""
echo "Assembled $FILE_COUNT files → $OUTPUT_DIR"
echo "Next: run 'bash scripts/verify-oss.sh $OUTPUT_DIR' before pushing."
