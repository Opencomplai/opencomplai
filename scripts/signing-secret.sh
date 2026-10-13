#!/usr/bin/env bash
#
# signing-secret.sh - Create the release signing key and store it as a GitHub
# repository secret, without the private key ever being shown or saved.
#
# Usage:
#   scripts/signing-secret.sh <NAME> <OWNER/REPO> [--replace]
#
#   NAME        secret name, for example OPENCOMPLAI_SIGNING_KEY
#   OWNER/REPO  repository that receives the secret
#   --replace   overwrite a secret that already exists (this changes the key
#               every earlier signature was made with)
#
# The key is an Ed25519 key, base64 of the unencrypted PKCS8 PEM on one line,
# which is the shape SIGNING_KEY_PRIVATE expects. It is generated in memory,
# piped to `gh secret set` on stdin and then dropped. Only the public key is
# printed, for you to publish.
#
# Requires: gh (authenticated), openssl, base64.

set -euo pipefail
set +x # a caller's `bash -x` must not trace the key

usage() {
  printf 'usage: %s <NAME> <OWNER/REPO> [--replace]\n' "${0##*/}" >&2
  exit 2
}

REPLACE=0
POS=()
for arg in "$@"; do
  if [[ $arg == --replace ]]; then REPLACE=1; else POS+=("$arg"); fi
done
[[ ${#POS[@]} -eq 2 ]] || usage
NAME=${POS[0]}
REPO=${POS[1]}
[[ $NAME =~ ^[A-Z_][A-Z0-9_]*$ ]] || usage
[[ $REPO =~ ^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$ ]] || usage

for tool in gh openssl; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    printf '%s: %s is required but was not found on PATH\n' "${0##*/}" "$tool" >&2
    exit 2
  fi
done

rc=0
LIST=$(gh secret list --repo "$REPO") || rc=$?
if [[ $rc -ne 0 ]]; then
  printf '%s: could not list secrets of %s (gh exit %s)\n' "${0##*/}" "$REPO" "$rc" >&2
  exit "$rc"
fi
if [[ $REPLACE -eq 0 ]]; then
  while read -r first _; do
    if [[ $first == "$NAME" ]]; then
      printf '%s: secret %s already exists in %s. Replacing it changes the key every earlier signature was made with; pass --replace to do it anyway.\n' \
        "${0##*/}" "$NAME" "$REPO" >&2
      exit 3
    fi
  done <<<"$LIST"
fi

PEM=$(openssl genpkey -algorithm ED25519)
B64=$(printf '%s\n' "$PEM" | base64 | tr -d '\n')

rc=0
printf '%s' "$B64" | gh secret set "$NAME" --repo "$REPO" || rc=$?
if [[ $rc -ne 0 ]]; then
  printf '%s: gh secret set failed (exit %s); no key was stored\n' "${0##*/}" "$rc" >&2
  exit "$rc"
fi

printf 'Secret %s stored in %s. Public key to publish (the private key was not shown or saved):\n' "$NAME" "$REPO"
printf '%s\n' "$PEM" | openssl pkey -pubout
unset PEM B64
