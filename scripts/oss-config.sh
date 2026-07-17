#!/usr/bin/env bash
#
# oss-config.sh — Single source of truth for the OSS publish pipeline.
#
# This file is SOURCED by assemble.sh, verify-oss.sh, and sync-oss.sh. It is not
# meant to be run directly. Edit HERE (and only here) when:
#   - adding/removing a private directory or file
#   - changing which secret-pattern files are forbidden
#   - adjusting the max file-size limit
#
# Keeping the denylist in one place is what prevents assemble/verify from
# drifting out of sync.

# --- Private directories ----------------------------------------------------
# Tracked directories that must be stripped from the public tree AND must never
# appear in a verified output tree.
#
# .github/ is excluded wholesale: the enterprise CI (workflows, issue templates,
# dependabot, etc.) is internal. The public repo manages its own .github/.
PRIVATE_DIRS=(
  "dashboard-saas"      # SaaS dashboard app, its API docs and config
  "isms"
  "compliance-reports"
  ".claude"
  ".github"             # all enterprise CI/issue templates — not published
)

# --- Private files (exact, root-relative paths) -----------------------------
# Specific files to strip from the output root.
PRIVATE_FILES=(
  "vercel.json"         # internal docs-site deploy config
)

# --- Private file globs ------------------------------------------------------
# File patterns to strip anywhere in the tree (e.g. internal plans).
PRIVATE_GLOBS=(
  "*.plan.md"
)

# --- Private workflow files --------------------------------------------------
# Paths (relative to the output root) of CI workflows that must not be published.
# Redundant now that all of .github/ is excluded above, but kept as a
# defense-in-depth gate in verify-oss.sh in case .github/ is ever re-included.
PRIVATE_WORKFLOWS=(
  ".github/workflows/dashboard-saas-ci.yml"
  ".github/workflows/risk-register-review.yml"
)

# --- Secret-pattern files ----------------------------------------------------
# File extensions/names that must NOT exist in the output (.env.example is OK,
# and is handled explicitly by verify-oss.sh).
SECRET_GLOBS=(
  "*.pem" "*.key" "*.p12" "*.pfx"
  "*.tfstate" "*.tfstate.backup"
  "*.db" "*.sqlite" "*.sqlite3"
  "*.sql" "*.dump"
)

# --- Build manifests (workspace/lockfiles) ----------------------------------
# Monorepo manifests pin dependencies for ALL workspace packages, including
# private ones. Stripping a private directory does NOT remove its footprint from
# these files — the private package's importer/dep graph stays behind and leaks
# (e.g. dashboard-saas's Next.js dep tree inside pnpm-lock.yaml). So:
#   * assemble.sh prunes private members from WORKSPACE_MANIFESTS and regenerates
#     the lockfile for the remaining (public) workspace.
#   * verify-oss.sh scans MANIFEST_GLOBS and FAILS if any still references a
#     private path — a hard backstop in case regeneration was skipped.

# Workspace membership files whose private-path entries assemble.sh prunes.
WORKSPACE_MANIFESTS=(
  "pnpm-workspace.yaml"
)

# Build/dependency manifests verify-oss.sh scans for leftover private-path refs.
MANIFEST_GLOBS=(
  "pnpm-lock.yaml" "pnpm-workspace.yaml"
  "package.json" "package-lock.json" "yarn.lock"
  "tsconfig.json" "tsconfig.*.json"
)

# --- Size limit --------------------------------------------------------------
# Max allowed file size in bytes (25 MB) — guards against accidental data dumps.
MAX_FILE_BYTES=$((25 * 1024 * 1024))

# --- Public repo -------------------------------------------------------------
# The public OSS repository (used for documentation/reference; the scripts do
# not push automatically).
PUBLIC_REPO_URL="git@github.com:Opencomplai/opencomplai.git"

# --- Commit-hash sync tracking ----------------------------------------------
# Records which enterprise commit the public repo was last synced from, so the
# NEXT sync can show exactly what changed since then (see sync-report.sh).
#
# The marker lives in the ENTERPRISE repo and is gitignored. It is:
#   * private   — it never enters the public tree (git archive skips untracked
#                 files, and it is gitignored on top of that), so it cannot leak
#                 the internal commit hash or release cadence.
#   * advisory  — it only sets the *baseline for the change report*. It is NEVER
#                 used to decide which files to transfer. Every sync is a full
#                 re-projection that is fully verified, so a stale/missing marker
#                 can make the report inaccurate but can NEVER cause a leak.
# Written only after verify-oss.sh PASSES (see sync-oss.sh).
SYNC_STATE_FILENAME=".oss-sync-state"

# Trailer added to the (human-made) public commit message for provenance. Lets
# any clone recover the last-synced SHA from public git history if the local
# marker file is lost — `git -C <public> log --grep '<key>'`.
SYNC_TRAILER_KEY="OSS-Synced-From"

# --- Shared denylist matcher -------------------------------------------------
# Single source of truth for "is this repo-relative path private?". Used by
# sync-report.sh to classify each changed file as published vs stripped, so the
# report can never disagree with the denylist above. (assemble.sh/verify-oss.sh
# keep their own proven loops; this helper mirrors the same rules for the
# advisory report surface.)
#
#   oss_is_private "<repo-relative-path>"  -> exit 0 if private, 1 if public
oss_is_private() {
  local p="${1#./}" d f g w base
  for d in "${PRIVATE_DIRS[@]}"; do
    case "$p" in "$d"/*|"$d") return 0 ;; esac
  done
  for f in "${PRIVATE_FILES[@]}"; do
    [ "$p" = "$f" ] && return 0
  done
  base="${p##*/}"
  for g in "${PRIVATE_GLOBS[@]}"; do
    # shellcheck disable=SC2254  # intentional glob match
    case "$base" in $g) return 0 ;; esac
  done
  for w in "${PRIVATE_WORKFLOWS[@]}"; do
    [ "$p" = "$w" ] && return 0
  done
  return 1
}
