#!/usr/bin/env bash
#
# smoke_wheel_install.sh — Install the built wheels into a clean venv and run
# the CLI the way a PyPI user would, then also from a uv tool and a pipx install.
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
# Needs uv and network (resolves the newest typer from PyPI). Works on Linux and Git Bash on Windows.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# shellcheck source=smoke_lib.sh
. "$REPO_ROOT/scripts/smoke_lib.sh"

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
VIRTUAL_ENV="$TMP/venv" uv pip install --refresh "$TMP"/dist/*.whl
BIN="$TMP/venv/bin"
[ -d "$BIN" ] || BIN="$TMP/venv/Scripts" # Windows venv layout
export PATH="$BIN:$PATH"

# Local engine only, and a first run: ~/.opencomplai lands in the scratch dir.
unset OPENCOMPLAI_API_URL
export HOME="$TMP/home" USERPROFILE="$TMP/home"
mkdir -p "$HOME" work
cd work

META_NAME="$(basename "$(ls "$TMP"/dist/opencomplai-[0-9]*.whl | head -n 1)")"
EXPECTED_VERSION="${META_NAME#opencomplai-}"
EXPECTED_VERSION="${EXPECTED_VERSION%%-*}"
venv_version="$(opencomplai --version)" || smoke_fail version "opencomplai --version failed"
smoke_assert_eq version "$venv_version" "opencomplai $EXPECTED_VERSION"
# typer 0.27+ vendors click, so click is expected to be absent there.
python -c 'import importlib.metadata as m
def v(n):
    try:
        return m.version(n)
    except m.PackageNotFoundError:
        return "absent"
print("typer=" + v("typer"), "click=" + v("click"))
assert v("typer") != "absent", "typer is a declared dependency"' || smoke_fail typer "typer missing from the venv"

# uv tool and pipx expose only scripts the named package declares itself, so
# install the meta package the way users do, with PATH cleared of the venv bin
# (otherwise the CLI package's script in the venv would mask a missing one).
# Local wheels stand in for the unreleased version.
META_WHL=("$TMP"/dist/opencomplai-[0-9]*.whl)
CORE_WHL=("$TMP"/dist/opencomplai_core-*.whl)
CLI_WHL=("$TMP"/dist/opencomplai_cli-*.whl)
CLEAN_PATH="${PATH#"$BIN:"}"
exe() { # $1 = bin dir
  if [ -x "$1/opencomplai" ]; then echo "$1/opencomplai"; else echo "$1/opencomplai.exe"; fi
}
check_tool_version() { # $1 = label, $2 = bin dir
  local out
  out="$(PATH="$CLEAN_PATH" "$(exe "$2")" --version)"
  [ -n "$out" ] && [ "$out" = "$venv_version" ] || {
    echo "$1: --version '$out' differs from venv '$venv_version'" >&2
    exit 1
  }
}

PATH="$CLEAN_PATH" UV_TOOL_DIR="$TMP/uvtool" UV_TOOL_BIN_DIR="$TMP/uvtool-bin"   uv tool install "${META_WHL[0]}" --with "${CORE_WHL[0]}" --with "${CLI_WHL[0]}"
check_tool_version "uv tool" "$TMP/uvtool-bin"

uv venv "$TMP/pipx-venv"
VIRTUAL_ENV="$TMP/pipx-venv" uv pip install pipx
PIPX_PY="$TMP/pipx-venv/bin/python"
[ -x "$PIPX_PY" ] || PIPX_PY="$TMP/pipx-venv/Scripts/python.exe" # Windows venv layout
# pip-args reach pip as-is; an MSYS /tmp path is not a Windows path, so convert when
# cygpath exists. --find-links lets pip pick the local core and cli wheels.
winpath() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else echo "$1"; fi; }
PATH="$CLEAN_PATH" PIPX_HOME="$TMP/pipx-home" PIPX_BIN_DIR="$TMP/pipx-bin"   "$PIPX_PY" -m pipx install "${META_WHL[0]}" --pip-args="--find-links=$(winpath "$TMP/dist")"
check_tool_version "pipx" "$TMP/pipx-bin"

echo '{"compliance_targets": ["EU_AI_ACT", "NIST_AI_RMF"]}' >targets.json
smoke_step init opencomplai init \
  --system-id smoke-system \
  --intended-purpose "customer support chatbot" \
  --section-extras-file targets.json \
  --output system-manifest.json
smoke_expect check 0 opencomplai check --manifest system-manifest.json --sign --with-gaps
out="$(opencomplai verify compliance-artifact.json)" || smoke_fail verify "verify exited non-zero: $out"
case "$out" in
  verified:*) echo "SMOKE OK step=verify" ;;
  *) smoke_fail verify "expected 'verified:', got '$out'" ;;
esac
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

# iso_42001.json must ship in the wheel: the ISO/IEC 42001 pack reads it.
opencomplai gaps --manifest system-manifest.json --target ISO_IEC_42001 --output json >iso-gaps.json
python - <<'EOF'
import json

payload = json.load(open("iso-gaps.json"))["payload"]
iso = payload["frameworks"]["ISO_IEC_42001"]
assert iso["report"]["articles"], "ISO_IEC_42001 has no rows"
EOF

echo "Wheel install smoke test passed."
