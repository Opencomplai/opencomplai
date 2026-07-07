#!/usr/bin/env bash
# Verify the cosign signature and the SBOM attestation for a published
# Opencomplai container image.
#
# Usage:
#   ./scripts/verify-sbom.sh ghcr.io/opencomplai/opencomplai/gateway-api:1.0.0
#
# Requires: cosign (>= 2.0), jq.
# PRD: Phase 14 — supply-chain integrity verification path for users.

set -euo pipefail

IMAGE="${1:?Usage: $0 <image-reference>}"

OIDC_ISSUER="https://token.actions.githubusercontent.com"
IDENTITY_REGEXP="^https://github.com/Opencomplai/opencomplai/\.github/workflows/supply-chain\.yml@"

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
