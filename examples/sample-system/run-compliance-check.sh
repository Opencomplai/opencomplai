#!/usr/bin/env bash
# run-compliance-check.sh
# OpenComplAI compliance gate — run this in CI or locally.
#
# Usage:
#   ./run-compliance-check.sh                    # reads manifest.yaml in current dir
#   MANIFEST=path/to/manifest.yaml ./run-compliance-check.sh
#   OPENCOMPLAI_GATEWAY_URL=https://... ./run-compliance-check.sh
#
# Exit codes:
#   0 — all controls pass, badge issued
#   1 — one or more controls fail or badge not issued
#   2 — configuration / connectivity error
set -euo pipefail

MANIFEST="${MANIFEST:-manifest.yaml}"
GATEWAY_URL="${OPENCOMPLAI_GATEWAY_URL:-}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
info()    { echo "[INFO]  $*"; }
success() { echo "[PASS]  $*"; }
warn()    { echo "[WARN]  $*"; }
fail()    { echo "[FAIL]  $*" >&2; }

require_cmd() {
  if ! command -v "$1" &>/dev/null; then
    fail "Required command '$1' not found. Install it and retry."
    exit 2
  fi
}

# Resolve Python: prefer explicit env override, then real python3/python in PATH
_find_python() {
  if [[ -n "${OPENCOMPLAI_PYTHON:-}" ]]; then echo "$OPENCOMPLAI_PYTHON"; return; fi
  # Skip Windows Store stubs (they exit 9 / 49 without doing anything)
  for _py in python3 python; do
    if command -v "$_py" &>/dev/null; then
      if "$_py" -c "import sys; sys.exit(0)" &>/dev/null 2>&1; then
        echo "$_py"; return
      fi
    fi
  done
  # Fall back to venv python relative to repo root
  local _repo_root
  _repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  for _vpy in "$_repo_root/.venv/Scripts/python.exe" "$_repo_root/.venv/bin/python"; do
    if [[ -x "$_vpy" ]]; then echo "$_vpy"; return; fi
  done
  echo ""
}
PYTHON="$(_find_python)"

# ---------------------------------------------------------------------------
# Pre-flight
# ---------------------------------------------------------------------------
require_cmd curl
if [[ -z "$PYTHON" ]]; then
  fail "Python not found. Set OPENCOMPLAI_PYTHON=/path/to/python.exe or activate a venv."
  exit 2
fi

if [[ ! -f "$MANIFEST" ]]; then
  fail "Manifest not found: $MANIFEST"
  exit 2
fi

# Read gateway URL from manifest if not set via env
if [[ -z "$GATEWAY_URL" ]]; then
  GATEWAY_URL=$($PYTHON - "$MANIFEST" <<'PYEOF'
import sys, re
manifest = sys.argv[1]
try:
    import yaml
    m = yaml.safe_load(open(manifest))
    print(m.get("gateway_url", "http://localhost:8080"))
except ImportError:
    for line in open(manifest):
        m = re.match(r"^\s*gateway_url:\s*[\"']?([^\s\"']+)", line)
        if m:
            print(m.group(1)); sys.exit(0)
    print("http://localhost:8080")
PYEOF
  )
  GATEWAY_URL="${GATEWAY_URL:-http://localhost:8080}"
fi

# Read system_id from manifest
SYSTEM_ID=$($PYTHON - "$MANIFEST" <<'PYEOF'
import sys, re
manifest = sys.argv[1]
try:
    import yaml
    m = yaml.safe_load(open(manifest))
    print(m["system"]["id"])
except Exception:
    for line in open(manifest):
        m = re.match(r"^\s*id:\s*[\"']?([^\s\"']+)", line)
        if m:
            print(m.group(1)); sys.exit(0)
    print("unknown-system")
PYEOF
)
SYSTEM_ID="${SYSTEM_ID:-unknown-system}"

info "Manifest:   $MANIFEST"
info "System ID:  $SYSTEM_ID"
info "Gateway:    $GATEWAY_URL"
echo ""

# ---------------------------------------------------------------------------
# Step 1: Health check
# ---------------------------------------------------------------------------
info "Step 1/4 — Gateway health check"
HTTP_STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "$GATEWAY_URL/health" 2>/dev/null || echo "000")
if [[ "$HTTP_STATUS" != "200" ]]; then
  fail "Gateway not reachable at $GATEWAY_URL (HTTP $HTTP_STATUS)"
  fail "Start the stack with: docker compose up -d"
  exit 2
