#!/usr/bin/env bash
#
# homebrew-release.sh - Fill the Homebrew formula url and sha256 from PyPI.
#
# Reads the published JSON for opencomplai <version>, selects its one sdist,
# refuses a missing, malformed or all-zero digest, downloads the sdist and
# checks that its bytes hash to the published digest, then patches the formula
# url and sha256 in place. Nothing is written unless the index, digest and
# download checks passed; a lint failure leaves the patched formula for review.
#
# Usage:
#   bash scripts/homebrew-release.sh <version> [--formula <path>]
#
# Run it once the release is on PyPI. Default formula:
# packaging/homebrew/opencomplai.rb next to this script's repository root.
# Environment (tests and maintainer use only):
#   HOMEBREW_PYTHON          python to use (default: python or python3)
#   HOMEBREW_PYPI_JSON_URL   release JSON (default https://pypi.org/pypi/opencomplai/<version>/json)
#   HOMEBREW_SDIST_BASE_URL  sdist directory (default https://files.pythonhosted.org/packages/source/o/opencomplai)
# Exit codes: 0 pass, 1 a named step failed, 2 bad usage.

set -euo pipefail
unset PYTHONPATH MYPYPATH

usage() {
  echo "usage: bash scripts/homebrew-release.sh <version> [--formula <path>]   (e.g. 1.2.3)" >&2
  exit 2
}

V=""
FORMULA=""
GIVEN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --formula)
      [ $# -ge 2 ] || usage
      FORMULA="$2"
      GIVEN=1
      shift 2
      ;;
    -*) usage ;;
    *)
      [ -z "$V" ] || usage
      V="$1"
      shift
      ;;
  esac
