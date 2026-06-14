#!/usr/bin/env bash
# benchmark-ttfs.sh — Time-To-First-Scan (TTFS) benchmark
#
# Measures the wall-clock time for a complete compliance scan cycle:
#   1. Submit a ScanStatusArtifact (ingest)
#   2. Issue a compliance badge
#   3. Verify the badge
#
# Reports mean, min, max, and p95 over N iterations.
#
# Usage:
#   ./scripts/benchmark-ttfs.sh
#   OPENCOMPLAI_GATEWAY_URL=https://... ITERATIONS=100 ./scripts/benchmark-ttfs.sh
#
# Requirements: bash, curl, python3 (stdlib only)

set -euo pipefail

GATEWAY_URL="${OPENCOMPLAI_GATEWAY_URL:-http://localhost:3000}"
ITERATIONS="${ITERATIONS:-20}"
SYSTEM_ID="benchmark-system-$$"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " OpenComplAI TTFS Benchmark"
echo " Gateway:    $GATEWAY_URL"
echo " Iterations: $ITERATIONS"
echo " System ID:  $SYSTEM_ID"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Health check
HTTP_STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "$GATEWAY_URL/health" 2>/dev/null || echo "000")
if [[ "$HTTP_STATUS" != "200" ]]; then
  echo "[ERROR] Gateway not reachable at $GATEWAY_URL (HTTP $HTTP_STATUS)" >&2
  exit 2
fi
echo "[INFO]  Gateway healthy. Starting benchmark..."
echo ""

TIMES=()

for i in $(seq 1 "$ITERATIONS"); do
  CHECKSUM="sha256:bench$(printf '%08d' "$i")"
  START=$(date +%s%N)  # nanoseconds

  # Step 1: ingest
  curl -sf -X POST \
    -H "Content-Type: application/json" \
    -d "{\"system_id\":\"$SYSTEM_ID\",\"result\":\"pass\",\"failed_controls\":[],\"pending_verifications_count\":0,\"bundle_checksum\":\"$CHECKSUM\"}" \
    "$GATEWAY_URL/v1/pro/ingest/status-artifact" > /dev/null

  # Step 2: issue badge
  BADGE_RESP=$(curl -sf -X POST \
    -H "Content-Type: application/json" \
    -d "{\"system_id\":\"$SYSTEM_ID\",\"bundle_checksum\":\"$CHECKSUM\",\"artifact\":{\"result\":\"pass\",\"pending_verifications_count\":0,\"system_id\":\"$SYSTEM_ID\",\"bundle_checksum\":\"$CHECKSUM\"}}" \
    "$GATEWAY_URL/v1/pro/badges/issue")

  BADGE_ID=$(echo "$BADGE_RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('badge_id',''))" 2>/dev/null || echo "")

  if [[ -z "$BADGE_ID" ]]; then
    echo "[WARN]  Iteration $i: badge issuance failed, skipping" >&2
    continue
  fi

  # Step 3: verify
  curl -sf "$GATEWAY_URL/v1/pro/badges/verify/$BADGE_ID" > /dev/null

  END=$(date +%s%N)
  ELAPSED_MS=$(( (END - START) / 1000000 ))
  TIMES+=("$ELAPSED_MS")

  printf "  [%3d/%d] %d ms\n" "$i" "$ITERATIONS" "$ELAPSED_MS"
done

echo ""

if [[ ${#TIMES[@]} -eq 0 ]]; then
  echo "[ERROR] No successful iterations" >&2
  exit 1
fi

# Statistics (python3 stdlib)
python3 - "${TIMES[@]}" <<'PYEOF'
import sys, statistics

times = [int(t) for t in sys.argv[1:]]
times_sorted = sorted(times)
n = len(times)
p95_idx = max(0, int(n * 0.95) - 1)

mean_ms   = statistics.mean(times)
median_ms = statistics.median(times)
min_ms    = min(times)
max_ms    = max(times)
p95_ms    = times_sorted[p95_idx]
stdev_ms  = statistics.stdev(times) if n > 1 else 0.0

print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
print(f" TTFS Benchmark Results  (n={n})")
print(f"  Mean:    {mean_ms:>8.1f} ms")
print(f"  Median:  {median_ms:>8.1f} ms")
print(f"  Min:     {min_ms:>8d} ms")
print(f"  Max:     {max_ms:>8d} ms")
print(f"  p95:     {p95_ms:>8d} ms")
print(f"  StdDev:  {stdev_ms:>8.1f} ms")
print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

# PRD target: TTFS < 500 ms at p95 for local deployment
TARGET_P95_MS = 500
if p95_ms <= TARGET_P95_MS:
    print(f"[PASS]  p95 {p95_ms}ms ≤ {TARGET_P95_MS}ms target")
else:
    print(f"[WARN]  p95 {p95_ms}ms > {TARGET_P95_MS}ms target — consider profiling")
PYEOF
