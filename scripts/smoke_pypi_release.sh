#!/usr/bin/env bash
#
# smoke_pypi_release.sh - Check what a user gets from PyPI after a publish.
#
# Installs opencomplai and opencomplai-ai at exactly <version> into a fresh venv
# and runs the first-run path (init, check, verify), a classification proposal
# and its acceptance, a scan-backed check, and the export and verify steps. It
# installs from the index named by pip's own configuration; nothing is sent to
# any OpenComplAI service.
#
# Usage:
#   bash scripts/smoke_pypi_release.sh <version>
#
# Needs python and network access to the package index. Environment:
#   SMOKE_PYTHON            python to build the venv with (default: python or python3)
#   SMOKE_PIP_ARGS          extra pip install arguments (e.g. --find-links <dir>)
#   SMOKE_INSTALL_ATTEMPTS  install tries while the index catches up (default 10)
#   SMOKE_INSTALL_WAIT      seconds between tries (default 30)
# Exit codes: 0 pass, 1 a named step failed, 2 bad usage.

set -euo pipefail

V="${1:-}"
if ! [[ "$V" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.+-][0-9A-Za-z.+-]*)?$ ]]; then
  echo "usage: bash scripts/smoke_pypi_release.sh <version>   (e.g. 1.2.3)" >&2
  exit 2
fi

. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/smoke_lib.sh"

unset PYTHONPATH MYPYPATH OPENCOMPLAI_API_URL
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

PY="${SMOKE_PYTHON:-$(command -v python || command -v python3 || true)}"
[ -n "$PY" ] || smoke_fail install "no python on PATH (set SMOKE_PYTHON)"

smoke_step install "$PY" -m venv "$TMP/venv"
BIN="$TMP/venv/bin"
[ -d "$BIN" ] || BIN="$TMP/venv/Scripts" # Windows venv layout
VPY="$BIN/python"
[ -x "$VPY" ] || VPY="$BIN/python.exe"

attempts="${SMOKE_INSTALL_ATTEMPTS:-10}"
n=0
until "$VPY" -m pip install --no-cache-dir --quiet "opencomplai==$V" "opencomplai-ai==$V" ${SMOKE_PIP_ARGS:-}; do
  n=$((n + 1))
  [ "$n" -lt "$attempts" ] || smoke_fail install "pip install of $V failed after $n attempts"
  sleep "${SMOKE_INSTALL_WAIT:-30}"
done
echo "SMOKE OK step=install"

export PATH="$BIN:$PATH"
# A first run: ~/.opencomplai lands in the scratch dir, outside any repo.
export HOME="$TMP/home" USERPROFILE="$TMP/home"
mkdir -p "$HOME" "$TMP/work"
cd "$TMP/work"

got="$(opencomplai --version)" || smoke_fail version "opencomplai --version failed"
smoke_assert_eq version "$got" "opencomplai $V"
for dist in opencomplai opencomplai-core opencomplai-cli opencomplai-ai; do
  have="$("$VPY" -c 'import importlib.metadata as m, sys; print(m.version(sys.argv[1]))' "$dist")" \
    || smoke_fail version "$dist is not installed"
  smoke_assert_eq version "$have" "$V"
done

M=system-manifest.json
smoke_step init opencomplai init --system-id smoke-system \
  --intended-purpose "customer support chatbot" --output "$M"
smoke_expect check 0 opencomplai check --manifest "$M" --sign --with-gaps
out="$(opencomplai verify compliance-artifact.json)" || smoke_fail verify "exit non-zero: $out"
case "$out" in verified:*) echo "SMOKE OK step=verify" ;; *) smoke_fail verify "got '$out'" ;; esac

mkdir -p repo/src
for n in a b c; do
  cat >"repo/src/screen_$n.py" <<'PYEOF'
from sklearn.ensemble import RandomForestClassifier


def screen(applicants):
    ranked = rank_candidates(applicants)
    return ranked
PYEOF
done
smoke_expect propose 0 opencomplai scan --manifest "$M" --repo-root repo --propose
PROP=repo/classification-proposal.json
[ -f "$PROP" ] || smoke_fail propose "$PROP was not written"
"$VPY" - "$PROP" <<'PYEOF' || smoke_fail propose "proposal is not unconfirmed from codebert-onnx"
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
assert d["status"] == "unconfirmed", d.get("status")
assert d["ai_model_id"] == "codebert-onnx", d.get("ai_model_id")
PYEOF

smoke_expect accept 0 opencomplai accept --manifest "$M" --accepted-by smoke@example.invalid \
  --proposal "$PROP" --repo-root repo --yes
ls repo/.opencomplai/acceptances/*classification_proposal_confirmation.json >/dev/null 2>&1 \
  || smoke_fail accept "no classification_proposal_confirmation record under repo/.opencomplai/acceptances"

smoke_expect check-scan 0 opencomplai check --manifest "$M" --sign --scan --repo-root repo --with-gaps

smoke_expect export 0 opencomplai export compliance-artifact.json --out package.json --artifact-out embedded.json
smoke_expect export 0 opencomplai export compliance-artifact.json --format csv --out package.csv
head -n 1 package.csv | grep -q 'tree_sha256,tree_dirty,signed,verdict' \
  || smoke_fail export "CSV header lacks tree_sha256,tree_dirty,signed,verdict"
out="$(opencomplai verify embedded.json)" || smoke_fail verify-export "exit non-zero: $out"
case "$out" in verified:*) echo "SMOKE OK step=verify-export" ;; *) smoke_fail verify-export "got '$out'" ;; esac

"$VPY" - <<'PYEOF'
import json
d = json.load(open("embedded.json", encoding="utf-8"))
d["system_id"] = d["system_id"] + "-tampered"
json.dump(d, open("tampered.json", "w", encoding="utf-8"))
PYEOF
smoke_expect verify-tamper 1 opencomplai verify tampered.json

smoke_expect export-sign 0 opencomplai export compliance-artifact.json --sign --out signed-package.json
out="$(opencomplai verify signed-package.json --kind evidence-package)" || smoke_fail verify-package "exit non-zero: $out"
case "$out" in verified:*) echo "SMOKE OK step=verify-package" ;; *) smoke_fail verify-package "got '$out'" ;; esac

echo "SMOKE PASS opencomplai==$V"