done
[[ "$V" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || usage

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "$GIVEN" -eq 0 ]; then
  FORMULA="$ROOT/packaging/homebrew/opencomplai.rb"
  # Windows python does not read /c/... paths.
  if command -v cygpath >/dev/null 2>&1; then FORMULA="$(cygpath -m "$FORMULA")"; fi
fi

PY="${HOMEBREW_PYTHON:-$(command -v python || command -v python3 || true)}"
if [ -z "$PY" ]; then
  echo "HOMEBREW FAIL step=usage: no python on PATH (set HOMEBREW_PYTHON)" >&2
  exit 1
fi

JSON_URL="${HOMEBREW_PYPI_JSON_URL:-https://pypi.org/pypi/opencomplai/$V/json}"
SDIST_BASE="${HOMEBREW_SDIST_BASE_URL:-https://files.pythonhosted.org/packages/source/o/opencomplai}"
CANON_URL="https://files.pythonhosted.org/packages/source/o/opencomplai/opencomplai-$V.tar.gz"

DIGEST="$(
  "$PY" - "$V" "$FORMULA" "$JSON_URL" "$SDIST_BASE" "$CANON_URL" <<'PYEOF'
import hashlib
import json
import os
import re
import sys
import urllib.request

version, formula, json_url, sdist_base, canon_url = sys.argv[1:6]
name = f"opencomplai-{version}.tar.gz"
URL_RE = re.compile(r'^(\s*url ")[^"]+(")$')
SHA_RE = re.compile(r'^(\s*sha256 ")[0-9a-f]{64}(")$')


def die(step, msg):
    sys.stderr.write(f"HOMEBREW FAIL step={step}: {msg}\n")
    sys.exit(1)


def ok(step):
    sys.stderr.write(f"HOMEBREW OK step={step}\n")


def load_formula():
    try:
        with open(formula, encoding="utf-8", newline="") as fh:
            text = fh.read()
    except OSError as exc:
        die("formula", f"cannot read {formula}: {exc}")
    lines = text.splitlines(keepends=True)
    bare = [ln.rstrip("\r\n") for ln in lines]
    if sum(1 for b in bare if URL_RE.match(b)) != 1:
        die("formula", "need exactly one url line")
    if sum(1 for b in bare if SHA_RE.match(b)) != 1:
        die("formula", "need exactly one sha256 line with a 64-hex digest")
    return lines


def fetch(url, step):
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return resp.read()
    except Exception as exc:  # network or file errors: report, never patch
        die(step, f"cannot fetch {url}: {exc}")


lines = load_formula()
ok("formula")

try:
    doc = json.loads(fetch(json_url, "index"))
except ValueError as exc:
    die("index", f"not JSON: {exc}")
if (doc.get("info") or {}).get("version") != version:
    die("index", f"JSON version is not {version}")
sdists = [u for u in doc.get("urls") or [] if u.get("packagetype") == "sdist"]
if not sdists:
    die("index", "no sdist in the release JSON")
if len(sdists) > 1:
    die("index", "ambiguous sdist: more than one in the release JSON")
entry = sdists[0]
if entry.get("filename") not in (None, name):
    die("index", f"sdist filename is not {name}")
digest = str((entry.get("digests") or {}).get("sha256", ""))
ok("index")

if not re.fullmatch(r"[0-9a-f]{64}", digest):
    die("digest", "published sha256 is not 64 lowercase hex characters")
if digest == "0" * 64:
    die("digest", "published sha256 is the all-zero placeholder")
ok("digest")

got = hashlib.sha256(fetch(f"{sdist_base}/{name}", "download")).hexdigest()
if got != digest:
    die("download", f"sdist hashes to {got} but the index publishes {digest}")
ok("download")

out = []
for ln in lines:
    bare = ln.rstrip("\r\n")
    end = ln[len(bare) :]
    if re.match(r"^\s*# PLACEHOLDER:", bare):
        continue
    m = URL_RE.match(bare)
    if m:
        ln = f"{m.group(1)}{canon_url}{m.group(2)}{end}"
    m = SHA_RE.match(bare)
    if m:
        ln = f"{m.group(1)}{digest}{m.group(2)}{end}"
    out.append(ln)
new = "".join(out)
tmp = formula + ".tmp"
try:
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(new)
    os.replace(tmp, formula)
except OSError as exc:
    if os.path.exists(tmp):
        os.unlink(tmp)
    die("patch", f"cannot write {formula}: {exc}")
ok("patch")

with open(formula, encoding="utf-8", newline="") as fh:
    final = fh.read()
if not any(
    URL_RE.match(b) and b.rstrip('"').endswith(name) for b in final.splitlines()
):
    die("lint", "url does not end with the sdist name")
if f'sha256 "{digest}"' not in final:
    die("lint", "sha256 line does not carry the verified digest")
if "\t" in final or re.search(r"[ \t]+\r?$", final, re.M):
    die("lint", "tab or trailing whitespace in the formula")
if not final.endswith("\n") or final.endswith("\n\n"):
    die("lint", "formula must end with exactly one newline")
ok("lint")
print(digest)
PYEOF
)"

if [ "$GIVEN" -eq 0 ]; then
  if [ -f "$ROOT/packages/cli/tests/test_homebrew_formula.py" ] && "$PY" -c "import pytest" 2>/dev/null; then
    (cd "$ROOT" && "$PY" -m pytest -q -p no:cacheprovider packages/cli/tests/test_homebrew_formula.py) ||
      {
        echo "HOMEBREW FAIL step=lint: test_homebrew_formula.py failed" >&2
        exit 1
      }
  else
    echo "HOMEBREW SKIP step=lint: pytest not available"
  fi
  if command -v brew >/dev/null 2>&1; then
    brew style "$FORMULA" || {
      echo "HOMEBREW FAIL step=lint: brew style failed" >&2
      exit 1
    }
  else
    echo "HOMEBREW SKIP step=lint: brew not installed"
  fi
fi

echo "HOMEBREW PASS opencomplai==$V sha256=$DIGEST"
cat <<EOF

Still to do by hand (this script does not run them):
  1. brew update-python-resources $FORMULA   (the formula has no resource blocks)
  2. copy the formula to Formula/opencomplai.rb in the tap repository
  3. brew install --build-from-source opencomplai
  4. brew test opencomplai
EOF
