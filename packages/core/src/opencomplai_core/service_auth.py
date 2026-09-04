"""
Service-to-service authentication for the internal Python services
(evidence-vault, risk-engine, doc-generator, egress-proxy) and their callers
(gateway-api, and the services calling each other directly).

Docker-compose network isolation was the only boundary protecting these
services (SEC-SERVICE-AUTH); this module makes that boundary explicit and
enforceable regardless of deployment topology. A caller proves its identity
with a short-lived, HMAC-SHA256-signed bearer token minted from a shared
secret (``INTERNAL_SERVICE_TOKEN_SECRET``) — no CA/cert provisioning needed,
matching the constraints of a docker-compose-only deployment today. The same
secret is distributed to every service and every caller via environment
variable, mirroring how ``OPENCOMPLAI_API_KEY`` is already distributed to
gateway-api.

Token format: ``<payload_b64>.<signature_b64>`` where ``payload_b64`` is the
base64url encoding of ``{"iss": <caller-service-name>, "exp": <unix-ts>}``
and ``signature_b64`` is the base64url HMAC-SHA256 of ``payload_b64`` under
the shared secret. Verification recomputes the HMAC in constant time and
checks ``exp``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass

DEFAULT_TOKEN_TTL_SECONDS = 300


class ServiceTokenError(RuntimeError):
    """Raised when a service token is missing, malformed, expired, or unsigned by the shared secret."""


@dataclass(frozen=True)
class ServiceTokenClaims:
    issuer: str
    expires_at: int


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(payload_b64: str, secret: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).digest()
    return _b64encode(digest)


def mint_service_token(
    issuer: str, secret: str, ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS
) -> str:
    """Mint a signed, short-lived bearer token identifying ``issuer`` as the caller."""
    payload = {"iss": issuer, "exp": int(time.time()) + ttl_seconds}
    payload_b64 = _b64encode(json.dumps(payload, sort_keys=True).encode("utf-8"))
    signature_b64 = _sign(payload_b64, secret)
    return f"{payload_b64}.{signature_b64}"


def verify_service_token(token: str, secret: str) -> ServiceTokenClaims:
    """
    Verify a token minted by ``mint_service_token`` against ``secret``.

    Raises ``ServiceTokenError`` on any malformed, unsigned, or expired token —
    callers should treat this uniformly as "reject the request", not branch on
    the failure reason.
    """
    try:
        payload_b64, signature_b64 = token.split(".", 1)
    except ValueError:
        raise ServiceTokenError("malformed token") from None

    expected_signature_b64 = _sign(payload_b64, secret)
    if not hmac.compare_digest(signature_b64, expected_signature_b64):
        raise ServiceTokenError("invalid signature")

    try:
        payload = json.loads(_b64decode(payload_b64))
        issuer = payload["iss"]
        expires_at = int(payload["exp"])
    except Exception as exc:
        raise ServiceTokenError("malformed payload") from exc

    if not isinstance(issuer, str) or not issuer:
        raise ServiceTokenError("missing issuer")
    if time.time() >= expires_at:
        raise ServiceTokenError("expired token")

    return ServiceTokenClaims(issuer=issuer, expires_at=expires_at)


def load_shared_secret(env: dict[str, str] | None = None) -> str | None:
    """
    Read ``INTERNAL_SERVICE_TOKEN_SECRET`` from the environment.

    Returns ``None`` if unset — callers decide what that means for them (a
    FastAPI dependency should fail closed; a minting call site has nothing
    to mint with and should fail loudly rather than send an unsigned request).
    """
    source = env if env is not None else os.environ
    value = source.get("INTERNAL_SERVICE_TOKEN_SECRET", "").strip()
    return value or None
