#!/usr/bin/env bash
# Run `opencomplai check` through a pinned uvx call and publish its result.
#
# Env in:  OC_VERSION (exact release, required), OC_INSTALL_FROM (optional path or
#          spec that replaces the pinned package, used by the self-test),
#          OC_WITH (newline list of extra --with specs), OC_MANIFEST, OC_ARGS
#          (extra check args, split on whitespace), OC_OUT_DIR, OC_SIGN and
#          OC_WITH_GAPS (the exact string "true" adds --sign-if-available / --with-gaps),
#          OC_STRICT (the exact string "true" adds the strict preset: --with-gaps --scan
#          --fail-on major --require-exemption-record --sign-if-available, each only when
#          not already set through the flags above or OC_ARGS).
# Out:     exit-code, summary-file, sarif-file, artifact-file in $GITHUB_OUTPUT.
# This script always exits 0: failing the job is the caller's decision.
set -uo pipefail

MARKER='<!-- opencomplai-gate -->'
manifest="${OC_MANIFEST:-system-manifest.json}"
out_dir="${OC_OUT_DIR:-${RUNNER_TEMP:-/tmp}/opencomplai}"
mkdir -p "$out_dir"
summary="$out_dir/summary.md"
sarif="$out_dir/results.sarif"
artifact="$out_dir/compliance-artifact.json"
rm -f "$summary" "$sarif" "$artifact"

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
  --summary-md "$summary" --sarif-output "$sarif")
# Flags come before the user's args so `args` can still add a strict --sign.
if [ "${OC_SIGN:-false}" = true ]; then cmd+=(--sign-if-available); fi
if [ "${OC_WITH_GAPS:-false}" = true ]; then cmd+=(--with-gaps); fi
# True when NAME or NAME=... is already in cmd or in the user's args.
has_flag() {
  local a
  for a in ${cmd[@]+"${cmd[@]}"} ${extra[@]+"${extra[@]}"}; do
    case "$a" in "$1" | "$1="*) return 0 ;; esac
  done
  return 1
}
if [ "${OC_STRICT:-false}" = true ]; then
  has_flag --with-gaps || cmd+=(--with-gaps)
  has_flag --scan || cmd+=(--scan)
  has_flag --fail-on || cmd+=(--fail-on major)
  has_flag --require-exemption-record || cmd+=(--require-exemption-record)
  # --no-sign plus --sign-if-available would still sign when a key exists.
  has_flag --sign-if-available || has_flag --sign || has_flag --no-sign || cmd+=(--sign-if-available)
fi
cmd+=(${extra[@]+"${extra[@]}"})

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
[ -s "$artifact" ] || artifact=""

{
  echo "exit-code=$code"
  echo "summary-file=$summary"
  echo "sarif-file=$sarif"
  echo "artifact-file=$artifact"
} >>"${GITHUB_OUTPUT:-/dev/null}"
exit 0
