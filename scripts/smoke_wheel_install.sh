#!/usr/bin/env bash
#
# smoke_wheel_install.sh — Install the built wheels into a clean venv and run
# the CLI the way a PyPI user would.
#
# Builds opencomplai-core, opencomplai-cli and the opencomplai meta-package
# the way the PyPI release does (sdist, then the wheel from it), installs
# only those wheels plus their PyPI dependencies into a fresh venv, then runs
# the CLI from an empty directory outside the repo. The workspace test suites
# import from source and cannot see a module, dependency or data file the
# wheels fail to ship; this does.
#
# Usage:
#   bash scripts/smoke_wheel_install.sh
#
# Needs uv. Works on Linux and Git Bash on Windows.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

cd "$REPO_ROOT"
# The CLI wheel force-includes this file. It is committed, so node is only
# needed when it has been deleted locally.
if [ ! -f packages/cli/src/opencomplai_cli/data/checker-local.html ]; then
  (cd docs/checker-widget && npm ci && node build.mjs)
fi
for pkg in opencomplai-core opencomplai-cli opencomplai; do
  uv build --package "$pkg" --out-dir "$TMP/dist"
done

# Outside the repo, so neither uv nor Python can see the workspace.
cd "$TMP"
uv venv venv
VIRTUAL_ENV="$TMP/venv" uv pip install "$TMP"/dist/*.whl
BIN="$TMP/venv/bin"
[ -d "$BIN" ] || BIN="$TMP/venv/Scripts" # Windows venv layout
export PATH="$BIN:$PATH"

# Local engine only, and a first run: ~/.opencomplai lands in the scratch dir.
unset OPENCOMPLAI_API_URL
export HOME="$TMP/home" USERPROFILE="$TMP/home"
mkdir -p "$HOME" work
cd work

opencomplai --version
echo '{"compliance_targets": ["EU_AI_ACT", "NIST_AI_RMF"]}' >targets.json
opencomplai init \
  --system-id smoke-system \
  --intended-purpose "customer support chatbot" \
  --section-extras-file targets.json \
  --output system-manifest.json
opencomplai check --manifest system-manifest.json --with-gaps
# Two targets: one framework report each, and the legacy blocks as before.
python - <<'EOF'
import json

artifact = json.load(open("compliance-artifact.json"))
assert list(artifact.get("framework_reports") or {}) == ["EU_AI_ACT", "NIST_AI_RMF"], (
    "framework_reports", list(artifact.get("framework_reports") or {})
)
assert artifact.get("gap_report"), "gap_report missing"
assert artifact.get("nist_rmf_report"), "nist_rmf_report missing"
EOF
opencomplai docs generate \
  --system-id smoke-system \
  --manifest system-manifest.json \
  --output-dir dossier \
  --allow-incomplete
ls dossier/dossier_*.json # named after the dossier_id; fails if none

# This directory has none of the documents the gap probes look for, so the
# NIST AI RMF rows derived from them are Missing and gating NIST AI RMF turns
# the PASS above into CONTROL_FAIL (exit 1).
status=0
opencomplai check --manifest system-manifest.json --gate NIST_AI_RMF || status=$?
if [ "$status" -ne 1 ]; then
  echo "check --gate NIST_AI_RMF exited $status, expected 1" >&2
  exit 1
fi
python - <<'EOF'
import json

failed = json.load(open("compliance-artifact.json"))["failed_controls"]
assert any(c.startswith("NIST_AI_RMF:") for c in failed), failed
EOF

echo "Wheel install smoke test passed."
