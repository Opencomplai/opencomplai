"""Abstract base class for ground-truth source adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod


class SourceAdapter(ABC):
    """
    Adapter that fetches a ground-truth value for a given claim.

    Implementations must be safe to call concurrently and must not
    store mutable state between calls.
    """

    @abstractmethod
    async def lookup(self, claim: dict) -> dict:
        """
        Look up the ground-truth value for claim.

        Args:
            claim: dict with at least claim_ref, source_ref, and optionally
                   expected_value, metric, threshold.

        Returns:
            dict with at least a "value" key containing the looked-up value.
            May include additional metadata (e.g. source, timestamp).

        Raises:
            RuntimeError: if the external source is unavailable (caller should
                          treat this as DEPENDENCY_UNAVAILABLE).
        """
        ...
