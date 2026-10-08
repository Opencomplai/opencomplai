"""Service-payload fragment for the structured human-oversight block."""

from __future__ import annotations

from typing import Any


def oversight_payload(manifest: Any) -> dict[str, Any]:
    """`{"human_oversight": {...}}` when the manifest declares the block, else `{}`.

    The two hand-picked `/v1/docs/generate` payloads spread this in, so a
    manifest without the block sends exactly the keys it sent before.
    """
    block = getattr(manifest, "human_oversight", None)
    return {"human_oversight": block.model_dump(mode="json")} if block else {}
