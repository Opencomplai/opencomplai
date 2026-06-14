"""
Offline (deterministic stub) adapter.

Used in airgap scan mode and all unit tests. Always returns the expected_value
from the claim, so every claim resolves as VERIFIED — this is intentional for
local/offline environments where external verification is unavailable.
"""

from __future__ import annotations

from opencomplai_core.adapters.base import SourceAdapter


class OfflineAdapter(SourceAdapter):
    """
    Returns expected_value from the claim as the lookup result.

    Produces a deterministic, dependency-free response suitable for
    airgap mode and CI environments that cannot reach external sources.
    """

    async def lookup(self, claim: dict) -> dict:
        return {
            "value": claim.get("expected_value"),
            "source": "offline",
            "deterministic": True,
        }
