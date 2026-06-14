"""Source adapter registry for the Ground Truth Verification Graph."""

from __future__ import annotations

from opencomplai_core.adapters.base import SourceAdapter
from opencomplai_core.adapters.http import HTTPAdapter
from opencomplai_core.adapters.offline import OfflineAdapter

__all__ = ["HTTPAdapter", "OfflineAdapter", "SourceAdapter", "get_adapter"]


def get_adapter(source_ref: str, egress_proxy_url: str = "") -> SourceAdapter:
    """
    Return the appropriate SourceAdapter for source_ref.

    Routing:
      offline://* → OfflineAdapter (deterministic stub; safe in airgap/tests)
      http://* | https://* → HTTPAdapter (routes through egress proxy)
      (anything else) → OfflineAdapter as safe fallback
    """
    if source_ref.startswith("offline://") or not source_ref.startswith(
        ("http://", "https://")
    ):
        return OfflineAdapter()
    return HTTPAdapter(egress_proxy_url=egress_proxy_url)