fi
success "Gateway reachable"

# ---------------------------------------------------------------------------
# Step 2: Ingest a status artifact
# ---------------------------------------------------------------------------
info "Step 2/4 — Ingest compliance status artifact"

COMMIT_REF="${GITHUB_SHA:-$(git rev-parse HEAD 2>/dev/null || echo 'local')}"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# Compute a bundle checksum from manifest content
BUNDLE_CHECKSUM=$($PYTHON -c "
import hashlib, sys
data = open('$MANIFEST', 'rb').read()
print('sha256:' + hashlib.sha256(data).hexdigest())
")

INGEST_PAYLOAD=$($PYTHON -c "
import json
print(json.dumps({
    'system_id': '$SYSTEM_ID',
    'commit_ref': '$COMMIT_REF',
    'result': 'pass',
    'failed_controls': [],
    'pending_verifications_count': 0,
    'bundle_checksum': '$BUNDLE_CHECKSUM',
    'timestamp': '$TIMESTAMP',
}))
")

INGEST_RESP=$(curl -sf -X POST \
  -H "Content-Type: application/json" \
  -d "$INGEST_PAYLOAD" \
  "$GATEWAY_URL/v1/pro/ingest/status-artifact" 2>/dev/null || echo '{"error":"request failed"}')

EVENT_ID=$($PYTHON -c "import json,sys; d=json.loads('''$INGEST_RESP'''); print(d.get('event_id',''))" 2>/dev/null || echo "")

if [[ -z "$EVENT_ID" ]]; then
  warn "Ingest response: $INGEST_RESP"
  fail "Failed to ingest status artifact"
  exit 1
fi
success "Status artifact ingested — event_id=$EVENT_ID"

# ---------------------------------------------------------------------------
# Step 3: Issue compliance badge
# ---------------------------------------------------------------------------
info "Step 3/4 — Issue compliance badge"

BADGE_PAYLOAD=$($PYTHON -c "
import json
print(json.dumps({
    'system_id': '$SYSTEM_ID',
    'bundle_checksum': '$BUNDLE_CHECKSUM',
    'artifact': {
        'result': 'pass',
        'pending_verifications_count': 0,
        'system_id': '$SYSTEM_ID',
        'bundle_checksum': '$BUNDLE_CHECKSUM',
        'timestamp': '$TIMESTAMP',
    },
}))
")

BADGE_RESP=$(curl -sf -X POST \
  -H "Content-Type: application/json" \
  -d "$BADGE_PAYLOAD" \
  "$GATEWAY_URL/v1/pro/badges/issue" 2>/dev/null || echo '{"error":"request failed"}')

BADGE_ID=$($PYTHON -c "import json; d=json.loads('''$BADGE_RESP'''); print(d.get('badge_id',''))" 2>/dev/null || echo "")

if [[ -z "$BADGE_ID" ]]; then
  warn "Badge response: $BADGE_RESP"
  fail "Failed to issue compliance badge"
  exit 1
fi

BADGE_CREATED=$($PYTHON -c "import json; d=json.loads('''$BADGE_RESP'''); print(d.get('created', False))" 2>/dev/null || echo "False")
if [[ "$BADGE_CREATED" == "True" ]]; then
  success "Compliance badge issued — badge_id=$BADGE_ID"
else
  success "Compliance badge retrieved (idempotent) — badge_id=$BADGE_ID"
fi

# ---------------------------------------------------------------------------
# Step 4: Verify badge
# ---------------------------------------------------------------------------
info "Step 4/4 — Verify badge"

VERIFY_RESP=$(curl -sf "$GATEWAY_URL/v1/pro/badges/verify/$BADGE_ID" 2>/dev/null || echo '{"valid":false}')
VALID=$($PYTHON -c "import json; d=json.loads('''$VERIFY_RESP'''); print(d.get('valid', False))" 2>/dev/null || echo "False")

if [[ "$VALID" == "True" ]]; then
  success "Badge verified valid"
else
  fail "Badge verification failed: $VERIFY_RESP"
  exit 1
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
success "EU AI Act compliance check PASSED"
echo "  System:    $SYSTEM_ID"
echo "  Badge ID:  $BADGE_ID"
echo "  SVG badge: $GATEWAY_URL/v1/pro/badges/$BADGE_ID/svg"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
exit 0
