#!/usr/bin/env bash
# Create or update the one sticky pull-request comment (found by its marker).
# Env in: GH_TOKEN, GITHUB_REPOSITORY, PR_NUMBER, BODY_FILE.
set -euo pipefail

MARKER='<!-- opencomplai-gate -->'
if [ -z "${PR_NUMBER:-}" ]; then
  echo "::notice::Not a pull request event: skipping the OpenComplAI comment."
  exit 0
fi

# GitHub rejects comment bodies over 65536 characters. 60000 bytes never exceeds that
# (a character is at least one byte); the cut is moved back to a character boundary.
body="$BODY_FILE"
if [ "$(wc -c <"$BODY_FILE")" -gt 60000 ]; then
  body="$BODY_FILE.trimmed"
  cut=60000
  for _ in 1 2 3; do
    next=$(head -c "$((cut + 1))" "$BODY_FILE" | tail -c 1 | od -An -tu1 | tr -d ' ')
    [ "$next" -ge 128 ] && [ "$next" -lt 192 ] || break
    cut=$((cut - 1))
  done
  { head -c "$cut" "$BODY_FILE"; printf '\n\n_Summary truncated._\n'; } >"$body"
fi

repo_api="repos/${GITHUB_REPOSITORY}"
id=$(gh api --paginate "$repo_api/issues/$PR_NUMBER/comments" \
  --jq ".[] | select(.body | contains(\"$MARKER\")) | .id" | sed -n '1p')

if [ -n "$id" ]; then
  gh api --method PATCH "$repo_api/issues/comments/$id" -F "body=@$body" >/dev/null
else
  gh api --method POST "$repo_api/issues/$PR_NUMBER/comments" -F "body=@$body" >/dev/null
fi
