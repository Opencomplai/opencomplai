#!/usr/bin/env bash
# Verify the cosign signature and the SBOM attestation for a published
# Opencomplai container image.
#
# Usage:
#   ./sync/verify-sbom.sh gateway-api:<version>
#   ./sync/verify-sbom.sh ghcr.io/opencomplai/opencomplai-enterprise/gateway-api:<version>
#
# Release images are built, signed and pushed by supply-chain.yml in the
# release repository (default Opencomplai/opencomplai-enterprise; override with
# OPENCOMPLAI_RELEASE_REPO=<owner>/<repo>). A <service>:<version> argument
# expands to ghcr.io/<release repo, lowercased>/<service>:<version>; an
# argument containing a "/" is used as is. Verification needs pull access to
# the image, so it works for anyone only if the GHCR packages are public.
#
# Requires: cosign (>= 2.0), jq.
# PRD: Phase 14 — supply-chain integrity verification path for users.

set -euo pipefail

REF="${1:?Usage: $0 <service>:<version> | <image-reference>}"
RELEASE_REPO="${OPENCOMPLAI_RELEASE_REPO:-Opencomplai/opencomplai-enterprise}"

case "$REF" in
  */*) IMAGE="$REF" ;;
  *) IMAGE="ghcr.io/$(printf '%s' "$RELEASE_REPO" | tr '[:upper:]' '[:lower:]')/$REF" ;;
esac

OIDC_ISSUER="https://token.actions.githubusercontent.com"
# The repo name is not regex-escaped: a "." in it matching any character is harmless.
IDENTITY_REGEXP="^https://github.com/${RELEASE_REPO}/\.github/workflows/supply-chain\.yml@"

echo "==> Image:    $IMAGE"
echo "==> Identity: $IDENTITY_REGEXP"

echo "==> Verifying image signature: $IMAGE"
cosign verify \
  --certificate-oidc-issuer "$OIDC_ISSUER" \
  --certificate-identity-regexp "$IDENTITY_REGEXP" \
  "$IMAGE" > /dev/null

echo "==> Verifying SBOM attestation: $IMAGE"
cosign verify-attestation \
  --type spdxjson \
  --certificate-oidc-issuer "$OIDC_ISSUER" \
  --certificate-identity-regexp "$IDENTITY_REGEXP" \
  "$IMAGE" \
  | jq -r '.payload | @base64d | fromjson | .predicate.name'

echo "==> OK — image and SBOM attestation verified."
