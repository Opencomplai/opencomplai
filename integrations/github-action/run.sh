#!/usr/bin/env bash
# Run `opencomplai check` through a pinned uvx call and publish its result.
#
# Env in:  OC_VERSION (exact release, required), OC_INSTALL_FROM (optional path or
#          spec that replaces the pinned package, used by the self-test),
#          OC_WITH (newline list of extra --with specs), OC_MANIFEST, OC_ARGS
#          (extra check args, split on whitespace), OC_OUT_DIR.
# Out:     exit-code, summary-file, sarif-file in $GITHUB_OUTPUT.
# This script always exits 0: failing the job is the caller's decision.
set -uo pipefail

MARKER='<!-- opencomplai-gate -->'
manifest="${OC_MANIFEST:-system-manifest.json}"
out_dir="${OC_OUT_DIR:-${RUNNER_TEMP:-/tmp}/opencomplai}"
mkdir -p "$out_dir"
summary="$out_dir/summary.md"
sarif="$out_dir/results.sarif"
rm -f "$summary" "$sarif"

if [ -n "${OC_INSTALL_FROM:-}" ]; then
  from="$OC_INSTALL_FROM"
else
  : "${OC_VERSION:?OC_VERSION must be an exact release such as 0.9.0}"
  from="opencomplai==${OC_VERSION}"
fi

cmd=(uvx --from "$from")
while IFS= read -r spec; do
  [ -n "$spec" ] && cmd+=(--with "$spec")
done <<<"${OC_WITH:-}"

read -r -a extra <<<"${OC_ARGS:-}"
cmd+=(opencomplai check --manifest "$manifest" --output-dir "$out_dir"
  --summary-md "$summary" --sarif-output "$sarif" ${extra[@]+"${extra[@]}"})

"${cmd[@]}"
code=$?

# The CLI body gets the sticky marker on top; a run that wrote none gets a one-line body.
if [ -s "$summary" ]; then
  { printf '%s\n' "$MARKER"; cat "$summary"; } >"$summary.tmp" && mv "$summary.tmp" "$summary"
else
  printf '%s\nOpenComplAI check finished with exit code %s. No summary was produced.\n' \
    "$MARKER" "$code" >"$summary"
fi
[ -s "$sarif" ] || sarif=""

{
  echo "exit-code=$code"
  echo "summary-file=$summary"
  echo "sarif-file=$sarif"
} >>"${GITHUB_OUTPUT:-/dev/null}"
exit 0
