"""
OIDC client-credentials (machine-to-machine) token acquisition.

Each OSS install receives a client_id/client_secret pair from admin-api's
``/enroll`` endpoint, alongside its Ed25519 signing key (see
``commands/dashboard.py``'s ``enroll()``). Before calling ingest-api, the
CLI exchanges those credentials directly with the IdP's token endpoint for
a short-lived JWT via the OAuth2 client_credentials grant (RFC 6749 §4.4)
— no browser, no user interaction, works identically in local runs and CI.

Uses stdlib ``urllib`` rather than a new HTTP dependency, matching every
other HTTP call already in this CLI (``main.py``'s ``_call_service``,
``commands/dashboard.py``'s ``_post``, both CI connectors).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request


class OidcTokenError(Exception):
    """Raised when the token endpoint rejects the request or returns an
    unparseable response."""


def acquire_token(
    token_endpoint: str,
    client_id: str,
    client_secret: str,
    scope: str | None = None,
    timeout: int = 30,
) -> tuple[str, int]:
    """
    Exchange client_id/client_secret for a bearer JWT via the OAuth2
    client_credentials grant. Returns (access_token, expires_in_seconds).

    Raises OidcTokenError on any non-2xx response or a response missing
    access_token.
    """
    form = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }
    if scope:
        form["scope"] = scope
    data = urllib.parse.urlencode(form).encode("ascii")

    req = urllib.request.Request(
        token_endpoint,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        raise OidcTokenError(
            f"token endpoint returned {exc.code}: {exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        raise OidcTokenError(f"token endpoint unreachable: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise OidcTokenError("token endpoint returned a non-JSON response") from exc

    access_token = body.get("access_token")
    if not access_token or not isinstance(access_token, str):
        raise OidcTokenError("token endpoint response missing access_token")
    expires_in = body.get("expires_in", 3600)
    if not isinstance(expires_in, int):
        expires_in = 3600
    return access_token, expires_in


__all__ = ["OidcTokenError", "acquire_token"]
