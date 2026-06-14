"""
HTTP adapter — routes external source lookups through the egress proxy.

All outbound HTTP calls must go through the egress proxy (REQ-ARC-001).
Raises RuntimeError on connectivity failure so the caller can handle
DEPENDENCY_UNAVAILABLE and queue for retry.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from opencomplai_core.adapters.base import SourceAdapter


class HTTPAdapter(SourceAdapter):
    """
    Fetches a ground-truth value from an external HTTP source via the egress proxy.

    The egress proxy enforces the allowlisted schema and destinations
    (PRD §4.4); this adapter just routes through it.
    """

    def __init__(self, egress_proxy_url: str = "http://egress-proxy:8004") -> None:
        self._proxy_url = egress_proxy_url.rstrip("/")

    async def lookup(self, claim: dict) -> dict:
        source_ref = claim.get("source_ref", "")
        if not source_ref:
            raise RuntimeError("claim missing source_ref for HTTP lookup")

        payload = json.dumps(
            {
                "destination": source_ref,
                "claim_ref": claim.get("claim_ref", ""),
                "expected_value": claim.get("expected_value"),
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            f"{self._proxy_url}/v1/egress/lookup",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode(errors="replace")
            raise RuntimeError(
                f"Egress proxy returned {exc.code} for {source_ref}: {body}"
            ) from exc
        except Exception as exc:
            raise RuntimeError(f"HTTP adapter lookup failed: {exc}") from exc
