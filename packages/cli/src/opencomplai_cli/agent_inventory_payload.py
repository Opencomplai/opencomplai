"""Service-payload fragment for the declared agent inventory."""

from __future__ import annotations

from typing import Any


def agent_inventory_payload(manifest: Any) -> dict[str, Any]:
    """`{"agent_inventory": {...}}` when the manifest declares the block, else `{}`.

    Spread into the two hand-picked `/v1/docs/generate` payloads, so a manifest
    without the block sends exactly the keys it sent before.
    """
    block = getattr(manifest, "agent_inventory", None)
    return {"agent_inventory": block.model_dump(mode="json")} if block else {}
